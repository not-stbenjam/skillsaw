# Ruler and Rulesync sources and outputs

skillsaw discovers local generator sources and checks existing generated files
with the rules for their consumers. Run the generator yourself or in CI;
`skillsaw lint`, `fix`, and `tree` never invoke it.

## Authored sources

- **Ruler:** `.ruler/**/*.md` are instruction prose, including any apparent YAML
  frontmatter. `.ruler/ruler.toml` is structured configuration. The recursive
  rule walk excludes the separately propagated top-level `skills/` and `agents/`
  trees. A package's nested `.ruler/` is discovered too, independently of whether
  a particular Ruler invocation enables nested generation.
- **Rulesync:** `.rulesync/rules/**/*.md` are frontmattered instruction sources.
  The body and `description` receive content checks; targeting metadata remains
  configuration. `rulesync.jsonc` beside `.rulesync/` is parsed as JSONC, including
  comments and trailing commas. Nested project directories are discovered.

Description findings point to the YAML field's key line, including folded
strings. Descriptions inherited through YAML merges have file-level locations.
Decoded descriptions are diagnostic-only because their Markdown spans
do not map directly to the YAML file for safe autofix.

Sources get the `instruction` budget role, rather than the generic `extra`
role of `content-paths`. This describes authored rules, not which files an agent
will load in a particular session. Ordinary exclusions apply to discovery.
Symlink files must resolve inside the source tree; directory symlinks are not
followed. Home configuration and remote sources are never loaded.

The following optional checks use pinned release contracts:

```yaml
rules:
  ruler-config-valid:
    enabled: true
  rulesync-source-valid:
    enabled: true
```

`ruler-config-valid` checks the TOML configuration shape from Ruler 0.3.44,
including its strict configuration keys, heterogeneous `agents` table, and MCP
server tables. It does not validate a universal agent/model registry or server
runtime behavior.

`rulesync-source-valid` checks conventional YAML rule frontmatter and the common
fields `root`, `localRoot`, `targets`, `description`, `globs`, `claudecode.paths`,
`cursor`, and `agentsmd.subprojectPath`. It checks JSONC syntax, common configuration
field shapes, and the `inputRoot`/`inputRoots` and object-form `targets`/`features`
exclusions. It removes null optional frontmatter fields and null entries in
the supported arrays, as Rulesync does. Rulesync itself remains responsible for
target/feature names, per-target
configuration, other frontmatter extensions, and full compiler validation.
These checks are opt-in because their scope and release pins are narrower than
the generators' evolving interfaces.

## Copy recognition and attribution

Existing consumer discovery still owns generated output files. A recognized
copy keeps its typed consumer node and structural, security, policy, reference,
and size checks. Only a fixed set of editorial checks, such as weak language
and repeated directives, is suppressed on verified copies. Source findings
keep the authored file and line. APM's existing generated-context handling is
unchanged.

For **Ruler**, recognition is automatic for conventional project `AGENTS.md`
and `CLAUDE.md` outputs. It requires Ruler's source comments, the `AGENTS.md`
generation stamp where applicable, discovered local sources, and an exact
match to the concatenation. A marker alone does not confer ownership.

**Rulesync** writes modular rules without an ownership stamp. To assert that
Rulesync owns its configured modular outputs, add this to `.skillsaw.yaml`:

```yaml
rulesync-generated: true
```

With that assertion, skillsaw recognizes non-root, non-local rule copies under
`.claude/rules/**/*.md` and `.cursor/rules/**/*.mdc`. It verifies the conventional
relative filename, configured target and `rules` feature, source targeting,
copied body, and emitted frontmatter. The body comparison allows the generator's
outer-whitespace normalization. The default is `false`: a matching filename or
matching prose alone never makes an unstamped, user-managed file generated.
Files outside those destinations remain fully checked. Edited or stale copies
that fail verification receive all checks too. Symlinked outputs are never
recognized as generated copies, so ownership cannot suppress another file's
authored findings.

Rulesync copy recognition supports array-form `targets` and `features`, the
default input tree, and the project output root (`outputRoots: ["."]` or omitted).
It stands down for custom roots, global mode, object-form selections, and local
config/source overlays. Rulesync root files, folded rules, and its fetched
`.curated` tree are outside this first increment. Those generated consumer
files are still linted when their native locations are supported by skillsaw.

