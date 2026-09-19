## Why

Cursor native plugins use `.cursor-plugin/plugin.json`. Invalid metadata or
component paths can leave a plugin unloaded or silently omit its content.
This rule validates the native manifest and checks explicit component paths
against the containing package. Marketplace entry metadata is merged with
plugin metadata, with the plugin manifest taking precedence.

Explicit `rules`, `agents`, `commands`, `skills`, `hooks`, and `mcpServers`
fields replace their default discovery locations. Paths and globs must stay
inside the plugin. Inline hooks and MCP configurations are attached to the
lint tree for the existing format, security, and policy checks.

## How to fix

Correct the field named in the finding. Use relative paths within the
plugin, or remove a component override to restore default discovery. JSON
findings are reported at file level. There is no automatic fix.

The [Cursor plugin reference](https://cursor.com/docs/reference/plugins)
defines the supported components. Portable root `plugin.json` packages
continue to use the Agent Plugins rules.
