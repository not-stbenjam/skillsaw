## Why

A Claude plugin must have a `.claude-plugin/plugin.json` manifest so
the host application can discover its metadata, commands, and
capabilities. Without this file the plugin directory is just a
collection of unregistered files. The requirement is scoped to
directories with Claude provenance.

A `.claude-plugin/marketplace.json` catalog alone does not declare its
parent directory a Claude plugin. A root Codex plugin may host that catalog
without needing a Claude manifest. An actual Claude manifest, an empty
`.claude-plugin/` marker, or an explicit local entry in the Claude catalog
still declares a Claude plugin.

## Examples

**Bad:**

```
my-plugin/
  .claude-plugin/
    commands/
      deploy.md
```

**Good:**

```
my-plugin/
  .claude-plugin/
    plugin.json
    commands/
      deploy.md
```

## How to fix

Create a `.claude-plugin/plugin.json` file with the required fields
(`name`, `description`, `version`). Put commands, agents, skills, and other
plugin content beside the `.claude-plugin/` directory.
