# Pi packages and project resources

## Upstream sources

- [Package documentation](https://pi.dev/docs/latest/packages)
- [Pinned loader source](https://github.com/earendil-works/pi/tree/36b60d2e8985899743c4cf5bd5f8929832a3f05d/packages/coding-agent/src/core)

Compare `pi-manifest.ts`, `package-manager.ts`, and `skills.ts` against the
pinned commit when updating support.

## Rules and discovery

The `pi-config-valid` rule checks resource arrays and local package selectors.
The `pi-skill-valid` rule validates native skill frontmatter and descriptions.
The opt-in `pi-resource-paths` rule checks assembled local paths.

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
keep their Agent Skills role. Report formatters use `skill_paths` and
`skill_count` so flat native skills are included in single- and multi-path
reports. Add `.pi/skills` through Pi's resource selection, not through the
unfiltered conventional skill directory lists.
