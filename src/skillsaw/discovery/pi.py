"""Contained, state-free discovery for Pi packages and project resources."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

from pathspec import GitIgnoreSpec
from wcmatch import glob
from bracex import ExpansionLimitException
from wcmatch._wcparse import PatternLimitException

from skillsaw.discovery.detect import WALK_SKIP_DIRS, VENDOR_DIR_NAMES

from skillsaw.formats.pi import REMOTE_PREFIXES, string_list
from skillsaw.paths import contained_resolve, relative_to_str, safe_resolve
from skillsaw.utils import read_json, read_text

_FLAGS = glob.GLOBSTAR | glob.BRACE | glob.EXTGLOB
_SKIP_DIRS = WALK_SKIP_DIRS | VENDOR_DIR_NAMES
_PATTERN_SECONDS = 0.02
_MAX_PATTERN_LENGTH = 1024
_MAX_IGNORE_PATTERNS = 4096


@lru_cache(maxsize=256)
def _compile_glob(pattern: str):
    # Imported lazily: discovery also runs while RepositoryContext initializes.
    from skillsaw.rules.builtin.content_analysis import RegexTimeout, regex_timeout

    if not pattern or len(pattern) > _MAX_PATTERN_LENGTH:
        return None
    try:
        with regex_timeout(_PATTERN_SECONDS):
            return glob.compile(pattern, flags=_FLAGS, limit=256)
    except (
        PatternLimitException,
        ExpansionLimitException,
        ValueError,
        re.error,
        RecursionError,
        RegexTimeout,
    ):
        return None


def _globmatch(value: str, pattern: str) -> bool:
    from skillsaw.rules.builtin.content_analysis import RegexTimeout, regex_timeout

    compiled = _compile_glob(pattern)
    if compiled is None:
        return False
    try:
        with regex_timeout(_PATTERN_SECONDS):
            return compiled.match(value)
    except (ValueError, re.error, RecursionError, RegexTimeout):
        return False


def _ignore_patterns(lines: Iterable[str]) -> list:
    from skillsaw.rules.builtin.content_analysis import RegexTimeout, regex_timeout

    patterns = []
    for index, line in enumerate(lines):
        if index >= _MAX_IGNORE_PATTERNS:
            break
        if len(line) > _MAX_PATTERN_LENGTH:
            continue
        try:
            with regex_timeout(_PATTERN_SECONDS):
                patterns.extend(GitIgnoreSpec.from_lines([line], backend="simple").patterns)
        except (ValueError, re.error, RecursionError, RegexTimeout):
            # GitIgnorePatternError (including the legacy GitWildMatch spelling)
            # derives from ValueError. A bad line must not suppress valid siblings.
            continue
    return patterns


def _ignored(ignore: GitIgnoreSpec, value: str) -> bool:
    from skillsaw.rules.builtin.content_analysis import RegexTimeout, regex_timeout

    try:
        with regex_timeout(_PATTERN_SECONDS):
            return ignore.match_file(value)
    except (ValueError, re.error, RecursionError, RegexTimeout):
        return False


def package_marker(path: Path) -> bool:
    """An explicit Pi key or gallery keyword identifies an npm package."""
    data, error = read_json(path)
    return (
        not error
        and isinstance(data, dict)
        and (
            "pi" in data
            or (isinstance(data.get("keywords"), list) and "pi-package" in data["keywords"])
        )
    )


def local_path(base: Path, value: str, boundary: Path) -> Path | None:
    """Resolve only repository-local resources; never consult home or the network."""
    if not value or value.startswith(("~", *REMOTE_PREFIXES)) or "\x00" in value:
        return None
    path = Path(os.path.abspath(base / value))
    return path if contained_resolve(path, boundary) is not None else None


def package_roots(
    root: Path,
    manifests: Iterable[Path],
    settings: Iterable[Path],
    excluded: Callable[[Path], bool],
) -> list[Path]:
    """Use the shared scan and local settings sources, without installing packages."""
    roots = set()
    for manifest in manifests:
        if (
            contained_resolve(manifest, root) is not None
            and not excluded(manifest)
            and package_marker(manifest)
        ):
            roots.add(manifest.parent)
    for path in settings:
        if contained_resolve(path, root) is None or excluded(path):
            continue
        data, _ = read_json(path)
        packages = data.get("packages") if isinstance(data, dict) else None
        if not isinstance(packages, list):
            continue
        for entry in packages:
            source = entry.get("source") if isinstance(entry, dict) else entry
            if not isinstance(source, str):
                continue
            local = local_path(path.parent, source, root)
            if local is not None and local.is_dir() and not excluded(local):
                roots.add(local)
    return sorted(roots)


def _matches(path: Path, pattern: str, base: Path, exact: bool = False) -> bool:
    candidates = [path]
    if path.name == "SKILL.md":
        candidates.append(path.parent)
    if exact:
        target = safe_resolve(base / pattern)
        return target is not None and any(safe_resolve(p) == target for p in candidates)
    return any(
        _globmatch(value, pattern.removeprefix("./"))
        for p in candidates
        for value in (relative_to_str(p, base) or str(p), p.name, str(p))
    )


def filter_resources(paths: Iterable[Path], patterns: list[str], base: Path) -> list[Path]:
    """Pi applies inclusion, exclusion, force-inclusion, then force-exclusion."""
    includes = [p for p in patterns if not p.startswith(("!", "+", "-"))]
    result = []
    for path in paths:
        enabled = not includes or any(_matches(path, p, base) for p in includes)
        if any(_matches(path, p[1:], base) for p in patterns if p.startswith("!")):
            enabled = False
        if any(_matches(path, p[1:], base, True) for p in patterns if p.startswith("+")):
            enabled = True
        if any(_matches(path, p[1:], base, True) for p in patterns if p.startswith("-")):
            enabled = False
        if enabled:
            result.append(path)
    return result


def visible_paths(base: Path, boundary: Path, excluded: Callable[[Path], bool]) -> list[Path]:
    """Glob candidates: visible paths only, never descend through a symlink."""
    if contained_resolve(base, boundary) is None or excluded(base):
        return []
    result = []
    for directory, dirs, files in os.walk(base, followlinks=False):
        here = Path(directory)
        dirs[:] = sorted(
            d
            for d in dirs
            if not d.startswith(".") and d not in _SKIP_DIRS and not excluded(here / d)
        )
        for name in dirs + sorted(files):
            path = here / name
            if (
                not name.startswith(".")
                and not excluded(path)
                and contained_resolve(path, boundary) is not None
            ):
                result.append(path)
    return result


def extension_entries(
    directory: Path, boundary: Path, excluded: Callable[[Path], bool]
) -> list[Path]:
    """An extension root declares exact entries or defaults to index.ts/index.js.

    If every declared entry fails containment, fall back to the default names.
    """
    manifest = directory / "package.json"
    data, _ = (
        read_json(manifest)
        if contained_resolve(manifest, boundary) is not None and not excluded(manifest)
        else (None, None)
    )
    pi = data.get("pi") if isinstance(data, dict) else None
    entries = pi.get("extensions") if isinstance(pi, dict) else None
    if string_list(entries) and entries:
        found = []
        for entry in entries:
            path = local_path(directory, entry, boundary)
            if path is not None and path.exists() and not excluded(path):
                found.append(path)
        if found:
            return found
    for name in ("index.ts", "index.js"):
        path = directory / name
        if contained_resolve(path, boundary) is not None and path.is_file() and not excluded(path):
            return [path]
    return []


def collect(
    path: Path,
    kind: str,
    boundary: Path,
    excluded: Callable[[Path], bool],
    *,
    shallow: bool = False,
) -> list[Path]:
    """Match Pi's resource walk, with cycle and repository-containment guards."""
    visited: set[Path] = set()
    suffixes = {
        "skills": (".md",),
        "prompts": (".md",),
        "themes": (".json",),
        "extensions": (
            ".ts",
            ".js",
        ),
    }

    def walk(current: Path, top: bool, ignore: GitIgnoreSpec) -> list[Path]:
        resolved = contained_resolve(current, boundary)
        if resolved is None or resolved in visited or excluded(current):
            return []
        visited.add(resolved)
        if current.is_file():
            return [current] if current.suffix in suffixes[kind] else []
        if not current.is_dir():
            return []
        if kind == "extensions":
            entries = extension_entries(current, boundary, excluded)
            if entries:
                return entries
        patterns = list(ignore.patterns)
        for name in (".gitignore", ".ignore", ".fdignore"):
            ignore_path = current / name
            if contained_resolve(ignore_path, boundary) is None:
                continue
            try:
                if ignore_path.stat().st_size > 128 * 1024:
                    continue
            except OSError:
                continue
            text = read_text(ignore_path) or ""
            # Keep nested rules relative to the directory declaring them.
            prefix = relative_to_str(current, path)
            prefix = "" if prefix == "." else prefix
            lines = []
            for line in text.splitlines():
                if not line or line.startswith("#"):
                    continue
                neg = line.startswith("!")
                raw = line[1:] if neg else line
                if prefix:
                    raw = prefix + "/" + raw.lstrip("/")
                lines.append(("!" if neg else "") + raw)
            patterns.extend(_ignore_patterns(lines))
        ignore = GitIgnoreSpec(patterns[-_MAX_IGNORE_PATTERNS:], backend="simple")

        def ignored(p: Path) -> bool:
            rel = (relative_to_str(p, path) or p.name) + ("/" if p.is_dir() else "")
            return _ignored(ignore, rel)

        entrypoint = current / "SKILL.md"
        if kind == "skills" and entrypoint.is_file() and not ignored(entrypoint):
            return walk(entrypoint, False, ignore)
        try:
            children = sorted(current.iterdir())
        except OSError:
            return []
        found = []
        for child in children:
            if child.name.startswith(".") or child.name in _SKIP_DIRS or ignored(child):
                continue
            if child.is_dir():
                if shallow:
                    continue
                if kind == "extensions":
                    found.extend(extension_entries(child, boundary, excluded))
                else:
                    found.extend(walk(child, False, ignore))
            elif kind != "skills" or top:
                found.extend(walk(child, False, ignore))
        return found

    if path.is_file() and contained_resolve(path, boundary) is not None and not excluded(path):
        # Explicit files have no suffix restriction in Pi's loader.
        return [path]
    try:
        return walk(path, True, GitIgnoreSpec([], backend="simple"))
    except RecursionError:
        # Deep repository trees must not escape the constructor's discovery leg.
        return []


