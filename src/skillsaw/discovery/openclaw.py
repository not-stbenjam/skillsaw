"""State-free native OpenClaw package discovery over the shared repository scan."""

from pathlib import Path
from typing import Callable, Iterable

from skillsaw.formats.openclaw import MANIFEST, contained_file
from skillsaw.paths import safe_exists, safe_is_symlink, safe_resolve, contained_resolve
from skillsaw.utils import read_json


def claims_plugin(root: Path) -> bool:
    """A native marker or explicit package metadata declares ecosystem identity.

    Even broken markers claim the directory, allowing a useful diagnostic
    without allowing their target to be read outside the package.
    """
    marker = root / MANIFEST
    if safe_exists(marker) or safe_is_symlink(marker):
        return True
    if not contained_file(root, "package.json"):
        return False
    data, _ = read_json(root / "package.json")
    return isinstance(data, dict) and "openclaw" in data


def discover_plugins(
    manifests: Iterable[Path], packages: Iterable[Path], excluded: Callable[[Path], bool]
) -> list[Path]:
    roots = set()
    for path in (*manifests, *packages):
        if excluded(path) or excluded(path.parent):
            continue
        root = safe_resolve(path.parent)
        if root is None or contained_resolve(path, root) is None:
            # A manifest symlink still declares a plugin; never read its target.
            if path.name == MANIFEST and root is not None:
                roots.add(path.parent)
            continue
        if path.name == MANIFEST or claims_plugin(path.parent):
            roots.add(path.parent)
    return sorted(roots)
