# Pi packages and project resources

## Upstream sources

- [Package documentation](https://pi.dev/docs/latest/packages)
- [Pinned loader source](https://github.com/earendil-works/pi/tree/36b60d2e8985899743c4cf5bd5f8929832a3f05d/packages/coding-agent/src/core)
- [MCP configuration loader, v0.99.2](https://github.com/earendil-works/pi/blob/v0.99.2/packages/coding-agent/src/extensions/mcp/config.ts)
- [MCP field validator, v0.99.2](https://github.com/earendil-works/pi/blob/v0.99.2/packages/coding-agent/src/core/mcp-servers.ts)

Compare `pi-manifest.ts`, `package-manager.ts`, and `skills.ts` against the
pinned commit when updating support.

## Rules and discovery

The `pi-config-valid` rule checks resource arrays and local package selectors.
The `pi-skill-valid` rule validates native skill frontmatter and descriptions.
The opt-in `pi-resource-paths` rule checks assembled local paths.

Pi 0.99.0 introduced project `.pi/mcp.json`. It attaches as `PiMcpBlock`,
including nested projects, so shared credential and server policy checks run.
The opt-in `pi-mcp-valid` rule follows v0.99.2 field types and transport selection.
It remains opt-in pending the ten-repository accuracy survey.

MCP sync points: exposure names and the `codemode-deferred` alias; HTTP-first
selection when both command and URL are present; the unsupported SSE transport;
server namespace collisions after replacing hyphens with underscores; project
HTTP provider `auth` refusal; and OAuth field types and callback-port bounds.
The project `auth` guard also applies to stdio entries retaining any `url`
property and a JavaScript-truthy `auth` value.
The wrapper may be omitted, unknown fields are ignored, duplicate keys use the
last value, and empty commands pass field validation. Shared credentials include
`oauth.clientSecret`. Whole-value `!command` references are never executed and
still receive structured-token detection.

URI validation and OAuth callback URI semantics are deliberately deferred to
Pi's WHATWG parser. User configuration, MCP connections, and extension code
remain outside static discovery.
Namespace checks admit stdio and ordinary ASCII DNS HTTP URLs without callback
URIs; uncertain HTTP entries cannot reserve names and create false conflicts.

## Sync notes

Check resource field names, remote source prefixes, conventional directories,
and the order of inclusion, exclusion, exact inclusion and exact exclusion.
Manifest globs discover paths; project wildcards filter literal roots. Project
prompt and theme autoload is shallow. Pi prefixes nested ignore patterns with
the declaring directory and matches overrides against absolute paths too;
compare those loader details before adopting generic gitignore semantics.

Pi skill names are optional. Flat Markdown needs a description to be a skill.
Unselected portable skills retain Agent Skills validation. Pi-only packages
receive shared prose checks but do not acquire Claude hooks/settings semantics.
Extensions remain data-only targets and remote packages are not installed.

## Architecture

Pi combines a packaging claim with a project tool layer. Its marker is a
`package.json` key or keyword, discovered by the shared repository scan rather
than a marker directory. Resource selection uses the scan mixin;
selected native skills use `PiSkillBlock`, while unselected portable skills
keep their Agent Skills role. A selected `SKILL.md` sits in a `PiSkillNode`
with its `references/*.md` attached through the tree builder's
`add_skill_references` seam, so the support prose and
`agentskill-unreferenced-files` cover it as they cover a portable skill;
the container is not a `SkillNode`, which keeps the `agentskill-*`
authoring rules off Pi's dialect. Report formatters use `skill_paths` and
`skill_count` so flat native skills are included in single- and multi-path
reports. Add `.pi/skills` through Pi's resource selection, not through the
unfiltered conventional skill directory lists.
