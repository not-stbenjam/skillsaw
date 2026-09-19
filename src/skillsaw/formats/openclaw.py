"""Native OpenClaw authoring contracts, pinned to upstream 912b21b98581.

Source: https://github.com/openclaw/openclaw/blob/912b21b98581c0be3baad87fe3686b64d69fffeb/src/plugins/manifest.ts
Native manifests are JSON5; package.json remains ordinary JSON. Optional
runtime capability metadata is deliberately forward compatible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillsaw.paths import contained_resolve, safe_is_file, safe_resolve
from skillsaw.utils import read_text, _file_cache

MANIFEST = "openclaw.plugin.json"


@_file_cache.cached
def read_manifest(path: Path) -> tuple[Any, str | None]:
    """Read JSON first (the common fast path), falling back to native JSON5."""
    content = read_text(path)
    if content is None:
        return None, "Cannot read manifest"
    try:
        return json.loads(content), None
    except RecursionError:
        return None, "Manifest nesting exceeds the parser limit"
    except ValueError:
        import json5

        try:
            return json5.loads(content), None
        except (ValueError, RecursionError) as exc:
            return None, str(exc)


def contained_file(root: Path, name: str) -> bool:
    resolved = safe_resolve(root)
    return (
        resolved is not None
        and contained_resolve(root / name, resolved) is not None
        and safe_is_file(root / name)
    )


def skill_roots(plugin: Path) -> list[Path]:
    """Only explicitly declared skill roots load; there is no skills/ fallback."""
    if not contained_file(plugin, MANIFEST):
        return []
    data, _ = read_manifest(plugin / MANIFEST)
    raw = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    return [plugin / value.strip() for value in raw if isinstance(value, str) and value.strip()]
