## Why

OpenClaw loads skill roots explicitly declared in its native manifest; an
undeclared `skills/` directory does not activate those skills. Ignored values,
missing directories and paths escaping the plugin prevent resources from loading.
Undeclared `skills/` directories are not reported.
An empty extension array suppresses conventional runtime entrypoint discovery.

## Activation

Opt-in with `--rule openclaw-resources` or `enabled: true`: source checkouts
may need dependencies installed or entrypoints built before checking resources.

## How to fix

Declare `skills` as an array of non-empty directory paths relative to the plugin
root. Each path may identify one skill directory or a directory containing several skills. Keep
resolved paths inside the package, including symlink targets.

Install dependencies before checking dependency-provided skill roots, or set
`check-skills-exist: false`. Set `check-entrypoints-exist: true` after building
to verify `package.json` runtime files too. The latter defaults to false because
compiled distribution files are often absent from a source checkout. Containment
checks remain active independently of both existence settings.

When `openclaw.runtimeExtensions` supplies a valid nonempty array corresponding
to `openclaw.extensions`, the existence check uses those explicit runtime files.
The source files may be absent from a built package. Both source and runtime
paths must remain inside the package, even with existence checking disabled.
Without an explicit mapping, the check continues to inspect `extensions`;
it does not infer compiled filenames.

See [manifest sources](openclaw-manifest-valid.md) for upstream contracts.
No autofix is offered: creating missing resources or rewriting declared paths
requires author intent.
