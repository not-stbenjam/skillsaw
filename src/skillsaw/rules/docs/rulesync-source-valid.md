# rulesync-source-valid

Checks conventional `.rulesync/rules/**/*.md` frontmatter and common
`rulesync.jsonc` field shapes against Rulesync 32.0.0. The check is opt-in and
does not attempt to validate every target or compiler feature.

## How to fix

Start rule files with YAML frontmatter delimited by `---`. Use booleans for
`root`, `localRoot`, and `cursor.alwaysApply`; arrays of strings for `targets`,
`globs`, and target-specific path lists; and a string for `description`.
Optional null frontmatter values are treated as absent, matching Rulesync.

Use a JSONC object for project configuration. Choose `inputRoot` or `inputRoots`,
and do not combine object-form `targets` or `features` with the other selection
field. Rulesync's own validation remains responsible for target/feature names,
per-target options, and frontmatter extensions outside the documented subset.

Generate explicitly, then lint the resulting native consumer files. Enable
`rulesync-generated: true` only when Rulesync owns the configured conventional
modular outputs. See the [generator workflow](https://skillsaw.org/generators/)
for exact copy-recognition limits and pinned compatibility evidence.