`skillsaw tree` labels recognized copies with their source paths. JSON output
findings on these files add `generator` and `generated_from`; the finding's
location remains the output location. There is no exact source-line map for
transformed output or MCP configuration, so skillsaw does not remap those
findings to guessed source lines. Matching copies are diagnostic-only for
autofix: edit the source or generator settings, generate again, then re-lint.

## Author → generate → lint

For Ruler, author Markdown in `.ruler/` and select consumers in
`.ruler/ruler.toml`:

```toml
default_agents = ["claude", "codex"]
[gitignore]
enabled = false
```

Run from the project directory:

```sh
npx --yes @intellectronica/ruler@0.3.44 apply --local-only
skillsaw lint . --strict -v
skillsaw tree .
```

For Rulesync, author `.rulesync/rules/backend/api.md`:

```markdown
---
root: false
targets: [claudecode, cursor]
description: HTTP service development
globs: ["src/**/*.ts"]
---
# HTTP API

Return a stable error code when a reservation cannot be fulfilled.
```

Select the outputs in `rulesync.jsonc`:

```jsonc
{
  "targets": ["claudecode", "cursor"],
  "features": ["rules"],
  "outputRoots": ["."]
}
```

Enable `rulesync-generated` and the optional source check in `.skillsaw.yaml`,
then run:

```sh
npx --yes rulesync@32.0.0 generate
skillsaw lint . --strict -v
skillsaw tree .
```

Use the same explicit sequence in CI. Generation failures stop the job;
successful generation does not imply valid consumer output. For example,
Ruler 0.3.44's emitted Codex HTTP MCP `headers` spelling is diagnosed by the
existing `codex-mcp-headers` check. No duplicate generator-specific header rule
is needed. Model aliases are left to the consumer's supported contracts;
skillsaw does not infer a cross-provider model registry from a generator bug.

## Compatibility evidence and fixtures

This increment was verified against the released npm CLIs, using Node 22.23.1:

- [Ruler v0.3.44](https://github.com/intellectronica/ruler/releases/tag/v0.3.44),
  commit `658d1bc168e3496015aa5c262361cce818fabcf9`:
  [recursive rule loading](https://github.com/intellectronica/ruler/blob/658d1bc168e3496015aa5c262361cce818fabcf9/src/core/FileSystemUtils.ts),
  [configuration schema](https://github.com/intellectronica/ruler/blob/658d1bc168e3496015aa5c262361cce818fabcf9/src/core/ConfigLoader.ts),
  [source comments and concatenation](https://github.com/intellectronica/ruler/blob/658d1bc168e3496015aa5c262361cce818fabcf9/src/core/RuleProcessor.ts).
- [Rulesync v32.0.0](https://github.com/dyoshikawa/rulesync/releases/tag/v32.0.0),
  commit `01118a908541f1f65fbbedcf7864f4c1173d8994`:
  [file formats](https://github.com/dyoshikawa/rulesync/blob/01118a908541f1f65fbbedcf7864f4c1173d8994/docs/reference/file-formats.md),
  [rule schema](https://github.com/dyoshikawa/rulesync/blob/01118a908541f1f65fbbedcf7864f4c1173d8994/src/features/rules/rulesync-rule.ts),
  [configuration schema](https://github.com/dyoshikawa/rulesync/blob/01118a908541f1f65fbbedcf7864f4c1173d8994/src/config/config.ts),
  [Claude output](https://github.com/dyoshikawa/rulesync/blob/01118a908541f1f65fbbedcf7864f4c1173d8994/src/features/rules/claudecode-rule.ts),
  [Cursor output](https://github.com/dyoshikawa/rulesync/blob/01118a908541f1f65fbbedcf7864f4c1173d8994/src/features/rules/cursor-rule.ts).

The source and emitted snapshots in `tests/fixtures/generators/ruler/` and
`tests/fixtures/generators/rulesync/` were produced by those CLIs. Their README
records reproduction commands and package integrity hashes. Tests consume the
committed snapshots without installing or executing generators. They include
intentional weak prose, a generated Cursor manual rule, and Ruler's Codex header
issue so both authored and output diagnostics remain exercised.

Custom compiler targets, skills/subagent propagation, global settings, complete
schema coverage for Rulesync, source maps, translation equivalence, and effective
Codex instruction selection are intentionally deferred.
