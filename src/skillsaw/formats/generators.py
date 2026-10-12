"""Pinned authored-source contracts, not target compilers.

Ruler v0.3.44 (658d1bc), src/core/ConfigLoader.ts and FileSystemUtils.ts.
Rulesync v32.0.0 (01118a9), src/config/config.ts and
src/features/rules/rulesync-rule.ts. See docs/generators.md for evidence.
"""

from __future__ import annotations

import re

import yaml

from skillsaw.utils import _SAFE_LOADER

# Unlike portable skill frontmatter, an entirely empty rule header is valid.
_RULE_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n((?:.*?\r?\n)?)---[ \t]*\r?(?:\n|\Z)", re.DOTALL)

STRING = {"type": "string"}
BOOLEAN = {"type": "boolean"}
STRINGS = {"type": "array", "items": STRING}


def object_schema(properties, *, additional=True):
    return {"type": "object", "properties": properties, "additionalProperties": additional}


_MCP_TOGGLE = object_schema(
    {
        "enabled": BOOLEAN,
        "merge_strategy": {"enum": ["merge", "overwrite"]},
    },
    additional=False,
)
_SERVERS = {"type": "object", "additionalProperties": {"type": "object"}}
_AGENT = object_schema(
    {
        "enabled": BOOLEAN,
        "output_path": STRING,
        "output_path_instructions": STRING,
        "output_path_config": STRING,
        "mcp": _MCP_TOGGLE,
        "mcp_servers": _SERVERS,
    },
    additional=False,
)
_SUBAGENTS = {key: BOOLEAN for key in ("enabled", "include_in_rules", "cleanup_orphaned")}
RULER_CONFIG = object_schema(
    {
        "default_agents": STRINGS,
        "agents": object_schema(_SUBAGENTS, additional=_AGENT),
        "mcp": _MCP_TOGGLE,
        "mcp_servers": _SERVERS,
        "gitignore": object_schema({"enabled": BOOLEAN, "local": BOOLEAN}, additional=False),
        "backup": object_schema({"enabled": BOOLEAN}, additional=False),
        "skills": object_schema({"enabled": BOOLEAN}, additional=False),
        "subagents": object_schema(_SUBAGENTS, additional=False),
        "nested": BOOLEAN,
    },
    additional=False,
)

# Only the common authored fields and the two modular copy targets. Unknown
# target names/options are left to the pinned generator's own validation.
RULESYNC_RULE = object_schema(
    {
        "root": BOOLEAN,
        "localRoot": BOOLEAN,
        "targets": STRINGS,
        "description": STRING,
        "globs": STRINGS,
        "claudecode": object_schema({"paths": STRINGS}),
        "cursor": object_schema({"alwaysApply": BOOLEAN, "description": STRING, "globs": STRINGS}),
        "agentsmd": object_schema({"subprojectPath": STRING}),
    }
)
RULESYNC_CONFIG = object_schema(
    {
        "$schema": STRING,
        "targets": {"anyOf": [STRINGS, {"type": "object"}]},
        "features": {"anyOf": [STRINGS, {"type": "object"}]},
        "outputRoots": {
            "anyOf": [
                STRINGS,
                {
                    "type": "object",
                    "additionalProperties": {
                        "anyOf": [STRING, STRINGS],
                    },
                },
            ]
        },
        "inputRoot": STRING,
        "inputRoots": {**STRINGS, "minItems": 1},
        **{
            key: BOOLEAN
            for key in (
                "verbose",
                "delete",
                "global",
                "silent",
                "dryRun",
                "check",
                "simulateCommands",
                "simulateSubagents",
                "simulateSkills",
                "preserveUnownedHooks",
                "deriveSubprojectPathFromGlobs",
                "gitignoreTargetsOnly",
            )
        },
    }
)


def schema_problems(data, schema):
    """Concise field locations; never echo config values (which may be secrets)."""
    from jsonschema import Draft7Validator

    return [
        (
            tuple(error.absolute_path),
            (
                f"{'.'.join(map(str, error.absolute_path)) or 'document'}: "
                f"expected {error.validator_value}"
                if error.validator == "type"
                else f"{'.'.join(map(str, error.absolute_path)) or 'document'}: invalid {error.validator}"
            ),
        )
        for error in Draft7Validator(schema).iter_errors(data)
    ]


class _RulesyncLoader(_SAFE_LOADER):
    # js-yaml's default schema accepts true/false, not YAML 1.1's yes/no/on/off.
    yaml_implicit_resolvers = {
        key: [(tag, pattern) for tag, pattern in values if tag != "tag:yaml.org,2002:bool"]
        for key, values in _SAFE_LOADER.yaml_implicit_resolvers.items()
    }

    def flatten_mapping(self, node):
        # js-yaml rejects duplicate explicit keys; a YAML merge followed by an
        # explicit override is valid and is left to SafeLoader's merge logic.
        # SafeLoader mutates anchored mappings during merge flattening. Check
        # each original mapping once, before inherited keys are inserted.
        checked = self.__dict__.setdefault("_duplicate_checked_nodes", set())
        if node in checked:
            return super().flatten_mapping(node)
        checked.add(node)
        seen = set()
        for key, _value in node.value:
            if key.tag == "tag:yaml.org,2002:merge":
                continue
            value = self.construct_object(key)
            try:
                duplicate = value in seen
                seen.add(value)
            except TypeError:
                continue  # SafeLoader reports an unhashable mapping key.
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "duplicate mapping key",
                    key.start_mark,
                )
        return super().flatten_mapping(node)


_RulesyncLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def parse_rulesync_frontmatter(content):
    """Parse conventional YAML frontmatter, retaining honest body line offsets.

    Rulesync drops null object fields and array entries before validation.
    Noncanonical gray-matter
    fences and target-specific extensions are outside this validator's scope.
    """
    match = _RULE_FRONTMATTER_RE.match(content.lstrip("\ufeff"))
    if match is None:
        return None, None, None, content, 0
    normalized = content.lstrip("\ufeff")
    body = normalized[match.end() :]
    offset = normalized[: match.end()].count("\n")
    try:
        data = yaml.load(match.group(1), Loader=_RulesyncLoader)
    except (yaml.YAMLError, ValueError, RecursionError) as error:
        mark = getattr(error, "problem_mark", None)
        return None, "Invalid YAML frontmatter", mark.line + 2 if mark else None, body, offset
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, "Frontmatter must be a mapping", 2, body, offset
    # Only remove nulls in the fields we interpret, without traversing arbitrary
    # YAML alias graphs. Those graphs remain the generator's validation job.
    data = {key: value for key, value in data.items() if value is not None}
    for key in ("cursor", "claudecode", "agentsmd"):
        if isinstance(data.get(key), dict):
            data[key] = {k: v for k, v in data[key].items() if v is not None}
    for mapping, keys in (
        (data, ("targets", "globs")),
        (data.get("cursor"), ("globs",)),
        (data.get("claudecode"), ("paths",)),
    ):
        if isinstance(mapping, dict):
            for key in keys:
                if isinstance(mapping.get(key), list):
                    mapping[key] = [item for item in mapping[key] if item is not None]
    return data, None, None, body, offset
