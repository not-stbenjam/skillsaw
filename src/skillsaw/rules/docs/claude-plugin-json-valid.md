## Why

`plugin.json` is the plugin manifest — if it contains invalid JSON or
is missing required fields, the plugin cannot be loaded. The host
application uses this file to register the plugin's name, version,
and capabilities.

`name` is required. `description`, `version`, and `author` are recommended;
their absence produces warnings controlled by `recommended-fields`.
When present, `version` must be a string. Claude Code accepts release labels
such as `"release-candidate"` and calendar versions such as `"2026.10"`
as well as semantic versions.

## Examples

**Bad:**

```json
{"name": "my-plugin", "version": 2026}
```

**Good:**

```json
{
  "name": "my-plugin",
  "description": "Deployment automation plugin",
  "version": "1.0.0"
}
```

## How to fix

Fix the JSON syntax error or add the missing required fields
identified in the violation message. Write version values as JSON strings;
they do not need to follow semantic versioning. See the upstream
[manifest version reference](https://code.claude.com/docs/en/plugins-reference#version).
