"""State-free discovery of Cursor catalogs and native plugin declarations."""

from pathlib import Path
from typing import Callable, Iterable

from skillsaw.discovery.excludes import is_root_or_ancestor_excluded
from skillsaw.formats.cursor import MARKER, local_source, read_manifest, source_path
from skillsaw.paths import contained_resolve, safe_exists, safe_is_dir, safe_is_symlink


def catalogs(root: Path, markers: Iterable[Path], excluded: Callable[[Path], bool]) -> list[Path]:
    return sorted(
        {
            p
            for marker in (root / MARKER, *markers)
            if contained_resolve(marker, root) is not None
            and contained_resolve(marker, marker.parent) is not None
            for p in [marker / "marketplace.json"]
            if (safe_exists(p) or safe_is_symlink(p))
            and contained_resolve(p, marker.parent) is not None
            and not is_root_or_ancestor_excluded(p, root, excluded)
        }
    )


def entries(paths: Iterable[Path]) -> dict[Path, list[tuple[Path, dict]]]:
    """Local claims, retaining catalog origins for merged inline components."""
    found: dict[Path, list[tuple[Path, dict]]] = {}
    for path in paths:
        data, error = read_manifest(path)
        if error or not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
            continue
        metadata = data.get("metadata")
        prefix = metadata.get("pluginRoot", "") if isinstance(metadata, dict) else ""
        if not isinstance(prefix, str):
            continue
        for entry in data["plugins"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                continue
            source = local_source(entry.get("source"))
            if source is None:
                continue
            target = source_path(path.parent.parent, prefix, source)
            if target is not None:
                found.setdefault(target, []).append((path, entry))
    return found


def plugins(
    root: Path, markers: Iterable[Path], claims: Iterable[Path], excluded: Callable[[Path], bool]
) -> list[Path]:
    found = set(claims)
    for marker in markers:
        manifest = marker / "plugin.json"
        if safe_exists(manifest) or safe_is_symlink(manifest):
            found.add(marker.parent)
    return sorted(
        p
        for p in found
        if safe_is_dir(p)
        and contained_resolve(p, root) is not None
        and contained_resolve(p / MARKER / "plugin.json", p) is not None
        and not is_root_or_ancestor_excluded(p, root, excluded)
        and not is_root_or_ancestor_excluded(p / MARKER / "plugin.json", root, excluded)
    )
