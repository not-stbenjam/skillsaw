# agentskills.io (Agent Skills)

<!-- Repo-root-relative src/... and cross-reference paths below are intentionally kept as prose, not navigable links. -->
<!-- skillsaw-disable content-unlinked-internal-reference -->

## Upstream source(s)
- Spec (authoritative for prose): https://agentskills.io/specification
- GitHub source repo: https://github.com/agentskills/agentskills — "Specification and
  documentation for Agent Skills". The format originated as Anthropic's open standard;
  the original spec text also lives at
  https://github.com/anthropics/skills (`spec/agent-skills-spec.md`).
- Treat the agentskills.io page as authoritative for the published field list; use the
  GitHub repo to see wording changes and history.

## What to check
- New required/optional frontmatter fields in `SKILL.md` (currently: `name`, `description`,
  plus optional metadata).
- Changes to naming rules (allowed chars, length), `description` length limit
  (skillsaw defaults to the spec's 1024).
- Directory structure conventions (`scripts/`, `references/`, `assets/`).
- Evals format and whether evals are required.

## skillsaw rules that map
Package `src/skillsaw/rules/builtin/agentskills/`:
- `agentskill-valid` — `agentskills/valid.py`
- `agentskill-name` — `agentskills/name.py`
- `agentskill-description` — `agentskills/description.py`
- `agentskill-structure` — `agentskills/structure.py`
- `agentskill-evals` — `agentskills/evals.py`
- `agentskill-evals-required` — `agentskills/evals_required.py`
- `agentskill-unreferenced-files` — `agentskills/unreferenced_files.py`
- `agentskill-rename-refs` — `agentskills/rename_refs.py`

## Sync notes
- `description.py` hand-copies the 1024-char limit — re-check against the spec.
- `name.py` uses the Unicode-aware format predicate in `_helpers.py`; re-check
  allowed characters and length. The published spec permits Unicode lowercase
  alphanumerics, confirmed against `skills-ref` at revision
  `547831f3a23724ba64a9b79bbf59c5e0bc8f2d1a`. Preserve non-Latin names in
  validation and autofixes. The reference validator also normalizes NFKC and
  trims names; the published spec does not specify those transformations, so
  skillsaw retains literal directory matching.
- agentskills rules are disabled in `openshift-eng/ai-helpers` config; keep them
  backward-compatible (`enabled: auto`/`false`).
