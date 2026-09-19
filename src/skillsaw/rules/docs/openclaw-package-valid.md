## Why

OpenClaw reads runtime entrypoint metadata from `package.json`, separately from
its native manifest. A non-object `openclaw` or non-array `openclaw.extensions`
rejects entrypoint discovery. Every array item must be a non-empty string.
Missing or null `openclaw` metadata or extensions permit conventional index entrypoint fallback.

## Activation

Opt-in with `--rule openclaw-package-valid` or `enabled: true` while native
plugin coverage expands.

## How to fix

Use an object for `openclaw`, and an array of non-empty path strings for
`extensions` when declaring explicit entrypoints. `package.json` uses JSON,
while the native manifest also accepts JSON5. Keep package metadata within
the native loader’s 16 MiB limit. A package.json is not mandatory
for a native plugin with a conventional index entrypoint. No autofix is provided.

See [manifest sources](openclaw-manifest-valid.md) for the pinned loader source.
Runtime file existence is an optional check in
[openclaw-resources](openclaw-resources.md), because source checkouts often
have not built their distribution files.