def resources(
    base: Path,
    kind: str,
    entries: object,
    boundary: Path,
    excluded: Callable[[Path], bool],
    *,
    manifest: bool = True,
) -> list[Path]:
    """Expand manifest globs; settings wildcards filter existing literal roots."""
    if not string_list(entries):
        return []
    paths = []
    candidates = None
    for entry in entries:
        if entry.startswith(("!", "+", "-")):
            continue
        if "*" in entry or "?" in entry:
            if not manifest:
                continue
            if candidates is None:
                candidates = visible_paths(base, boundary, excluded)
            roots = [
                p
                for p in candidates
                if _globmatch(relative_to_str(p, base) or p.name, entry.removeprefix("./"))
            ]
        else:
            local = local_path(base, entry, boundary)
            roots = [local] if local is not None else []
        for resource in roots:
            paths.extend(collect(resource, kind, boundary, excluded))
    patterns = [
        p
        for p in entries
        if p.startswith(("!", "+", "-")) or (not manifest and ("*" in p or "?" in p))
    ]
    return sorted(set(filter_resources(paths, patterns, base)))


def package_resources(
    base: Path,
    kind: str,
    boundary: Path,
    excluded: Callable[[Path], bool],
) -> list[Path]:
    manifest = base / "package.json"
    data, _ = (
        read_json(manifest)
        if contained_resolve(manifest, boundary) is not None and not excluded(manifest)
        else (None, None)
    )
    pi = data.get("pi") if isinstance(data, dict) else None
    if isinstance(pi, dict):
        return resources(base, kind, pi.get(kind, []), boundary, excluded)
    return collect(base / kind, kind, boundary, excluded)


def project_resources(
    directory: Path,
    kind: str,
    boundary: Path,
    excluded: Callable[[Path], bool],
) -> list[Path]:
    """Autoload and explicitly configured resources share override semantics."""
    settings = directory / "settings.json"
    data, _ = (
        read_json(settings)
        if contained_resolve(settings, boundary) is not None and not excluded(settings)
        else (None, None)
    )
    entries = data.get(kind, []) if isinstance(data, dict) else []
    overrides = (
        [p for p in entries if p.startswith(("!", "+", "-"))] if string_list(entries) else []
    )
    automatic = collect(
        directory / kind, kind, boundary, excluded, shallow=kind in {"prompts", "themes"}
    )
    automatic = filter_resources(automatic, overrides, directory)
    explicit = resources(
        directory,
        kind,
        entries,
        boundary,
        excluded,
        manifest=False,
    )
    return sorted(set(automatic + explicit))
