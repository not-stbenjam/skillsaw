# guard

Stops the agent from reading production secrets. Claude Code runs the hook in
`hooks/hooks.json` before every shell command and blocks any command that
touches the `prod/secrets` store.

Install it from the platform-guards marketplace. The hook script needs only a
POSIX shell and `grep`.
