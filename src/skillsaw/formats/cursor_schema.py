"""Offline Cursor validators, reconciling publication schemas and host docs."""

import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft7Validator, FormatChecker


@lru_cache(maxsize=2)
def validator(kind: str):
    package = files("skillsaw.schemas.cursor")
    plugin = json.loads(package.joinpath("plugin.schema.json").read_text())
    schema = (
        plugin
        if kind == "plugin"
        else json.loads(package.joinpath("marketplace.schema.json").read_text())
    )
    # The public authoring schema is stricter than the host reference.
    # Unknown metadata alone is not evidence that a package fails to load.
    schema["additionalProperties"] = True
    if kind == "marketplace":
        schema["$defs"].update(plugin["$defs"])
        entry = schema["$defs"]["pluginEntry"]
        entry["additionalProperties"] = True
        entry["properties"].update(plugin["properties"])
        entry["properties"]["source"] = {
            "oneOf": [
                {"type": "string", "minLength": 1},
                {
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string", "minLength": 1}},
                },
            ]
        }
        schema["properties"]["metadata"]["properties"].update(
            {key: {"type": "string"} for key in ("pluginRoot", "version")}
        )
    return Draft7Validator(schema, format_checker=FormatChecker())
