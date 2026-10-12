## Why

Diagnoses the cumulative Codex project instruction byte limit for one supplied
repository root and working directory. This rule is **opt-in**: `AGENTS.md` is
shared by several hosts, and a static checkout cannot reveal a developer's
global Codex settings or trust decision.

Two 18 KiB files at the root and in a child directory are individually below
the generic `context-budget` warning threshold. With Codex's default 32 KiB
project cap, the child contributes only 14 KiB. This rule reports cumulative
byte loss; `context-budget` estimates tokens per file.

## Usage

```sh
# The path is the project root; --cwd is relative to that root.
skillsaw tree /path/to/repo --codex-instructions --cwd services/payments
skillsaw tree /path/to/repo --codex-instructions --cwd services/payments --format json

# Inspect at the supplied root with assumed defaults and in-scope project config.
skillsaw lint /path/to/repo --rule codex-project-instructions --strict
```

For a repeatable CI check, configure the projection in `.skillsaw.yaml`:

```yaml
codex-instructions:
  cwd: services/payments
  # Optional explicit effective settings, for example from your Codex CLI/profile:
  project_doc_max_bytes: 65536
  project_doc_fallback_filenames: [TEAM_GUIDE.md, .agents.md]
rules:
  codex-project-instructions:
    enabled: true
    severity: warning
```

`codex-instructions` is a shared analysis input for lint and tree inspection,
separate from rule enablement. It makes selected fallback files part of the
typed content tree before content checks run. The two `project_doc_*` settings
are optional; omit them or use `null` to read the in-scope project settings and
then assume Codex defaults. An explicit empty fallback list disables fallbacks
in the projection, and a byte limit of zero models disabled project loading.
`cwd: null` means the supplied root. `tree --cwd` overrides the configured cwd.
These inputs do **not** modify Codex configuration.

## Selection model

The model follows the released
[Codex 0.162.1 loader](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/core/src/agents_md.rs)
and [configuration conversion](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/core/src/config/mod.rs),
verified with the installed `codex-cli 0.162.1` `debug prompt-input` command.
The [official guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
documents the 32 KiB default and precedence; the released source resolves the
empty-file and byte-boundary details.

1. Treat the supplied path as the project root, resolve cwd inside it, and
   visit only the directories on that root-to-cwd chain, inclusively. Siblings,
   deeper directories, and ancestors above the supplied root cannot contribute.
2. Assuming the project is trusted, merge the two supported settings from each
   `.codex/config.toml` on the chain. The closest layer wins; fallback arrays
   replace earlier arrays. Explicit skillsaw analysis inputs win last. The
   resulting fallback order applies to **every** directory, including ancestors.
3. In each directory select the first regular file: `AGENTS.override.md`, then
   `AGENTS.md`, then configured fallbacks in order. There is at most one
   selection per directory. Fallbacks are trimmed and deduplicated. Path syntax
   is ignored before probing, using the local OS convention: `/`, NUL, `.` and
   `..` are rejected everywhere, plus `\` and `:` on Windows.
4. Selection precedes reading. An empty or whitespace-only override shadows the
   standard file and fallbacks. Its empty content is dropped **without trying
   the next name**. Directories named like candidates are skipped. In-scope
   symlinks are supported; the same target selected at two directory levels
   consumes bytes twice, while its content checks run once.
5. Load selected files in root-to-cwd order. Read at most the remaining **raw
   bytes**, then decode that prefix as lossy UTF-8. Invalid or split sequences
   become replacement characters. BOM and CRLF bytes count. If the decoded
   prefix contains only Unicode whitespace, drop it without spending the
   budget. Otherwise debit the raw prefix length. At zero remaining bytes,
   later selections are omitted. A zero configured limit omits every selection.
6. Join included project entries with `\n\n`. These separators, UTF-8
   replacement expansion, user/global instructions, and prompt wrappers do not
   consume the project-file cap. Rendered project text can exceed the cap for
   those reasons. The report distinguishes raw file size, bytes read, bytes
   charged, cumulative bytes, and rendered project bytes.

The selection view lists candidates even when a zero or exhausted budget means
Codex would stop before loading them. Status `empty` refers to the **read
prefix**; `truncated: true` still records a discarded suffix. JSON `complete`
means the local projection was computable under its stated assumptions, not
that skillsaw observed a running Codex session.

## How to fix

One consolidated warning identifies truncated or omitted files for the chosen
cwd. Reduce the selected ancestor chain or raise `project_doc_max_bytes` in the
Codex configuration actually used by the developer. Splitting a large file
between ancestors on the **same** chain does not avoid the cumulative cap.

Inspection exits zero for a complete model, including one that diagnoses lost
content. Use the lint rule with `--strict` or `--fail-on warning` for CI failure.
Inspection exits one for incomplete local evidence; the rule reports that
uncertainty instead of asserting an exact truncation result. There is no autofix.

## Limits

Global, managed, profile, and CLI Codex settings and global/user instructions
are **never read**. Pass effective values explicitly when they differ from the
assumed defaults. The analysis assumes one trusted local environment: the
released loader skips project instructions entirely for an untrusted project.
Multi-environment budget sharing, automatic root-marker discovery, remote
executor path conventions, and runtime trust/profile resolution are deferred.
Without a root marker Codex normally considers only cwd; supply cwd itself as
skillsaw's root to model that case. A nested Git repository may similarly need
a different explicit root.

skillsaw honors its authoring scope, including excluded directories and
`lint-external-content: false`. Excluded, unreadable, unresolved, or
out-of-root instruction/config paths make the projection incomplete and never
cause silent selection of a lower-precedence file. Existing structured parser
roles remain configuration, even if explicitly named as a fallback; novel
fallback files become instruction prose. `AGENTS.override.md` is discovered
for content checks without opting into this diagnostic. Arbitrary fallback
discovery is limited to the requested projection. Other hosts' files contribute
only when explicitly named as Codex fallbacks.

The analysis and its finding are attached to the supplied root. A cwd excluded
by these policies remains an incomplete analysis; excluding that directory
does not silently suppress the requested CI check.
