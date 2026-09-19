## Why

OpenClaw loads skill roots explicitly declared in its native manifest; an
undeclared `skills/` directory does not activate those skills. Ignored values,
missing directories and paths escaping the package lose content at runtime.
An empty extension array suppresses conventional runtime entrypoint discovery.

## Activation

Opt-in with `--rule openclaw-resources` or `enabled: true`. Default severity is
warning. All findings honor severity overrides and report at file level.

## How to fix

Declare `skills` as an array of non-empty directory paths relative to the plugin
root. Both a skill directory and a collection of skills are supported. Keep
resolved paths inside the package, including symlink targets.

Install dependencies before checking dependency-provided skill roots, or set
`check-skills-exist: false`. Set `check-entrypoints-exist: true` after building
to verify `package.json` runtime files too. The latter defaults to false because
compiled distribution files are often absent from a source checkout. Containment
checks remain active independently of both existence settings.

See [manifest evidence](openclaw-manifest-valid.md) for upstream contracts.
No autofix is offered: creating missing resources or rewriting declared paths
requires author intent.
