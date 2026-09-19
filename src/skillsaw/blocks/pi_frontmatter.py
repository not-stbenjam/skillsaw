"""Pi-local YAML core schema and frontmatter boundaries.

Pi's npm ``yaml.parse`` defaults to YAML 1.2 core: timestamps and yes/no
are strings, duplicate mapping keys fail, and merge keys have no special
meaning. Keep these choices isolated from portable Agent Skills parsing.
"""

from __future__ import annotations

import math
import re
from typing import Any, NamedTuple

import yaml

from skillsaw.utils import _SAFE_LOADER

_TAG = "tag:yaml.org,2002:"


class _PiLoader(_SAFE_LOADER):
    # Independent table: never mutate the resolver used by other hosts.
    yaml_implicit_resolvers = {}

    def construct_mapping(self, node, deep=False):
        seen = {}
        for key, _value in node.value:
            if isinstance(key, yaml.ScalarNode):
                value = self.construct_object(key, deep=deep)
                if type(value) in (int, float):
                    # npm YAML compares numeric keys as JavaScript Numbers:
                    # integer/float spellings share equality, but NaN never does.
                    try:
                        number = float(value)
                    except OverflowError:
                        number = math.inf if value > 0 else -math.inf
                    if math.isnan(number):
                        continue
                    identity = (float, number)
                else:
                    identity = (type(value), value)
                try:
                    duplicate = identity in seen
                except TypeError as exc:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        "found unhashable key",
                        key.start_mark,
                    ) from exc
                if duplicate:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        "duplicate mapping key",
                        None if seen[identity] is key else key.start_mark,
                    )
                seen[identity] = key
        # Do not flatten_mapping: the core schema leaves << as ordinary data.
        return yaml.constructor.BaseConstructor.construct_mapping(self, node, deep=deep)

    def construct_yaml_int(self, node):
        value = self.construct_scalar(node)
        radix = 8 if value.startswith("0o") else 16 if value.startswith("0x") else 10
        return int(value, radix)


# Match npm yaml's core schema, including decimal leading zeroes and exponent
# floats. YAML 1.1's binary, sexagesimal and underscored numbers remain strings.
for _name, _pattern, _initial in (
    ("null", r"^(?:~|null|Null|NULL|)$", "~nN"),
    ("bool", r"^(?:true|True|TRUE|false|False|FALSE)$", "tTfF"),
    ("int", r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$", "-+0123456789"),
    (
        "float",
        r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)[eE][-+]?[0-9]+"
        r"|[-+]?(?:\.[0-9]+|[0-9]+\.[0-9]*)"
        r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$",
        "-+0123456789.",
    ),
):
    _PiLoader.add_implicit_resolver(_TAG + _name, re.compile(_pattern), list(_initial))
_PiLoader.add_implicit_resolver(_TAG + "null", re.compile(r"^$"), [""])
_PiLoader.add_constructor(_TAG + "int", _PiLoader.construct_yaml_int)


class PiFrontmatter(NamedTuple):
    data: dict[str, Any] | None
    error: str | None
    error_line: int | None
    body: str
    line_offset: int
    key_lines: dict[str, int]


def parse_pi_frontmatter(content: str) -> PiFrontmatter:
    """Share native parsing with flat eligibility; preserve body splice spans."""
    missing = PiFrontmatter(None, None, None, content, 0, {})
    if not content.startswith("---"):
        return missing
    end = content.find("\n---", 3)
    if end < 0:
        return missing
    text = content[4:end]
    yaml_offset = content[:4].count("\n")
    body_start = end + 4
    if content[body_start : body_start + 1] == "\n":
        body_start += 1
    loader = _PiLoader(text)
    key_lines = {}
    try:
        node = loader.get_single_node()
        data = loader.construct_document(node) if node is not None else {}
        if isinstance(node, yaml.MappingNode):
            key_lines = {
                key.value: key.start_mark.line + yaml_offset + 1
                for key, _value in node.value
                if isinstance(key, yaml.ScalarNode) and key.tag == _TAG + "str"
            }
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + yaml_offset + 1 if mark is not None else None
        return PiFrontmatter(None, "Invalid YAML frontmatter", line, content, 0, {})
    finally:
        loader.dispose()
    # Non-mappings have no description in Pi. Declared skills get the required
    # description diagnostic; flat documents are ignored.
    return PiFrontmatter(
        data if isinstance(data, dict) else {},
        None,
        None,
        content[body_start:],
        content[:body_start].count("\n"),
        key_lines,
    )
