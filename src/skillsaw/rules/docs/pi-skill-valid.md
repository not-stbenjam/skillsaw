## Why

Pi loads directory-form `SKILL.md` files and flat Markdown skills. Its native
loader requires a nonempty description, but accepts missing names and names
that differ from their directory. Portable Agent Skills rules must not rewrite
valid native Pi metadata.

## How to fix

Add parseable frontmatter with a nonempty string `description`. A `name` is
optional. Pi derives the fallback name from the containing directory.

Native frontmatter follows Pi's YAML 1.2 core schema: unquoted `no` and
dates are strings, duplicate mapping keys are invalid, and YAML merge keys
(`<<`) do not supply a missing description. Flat-file selection uses the
same parser as directory skills.

Ordinary flat Markdown without a description is ignored, as Pi does, rather
than diagnosed as an invalid skill. An explicit `SKILL.md` without a description
is reported because its filename declares a skill that Pi will skip.

Native Pi skill bodies and descriptions receive the shared content and security
checks, and a skill directory's `references/` files are checked the same way
as in a portable skill, including the unreferenced-file check. Dual-format
packages retain the other host's portable skill checks for its own discovered
skills. This rule follows the loader pinned by
[pi-config-valid](pi-config-valid.md).
