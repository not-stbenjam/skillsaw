"""Native OpenClaw authoring contracts, pinned to upstream 912b21b98581.

Source: https://github.com/openclaw/openclaw/blob/912b21b98581c0be3baad87fe3686b64d69fffeb/src/plugins/manifest.ts
Native manifests are JSON5; package.json remains ordinary JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import json5

from skillsaw.paths import contained_resolve, safe_is_file, safe_resolve
from skillsaw.utils import cached_file_read, strip_jsonc

MANIFEST = "openclaw.plugin.json"
# MAX_PLUGIN_MANIFEST_BYTES in the pinned native loader, before any parsing.
MAX_MANIFEST_BYTES = 256 * 1024


@cached_file_read
def read_manifest(path: Path) -> tuple[object | None, str | None]:
    """Bound the read, then prefer JSON/JSONC before the slower JSON5 parser."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except FileNotFoundError:
        return None, f"Missing {MANIFEST}; create it with 'id' and 'configSchema'"
    except OSError:
        return None, f"Cannot read {MANIFEST}; check the file and its permissions"
    if len(raw) > MAX_MANIFEST_BYTES:
        return None, f"Manifest exceeds OpenClaw's {MAX_MANIFEST_BYTES}-byte limit"
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "Manifest must be UTF-8 text"
    try:
        return json.loads(content), None
    except RecursionError:
        return None, "Manifest nesting exceeds the parser limit"
    except ValueError:
        pass
    try:
        # Reuse the JSONC scanner on the already bounded input. Calling
        # read_jsonc(path) here would reopen the file with an unbounded read.
        return json.loads(strip_jsonc(content)), None
    except RecursionError:
        return None, "Manifest nesting exceeds the parser limit"
    except ValueError:
        pass
    try:
        return json5.loads(content), None
    except (ValueError, RecursionError, OverflowError) as exc:
        return None, f"Cannot parse JSON5 manifest: {exc}"


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


def inline_mcp_servers(plugin: Path) -> dict[str, Any] | None:
    """Expose exactly the servers retained by normalizeManifestMcpServers.

    The pinned manifest-capability-normalizers.ts trims server names and
    rejects empty names, prototype keys and non-object entries before the
    runtime sees them. This is host normalization, not Python dict protection.
    """
    if not contained_file(plugin, MANIFEST):
        return None
    data, _ = read_manifest(plugin / MANIFEST)
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        return None
    return {
        key.strip(): value
        for key, value in servers.items()
        if key.strip()
        and key.strip() not in {"__proto__", "prototype", "constructor"}
        and isinstance(value, dict)
    }
