"""Cursor native packaging paths and component resolution.

Reference: https://cursor.com/docs/reference/plugins (2026-09-18).
Explicit component paths replace defaults; catalog metadata is overridden
by the plugin manifest. Resolution never follows paths outside the package.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from skillsaw.discovery.excludes import is_root_or_ancestor_excluded
from skillsaw.discovery.cursor_globs import contained_glob
from skillsaw.paths import (
    contained_resolve,
    has_parent_traversal,
    is_absolute_path,
    safe_is_dir,
    safe_is_file,
)
from skillsaw.utils import read_json_strict

MARKER = ".cursor-plugin"
COMPONENT_EXTENSIONS = {
    "rules": (".md", ".mdc", ".markdown"),
    "agents": (".md", ".mdc", ".markdown"),
    "commands": (".md", ".mdc", ".markdown", ".txt"),
    "skills": (".md",),
}
DEFAULTS = {"hooks": "hooks/hooks.json", "mcpServers": "mcp.json"}


def read_manifest(path: Path) -> tuple[Any, str | None]:
    """Use JSON.parse semantics: duplicate keys keep their last value."""
    return read_json_strict(path, allow_duplicate_keys=True)


def local_source(source: Any) -> str | None:
    """Extract a local catalog source, leaving remote URLs un-fetched."""
    if isinstance(source, dict):
        source = source.get("path")
    if not isinstance(source, str) or not source:
        return None
    if source.casefold().startswith(("https://", "http://", "ssh://", "git://", "git@")):
        return None
    return source


def safe_component(root: Path, value: str) -> Path | None:
    if not value or is_absolute_path(value) or has_parent_traversal(value):
        return None
    return contained_resolve(root / value, root)


def source_path(root: Path, prefix: str, source: str) -> Path | None:
    """A pluginRoot prefix must not disguise an absolute or traversing source."""
    if safe_component(root, source) is None:
        return None
    if prefix and safe_component(root, prefix) is None:
        return None
    if prefix:
        prefix = prefix.replace("\\", "/").rstrip("/")
        source = source.replace("\\", "/")
        # Cursor's template accepts sources that already include pluginRoot.
        if source != prefix and not source.startswith(f"{prefix}/"):
            source = f"{prefix}/{source}"
    return safe_component(root, source)


def component_paths(root: Path, data: dict, field: str) -> list[Path]:
    """Resolve declared paths/globs, or the default when no field exists."""
    value = data.get(field, DEFAULTS.get(field, field))
    values = value if isinstance(value, list) else [value]
    result: set[Path] = set()
    for item in values:
        if not isinstance(item, str) or safe_component(root, item) is None:
            continue
        if any(char in item for char in "*?["):
            try:
                result.update(contained_glob(root, item))
            except (OSError, ValueError, RecursionError):
                continue
        else:
            result.add(root / item)
    return sorted(result)


def component_files(root: Path, data: dict, field: str, excluded=lambda _: False) -> list[Path]:
    """Expand prose components with Cursor's supported file extensions."""
    result: set[Path] = set()
    for path in component_paths(root, data, field):
        if is_root_or_ancestor_excluded(path, root, excluded):
            continue
        if safe_is_dir(path):
            for current, dirs, names in os.walk(path):
                here = Path(current)
                dirs[:] = [name for name in dirs if not excluded(here / name)]
                result.update(
                    p
                    for name in names
                    if (p := here / name).suffix in COMPONENT_EXTENSIONS[field]
                    and not excluded(p)
                    and safe_is_file(p)
                    and contained_resolve(p, root) is not None
                )
        elif safe_is_file(path) and path.suffix in COMPONENT_EXTENSIONS[field]:
            result.add(path)
    return sorted(result)


def skill_dirs(root: Path, data: dict, excluded=lambda _: False) -> list[Path]:
    if "skills" not in data and not safe_is_dir(root / "skills"):
        return (
            [root]
            if safe_is_file(root / "SKILL.md") and contained_resolve(root / "SKILL.md", root)
            else []
        )
    if "skills" not in data:
        directory = root / "skills"
        if (
            is_root_or_ancestor_excluded(directory, root, excluded)
            or contained_resolve(directory, root) is None
        ):
            return []
        try:
            return sorted(
                p
                for p in directory.iterdir()
                if safe_is_file(p / "SKILL.md")
                and contained_resolve(p / "SKILL.md", root) is not None
                and not excluded(p)
                and not excluded(p / "SKILL.md")
            )
        except OSError:
            return []
    return sorted(
        {p.parent for p in component_files(root, data, "skills", excluded) if p.name == "SKILL.md"}
    )
