"""State-free native OpenClaw package discovery over the shared repository scan."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from skillsaw.formats.openclaw import MANIFEST, contained_file
from skillsaw.paths import safe_exists, safe_is_symlink, safe_resolve, contained_resolve
from skillsaw.utils import read_json, read_text


def declares_extensions(path: Path) -> bool:
    """Package hook packs alone are not native plugins; extensions declare one."""
    content = read_text(path)
    # Escaped keys are legal JSON too, so a backslash requires parsing.
    if not content or ('"openclaw"' not in content and "\\" not in content):
        return False
    data, _ = read_json(path)
    metadata = data.get("openclaw") if isinstance(data, dict) else None
    return isinstance(metadata, dict) and "extensions" in metadata


def claims_plugin(root: Path) -> bool:
    """Native markers and package extension declarations establish ownership.

    Even broken markers claim the directory, allowing a useful diagnostic
    without allowing their target to be read outside the plugin.
    """
    marker = root / MANIFEST
    if safe_exists(marker) or safe_is_symlink(marker):
        return True
    return contained_file(root, "package.json") and declares_extensions(root / "package.json")


def discover_plugins(
    manifests: Iterable[Path], packages: Iterable[Path], excluded: Callable[[Path], bool]
) -> list[Path]:
    """Find native declarations without reading files outside their plugin."""
    roots: set[Path] = set()
    for path in (*manifests, *packages):
        if excluded(path) or excluded(path.parent):
            continue
        root = safe_resolve(path.parent)
        if root is None:
            continue
        # A manifest symlink still declares a plugin; never read its target.
        if path.name == MANIFEST:
            roots.add(path.parent)
        elif contained_resolve(path, root) is not None and declares_extensions(path):
            roots.add(path.parent)
    return sorted(roots)
