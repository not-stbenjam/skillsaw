# Upgrading to 0.21

Skillsaw 0.21.0 adds native Cursor plugins and marketplaces, Pi packages and
projects, and OpenClaw plugins. Review these changes when updating from 0.20.0.

## Removed command and rules

`skillsaw docs` has been removed. Old invocations exit 2 without writing output.
To lint a directory named `docs`, run `skillsaw lint docs` or `skillsaw ./docs`.
The [rule reference](rules/index.md) and `skillsaw explain <rule-id>` remain
available; neither generates documentation for your repository.
`skillsaw add` remains deprecated but available.

Remove these retired rules from `.skillsaw.yaml`:

- `content-critical-position`
- `content-actionability-score`
- `skill-frontmatter` — use [`agentskill-valid`](rules/agentskill-valid.md)
  for portable Agent Skills frontmatter.

`skillsaw explain` and `--rule` explain a removed rule's status and exit 1.
`--skip-rule` warns and continues because the rule no longer runs. Other
unknown IDs passed to either selector are still errors.

Unknown or removed IDs in configuration produce advisory `unknown-rule`
warnings. They do not fail strict CI, affect grades or enter baselines.
Correct misspellings and remove obsolete entries to clear them. Unknown
options inside an existing rule still produce `invalid-config` findings and
follow your failure threshold. See [configuration](configuration.md#unknown-rules).

## New rule activation

Keeping `version: "0.20.0"` in `.skillsaw.yaml` defers newly introduced `auto`
rules. Set it to `"0.21.0"` when ready, or explicitly enable individual rules.
Existing checks can receive compatibility fixes regardless of that gate.

The following new checks require explicit opt-in, even after a version bump:

- [`openclaw-manifest-valid`](rules/openclaw-manifest-valid.md)
- [`openclaw-package-valid`](rules/openclaw-package-valid.md)
- [`openclaw-resources`](rules/openclaw-resources.md)
- [`pi-resource-paths`](rules/pi-resource-paths.md)

## Pi skill metadata

Upgrading the executable changes selected Pi skills to Pi's native metadata
contract independently of the configured rules version. Names are optional;
frontmatter must parse and include a nonempty description. Advance your
configuration version to `"0.21.0"` or explicitly enable
[`pi-skill-valid`](rules/pi-skill-valid.md) to validate those native skills.
Unselected portable skills keep Agent Skills validation.

`pi-skill-valid` reports at WARNING, where `agentskill-valid` reports at
ERROR, so metadata defects in Pi-owned skills that failed CI on 0.20.0 may now
pass. Set `severity: error` on `pi-skill-valid` to keep them blocking.

Pi discovery includes package resources, `.pi/` project resources, flat Markdown
skills, prompt templates and local package references. Resource selection,
plugin ownership and compatibility fixes can change the files being checked;
review findings before refreshing a baseline. See [repository types](repo-types.md).

## Reported repository type

The `repo_type` field in JSON and SARIF output reports the highest-priority
detected type, so the new types can replace the value 0.20.0 reported.
`cursor-marketplace`, `cursor-plugin`, `openclaw-plugin` and `pi-package` rank
above `agentskills`, and any new type, including `pi`, replaces `unknown`.
Update CI that matches on `repo_type`, or read the `repo_types` list instead.

## Hook checks

`hooks-dangerous` no longer flags hooks that run local scripts with Bun, such
as `bun run scripts/format.ts`. Downloading a script and running it with Bun is
still flagged.

## New dependencies

skillsaw now requires `wcmatch`, `pathspec` and `json5`. Pip installs them
automatically; update pinned lockfiles and distribution packages.
