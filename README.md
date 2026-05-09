[![PyPI version](https://badge.fury.io/py/skillsaw.svg)](https://badge.fury.io/py/skillsaw)
[![PyPI Downloads](https://img.shields.io/pypi/dm/skillsaw)](https://pypi.org/project/skillsaw/)
[![Tests](https://github.com/stbenjam/skillsaw/workflows/Tests/badge.svg)](https://github.com/stbenjam/skillsaw/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/stbenjam/skillsaw/branch/main/graph/badge.svg)](https://codecov.io/gh/stbenjam/skillsaw)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/skillsaw.svg)](https://pypi.org/project/skillsaw/)

<table><tr>
<td width="200" valign="top"><img src="https://raw.githubusercontent.com/stbenjam/skillsaw/main/images/logo.png" alt="skillsaw logo" width="200"></td>
<td valign="top">

### skillsaw

Keep your skills sharp. A configurable linter, scaffolding tool, doc generator, and CI companion for [agentskills.io](https://agentskills.io) skills, [Claude Code](https://docs.claude.com/en/docs/claude-code) [plugins](https://docs.claude.com/en/docs/claude-code/plugins), and [plugin marketplaces](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces).

> Formerly named `claudelint`. If you're migrating, see [Migrating from claudelint](#migrating-from-claudelint).

</td>
</tr></table>

## Features

- 🔍 **Context-Aware** — Automatically detects agentskills repos, single plugins, and marketplaces and enables the right rules
- 📐 **Rule-Based** — Enable/disable individual rules with configurable severity levels
- 🏗️ **Scaffolding** — Initialize marketplaces and add plugins, skills, commands, agents, and hooks with `skillsaw add`
- 📝 **Doc Generation** — Generate HTML or Markdown documentation for your plugins and skills with `skillsaw docs`
- 🔌 **Extensible** — Load custom rules from Python files
- ✅ **Comprehensive** — Validates skill format, plugin structure, metadata, command format, and cross-file consistency
- 🤖 **CI-Ready** — GitHub Action posts inline PR comments with automatic deduplication and thread resolution
- 🐳 **Containerized** — Run via Docker for consistent, isolated linting
- ⚡ **Fast** — Efficient validation with clear, actionable output

## Table of Contents

<!-- BEGIN GENERATED TOC -->

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Via uvx (easiest, no install required)](#via-uvx-easiest-no-install-required)
  - [Via pip](#via-pip)
  - [From source](#from-source)
  - [Using Docker](#using-docker)
  - [GitHub Action](#github-action)
- [Repository Types](#repository-types)
  - [agentskills.io Skills](#agentskillsio-skills)
  - [Single Plugin](#single-plugin)
  - [Marketplace (Multiple Plugins)](#marketplace-multiple-plugins)
- [Configuration](#configuration)
- [Builtin Rules](#builtin-rules)
- [Custom Rules](#custom-rules)
- [Scaffolding](#scaffolding)
  - [Initialize a Marketplace](#initialize-a-marketplace)
  - [Add Components](#add-components)
  - [Context Detection](#context-detection)
- [Documentation Generation](#documentation-generation)
- [Exit Codes](#exit-codes)
- [Example Output](#example-output)
- [Migrating from claudelint](#migrating-from-claudelint)
  - [Removed rules](#removed-rules)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [See Also](#see-also)
- [Support](#support)

<!-- END GENERATED TOC -->

## Quick Start

```bash
# Lint current directory (no install required)
uvx skillsaw

# Lint specific directory
skillsaw /path/to/skills

# Verbose output
skillsaw -v

# Strict mode (warnings as errors)
skillsaw --strict

# Generate default config
skillsaw init

# List all available rules
skillsaw list-rules

# Generate documentation
skillsaw docs

# Initialize a new marketplace
skillsaw add marketplace

# Add a plugin, skill, or hook
skillsaw add plugin my-plugin
skillsaw add skill my-skill
skillsaw add hook PreToolUse
```

## Installation

### Via uvx (easiest, no install required)

```bash
uvx skillsaw
uvx skillsaw /path/to/skills
```

### Via pip

```bash
pip install skillsaw
```

### From source

```bash
git clone https://github.com/stbenjam/skillsaw.git
cd skillsaw
pip install -e .
```

### Using Docker

```bash
docker pull ghcr.io/stbenjam/skillsaw:latest
docker run -v $(pwd):/workspace ghcr.io/stbenjam/skillsaw
```

### GitHub Action

The built-in GitHub Action installs skillsaw, runs it, and posts violations as
inline PR comments with automatic deduplication. Fixed violations have their
comment threads resolved.

```yaml
name: Lint

on: [pull_request]

permissions:
  contents: read
  pull-requests: write

jobs:
  skillsaw:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: stbenjam/skillsaw@v0
        with:
          strict: true
```

#### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `path` | Path to lint | `.` |
| `version` | Specific skillsaw version to install | latest |
| `strict` | Treat warnings as errors | `false` |
| `verbose` | Include info-level violations | `false` |
| `token` | GitHub token for posting PR comments | `${{ github.token }}` |

#### Outputs

| Output | Description |
|--------|-------------|
| `exit-code` | skillsaw exit code (0=pass, 1=errors, 2=strict+warnings) |
| `errors` | Number of errors found |
| `warnings` | Number of warnings found |
| `report` | Full JSON report |

#### PR comment behavior

- Each violation gets its own inline comment on the relevant line or file
- Comments are deduplicated across re-runs using content fingerprinting
- When a violation is fixed, its comment thread is automatically resolved
- Comments with human replies are preserved

> **Permissions:** `contents: read` is required for checkout.
> `pull-requests: write` is required for posting comments.

## Repository Types

skillsaw automatically detects your repository structure:

### agentskills.io Skills

Standalone skill repositories following the [agentskills.io](https://agentskills.io) specification:

```
my-skill/
├── SKILL.md              # Required: metadata + instructions
├── scripts/              # Optional: executable code
├── references/           # Optional: documentation
├── assets/               # Optional: templates, resources
├── evals/                # Optional: evaluation tests
│   └── evals.json
└── <any-dir>/            # Arbitrary directories allowed per spec
```

Skill collections (multiple skills in subdirectories) are also supported:

```
skills-repo/
├── skill-one/
│   └── SKILL.md
└── skill-two/
    └── SKILL.md
```

Standard discovery paths (`.claude/skills/`, `.github/skills/`, `.agents/skills/`) are checked automatically.

### Single Plugin

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   └── my-command.md
├── skills/
│   └── my-skill/
│       └── SKILL.md
└── README.md
```

### Marketplace (Multiple Plugins)

skillsaw supports multiple marketplace structures per the [Claude Code specification](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces):

#### Traditional Structure (plugins/ directory)
```
marketplace/
├── .claude-plugin/
│   └── marketplace.json
└── plugins/
    ├── plugin-one/
    │   ├── .claude-plugin/
    │   └── commands/
    └── plugin-two/
        ├── .claude-plugin/
        └── commands/
```

#### Flat Structure (root-level plugin)
```
marketplace/
├── .claude-plugin/
│   └── marketplace.json    # source: "./"
├── commands/
│   └── my-command.md
└── skills/
    └── my-skill/
```

#### Custom Paths and Mixed Structures

Plugins from `plugins/`, custom paths, and remote sources can coexist in one marketplace. Only local sources are validated.

## Configuration

Generate a default `.skillsaw.yaml` in your repository root:

```bash
skillsaw init
```

This creates a config file with all builtin rules, their defaults, and
descriptions. Edit it to enable, disable, or customize rules for your project.
See [`.skillsaw.yaml.example`](.skillsaw.yaml.example) for a complete example.

## Builtin Rules

<!-- BEGIN GENERATED RULES -->

### agentskills.io

These rules validate skills against the [agentskills.io specification](https://agentskills.io/specification). They auto-enable for agentskills repos, single plugins, and marketplaces whenever skills are detected.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `agentskill-valid` | SKILL.md must have valid frontmatter with name and description | error (auto) |
| `agentskill-name` | Skill name must be lowercase with hyphens and match directory name | error (auto) |
| `agentskill-description` | Skill description should be meaningful and within length limits | warning (auto) |
| `agentskill-structure` | Skill directories should only contain recognized subdirectories (stricter than spec) | warning (disabled) |
| `agentskill-evals` | Validate evals/evals.json format when present | error (auto) |
| `agentskill-evals-required` | Require evals/evals.json for each skill (opt-in) | error (disabled) |

**`agentskill-structure` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `allowed_dirs` | Directory names allowed in the skill root | `["assets", "evals", "references", "scripts"]` |

### Plugin Structure

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `plugin-json-required` | Plugin must have .claude-plugin/plugin.json | error (auto) |
| `plugin-json-valid` | Plugin.json must be valid JSON with required fields | error (auto) |
| `plugin-naming` | Plugin names should use kebab-case | warning (auto) |
| `plugin-readme` | Plugin should have a README.md file | warning (auto) |

**`plugin-json-valid` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `recommended-fields` | Fields that trigger a warning if missing from plugin.json | `["description", "version", "author"]` |

### Command Format

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `command-naming` | Command files should use kebab-case naming | warning |
| `command-frontmatter` | Command files must have valid frontmatter with description | error |
| `command-sections` | Command files should have Name, Synopsis, Description, and Implementation sections | warning |
| `command-name-format` | Command Name section should be 'plugin-name:command-name' | warning |

### Marketplace

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `marketplace-json-valid` | Marketplace.json must be valid JSON with required fields | error (auto) |
| `marketplace-registration` | Plugins must be registered in marketplace.json | error (auto) |

### Skills, Agents, Hooks

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `skill-frontmatter` | SKILL.md files should have frontmatter with name and description | warning |
| `agent-frontmatter` | Agent files must have valid frontmatter with name and description | error |
| `hooks-json-valid` | hooks.json must be valid JSON with proper hook configuration structure | error |

### MCP (Model Context Protocol)

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `mcp-valid-json` | MCP configuration must be valid JSON with proper mcpServers structure | error |
| `mcp-prohibited` | Plugins should not enable non-allowlisted MCP servers | error (disabled) |

**`mcp-prohibited` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `allowlist` | MCP server names that are permitted | `[]` |

### Rules Directory

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `rules-valid` | .claude/rules/ files must be markdown with valid optional paths frontmatter | error (auto) |

### Openclaw

Validates `metadata.openclaw` in SKILL.md frontmatter against the [openclaw spec](https://docs.openclaw.ai/tools/skills). Only fires when `metadata.openclaw` is present.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `openclaw-metadata` | Validate metadata.openclaw fields against the openclaw spec | warning (auto) |

### Instruction Files

Validates AI coding assistant instruction files (AGENTS.md, CLAUDE.md, GEMINI.md) at the repository root. Checks encoding, non-emptiness, and that `@import` references resolve to existing files. Disabled by default.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `instruction-file-valid` | Instruction files (AGENTS.md, CLAUDE.md, GEMINI.md) must be valid and non-empty | warning (disabled) |
| `instruction-imports-valid` | Import references (@path) in CLAUDE.md and GEMINI.md must point to existing files | warning (disabled) |

### AGENTS.md Deep Validation

Deep validation for AGENTS.md files (used by OpenAI Codex and GitHub Copilot coding agent). Checks size limits, override semantics, hierarchy consistency, dead references, weak language, structure quality, and more. Auto-enabled when AGENTS.md is detected.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `agents-md-structure` | AGENTS.md should have at least one heading and meaningful content | warning (disabled) |
| `agents-md-size-limit` | AGENTS.md must not exceed the Codex 32 KB size limit | warning (auto) |
| `agents-md-override-semantics` | AGENTS.override.md replaces AGENTS.md entirely — verify it is self-contained | warning (auto) |
| `agents-md-hierarchy-consistency` | Subdirectory AGENTS.md files should not contradict root AGENTS.md | warning (auto) |
| `agents-md-dead-file-refs` | File paths referenced in AGENTS.md should exist in the repo | warning (auto) |
| `agents-md-dead-command-refs` | Shell commands in AGENTS.md (npm scripts, make targets) should exist in the project | warning (auto) |
| `agents-md-weak-language` | AGENTS.md should use direct, actionable language instead of vague phrases | info (auto) |
| `agents-md-negative-only` | Negative instructions (never/don't) should include a positive alternative | warning (auto) |
| `agents-md-section-length` | AGENTS.md sections should not exceed 50 lines (lost-in-the-middle effect) | warning (auto) |
| `agents-md-structure-deep` | AGENTS.md should have task-organized structure with boundary sections | info (auto) |
| `agents-md-tautological` | Remove self-evident instructions like 'write clean code' that waste instruction budget | warning (auto) |
| `agents-md-critical-position` | Critical instructions (MUST/NEVER/ALWAYS) should be in the first or last 20% of the file | info (auto) |
| `agents-md-hook-candidate` | Deterministic rules in AGENTS.md should be implemented as hooks instead | info (auto) |

**`agents-md-size-limit` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `warn_bytes` | Byte count to warn at | `24576` |
| `error_bytes` | Byte count to error at | `32768` |

**`agents-md-section-length` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_lines` | Max lines per section | `50` |

**`agents-md-critical-position` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `zone_pct` | Percentage of file considered primacy/recency zone | `20` |

### Context Budget

Warns when instruction and configuration files exceed recommended token limits. Uses a `len(text) / 4` approximation for token counting. Supports per-category `warn` and `error` thresholds. Disabled by default.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `context-budget` | Warn when instruction or config files exceed recommended token limits | warning (disabled) |

**`context-budget` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `limits` | Token limits per file category (int for warn-only, or {warn, error} dict) | `{"agents-md": {"warn": 6000, "error": 12000}, "claude-md": {"warn": 6000, "error": 12000}, "gemini-md": {"warn": 6000, "error": 12000}, "skill": {"warn": 3000, "error": 6000}, "command": {"warn": 2000, "error": 4000}, "agent": {"warn": 2000, "error": 4000}, "rule": {"warn": 2000, "error": 4000}}` |

### Cursor Rules

Validates Cursor IDE `.cursor/rules/*.mdc` files (YAML frontmatter + Markdown content) and warns about the deprecated `.cursorrules` file. The monolithic rules (`cursor-mdc-valid`, `cursor-rules-deprecated`) are disabled by default. The 11 focused rules auto-enable when `.cursor/` is present and include autofixes for common issues.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `cursor-mdc-valid` | Cursor .mdc rule files must have valid frontmatter with known keys and correct types | error (disabled) |
| `cursor-rules-deprecated` | Legacy .cursorrules file is deprecated; migrate to .cursor/rules/*.mdc | warning (disabled) |
| `cursor-mdc-frontmatter` | Only 3 valid frontmatter fields: description, globs, alwaysApply | warning (auto) |
| `cursor-activation-type` | Warn when .mdc rule activation type is Manual (no frontmatter) | warning (auto) |
| `cursor-crlf-detection` | CRLF line endings break --- frontmatter detection in .mdc files | error (auto) |
| `cursor-glob-valid` | Validate glob patterns: catch invalid syntax and overly broad patterns | warning (auto) |
| `cursor-empty-body` | Rule file has frontmatter but empty body — the rule has no content | warning (auto) |
| `cursor-description-quality` | Agent-requested rules need clear descriptions (the agent's only signal) | warning (auto) |
| `cursor-glob-overlap` | Warn when multiple .mdc files have overlapping glob patterns | warning (auto) |
| `cursor-rule-size` | Warn when a rule file exceeds 500 lines (wastes context budget) | warning (auto) |
| `cursor-frontmatter-types` | alwaysApply must be boolean, globs must be string or list | error (auto) |
| `cursor-duplicate-rules` | Detect .mdc files with >80% similar bodies — suggest consolidation | warning (auto) |
| `cursor-always-apply-overuse` | Warn when >3 rules have alwaysApply: true (context budget) | warning (auto) |

**`cursor-rule-size` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max-lines` | Maximum lines before warning | `500` |

**`cursor-duplicate-rules` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `similarity-threshold` | Minimum similarity ratio (0-1) to flag as duplicate | `0.8` |

**`cursor-always-apply-overuse` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max-always-apply` | Maximum number of rules with alwaysApply: true before warning | `3` |

### Kiro Steering

Validates Kiro IDE `.kiro/steering/*.md` files (YAML frontmatter with inclusion modes, fileMatchPattern globs, and auto-mode metadata). Disabled by default.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `kiro-steering-valid` | Kiro steering files must have valid frontmatter with known inclusion mode and correct types | error (disabled) |

### Gemini

Validates GEMINI.md instruction files for the Gemini CLI. Checks `@import` resolution, circular imports, hierarchy consistency, dead file references, weak language, and instruction positioning. Auto-enabled when GEMINI.md is detected.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `gemini-import-valid` | Validate that @import targets in GEMINI.md resolve to existing files | warning (auto) |
| `gemini-import-circular` | Detect circular @import references in GEMINI.md files | error (auto) |
| `gemini-import-depth` | Warn when GEMINI.md import chains exceed depth 5 | warning (auto) |
| `gemini-scope-false-positive` | Detect @scope/package-name patterns that look like npm scoped packages, not imports | warning (auto) |
| `gemini-hierarchy-consistency` | Check subdirectory GEMINI.md files for contradictions with parent | warning (auto) |
| `gemini-size-limit` | Warn when GEMINI.md is too large | warning (auto) |
| `gemini-dead-file-refs` | Scan GEMINI.md for file path references to non-existent files | warning (auto) |
| `gemini-weak-language` | Detect weak or hedging language in GEMINI.md instructions | info (auto) |
| `gemini-tautological` | Detect tautological instructions that restate default AI behavior | info (auto) |
| `gemini-critical-position` | Check that critical instructions are positioned at the top of GEMINI.md | info (auto) |

**`gemini-size-limit` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `warn_lines` | Line count warning threshold | `150` |
| `error_lines` | Line count error threshold | `500` |

### Copilot Instructions

Validates GitHub Copilot instruction files: `.github/copilot-instructions.md` and `.instructions.md` files with YAML frontmatter `applyTo` glob patterns. Disabled by default.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `copilot-instructions-valid` | .github/copilot-instructions.md must be valid UTF-8 and non-empty | warning (disabled) |
| `copilot-dot-instructions-valid` | .instructions.md files must have valid YAML frontmatter with applyTo glob patterns | warning (disabled) |

### APM (Agent Package Manager)

Validates `apm.yml` manifests and related files for the Agent Package Manager ecosystem. Checks required fields, type validation, dependency structure, lockfile consistency, entry points, and naming conflicts. Auto-enabled when `apm.yml` is detected.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `apm-manifest-valid` | apm.yml must exist with required name and version fields | error (auto) |
| `apm-target-valid` | apm.yml target must use valid target values | error (auto) |
| `apm-type-valid` | apm.yml type must be a valid package type | error (auto) |
| `apm-dependencies-valid` | apm.yml dependencies must have valid apm and mcp entries | error (auto) |
| `apm-compilation-valid` | apm.yml compilation config must use valid values | warning (auto) |
| `apm-mcp-transport` | MCP server declarations must have valid transport configuration | error (auto) |
| `apm-lockfile-consistency` | apm.lock.yaml must be consistent with apm.yml dependencies | warning (auto) |
| `apm-readme-present` | APM packages should have a README.md | warning (auto) |
| `apm-entry-point` | Entry point file specified in main/entry must exist | error (auto) |
| `apm-name-conflict` | Package name should not conflict with well-known npm/pypi packages | warning (auto) |
| `apm-field-types` | YAML field value types must match the APM specification | error (auto) |
| `apm-deprecated-fields` | Flag deprecated or renamed fields in apm.yml | warning (auto) |

### Content Intelligence

Cross-format analysis rules that apply to all instruction files (CLAUDE.md, AGENTS.md, GEMINI.md, .cursorrules, etc.). Detect weak language, dead references, tautological instructions, buried critical directives, contradictions, embedded secrets, and cross-file inconsistencies. Disabled by default; enabled via `--init`.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `content-weak-language` | Detect hedging, vague, and non-actionable language in instruction files | warning (disabled) |
| `content-dead-references` | Detect broken file paths, npm scripts, and Makefile targets in instruction files | warning (disabled) |
| `content-tautological` | Detect tautological instructions that the model already follows by default | warning (disabled) |
| `content-critical-position` | Detect critical instructions in the middle of files where LLM attention is lowest | info (disabled) |
| `content-redundant-with-tooling` | Detect instructions that duplicate .editorconfig, ESLint, Prettier, or tsconfig settings | warning (disabled) |
| `content-instruction-budget` | Check if total instruction count across all files exceeds LLM instruction budget (~150) | warning (disabled) |
| `content-readme-overlap` | Detect instruction file sections that significantly overlap with README.md content | info (disabled) |
| `content-negative-only` | Detect prohibitions without a positive alternative (agent has no path forward) | warning (disabled) |
| `content-section-length` | Warn about markdown sections longer than 50 lines (optimal: 10-30 lines) | info (disabled) |
| `content-contradiction` | Detect likely contradictions within instruction files using keyword-pair heuristics | warning (disabled) |
| `content-hook-candidate` | Detect instructions that should be automated as hooks instead of prose instructions | info (disabled) |
| `content-actionability-score` | Score instruction files on actionability (verb density, commands, file references) | info (disabled) |
| `content-cognitive-chunks` | Check that instruction files are organized into cognitive chunks with headings | info (disabled) |
| `content-embedded-secrets` | Detect potential API keys, tokens, and passwords in instruction files | error (disabled) |
| `content-cross-file-consistency` | Check consistency across multiple instruction file formats (CLAUDE.md, AGENTS.md, .cursorrules, etc.) | warning (disabled) |

### Claude Code Deep Rules

Deep validation for Claude Code configuration: CLAUDE.md quality, hook migration candidates, skill quality, MCP security, plugin size budgets, rules overlap detection, agent delegation checks, and total context budget analysis. Auto-enabled when `.claude/` is detected.

| Rule ID | Description | Default Severity |
|---------|-------------|------------------|
| `claude-md-quality` | CLAUDE.md should contain clear, actionable instructions without weak language or tautologies | warning (auto) |
| `claude-md-hook-migration` | Detect instructions in CLAUDE.md that would be more reliable as hooks.json entries | info (auto) |
| `claude-skill-quality` | SKILL.md files should have a clear purpose, examples, and reasonable size | warning (auto) |
| `claude-mcp-security` | Check MCP server configurations for security issues | warning (auto) |
| `claude-plugin-size` | Warn when total plugin content exceeds reasonable context budget limits | warning (auto) |
| `claude-rules-overlap` | Check for overlapping path globs in .claude/rules/ frontmatter | warning (auto) |
| `claude-agent-delegation` | Check AGENTS.md for vague descriptions and missing tool/scope definitions | warning (auto) |
| `claude-context-budget-total` | Check total context budget across all Claude Code configuration files | warning (auto) |

**`claude-md-quality` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `min_length` | Minimum character length for CLAUDE.md body content | `50` |
| `max_weak_phrases` | Maximum number of weak/hedging phrases before warning | `5` |

**`claude-skill-quality` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_lines` | Maximum recommended lines for a single SKILL.md | `200` |

**`claude-plugin-size` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `warn_tokens` | Token count at which to warn | `8000` |
| `error_tokens` | Token count at which to error | `16000` |

**`claude-agent-delegation` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `min_description_words` | Minimum word count for agent descriptions | `5` |

**`claude-context-budget-total` parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `warn_total_tokens` | Total token count across all context files at which to warn | `8000` |
| `error_total_tokens` | Total token count across all context files at which to error | `16000` |

<!-- END GENERATED RULES -->

## Custom Rules

Create custom validation rules by extending the `Rule` base class:

```python
from pathlib import Path
from typing import List
from skillsaw import Rule, RuleViolation, Severity, RepositoryContext

class NoTodoCommentsRule(Rule):
    @property
    def rule_id(self) -> str:
        return "no-todo-comments"

    @property
    def description(self) -> str:
        return "Command files should not contain TODO comments"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for plugin_path in context.plugins:
            commands_dir = plugin_path / "commands"
            if not commands_dir.exists():
                continue
            for cmd_file in commands_dir.glob("*.md"):
                content = cmd_file.read_text()
                if "TODO" in content:
                    violations.append(
                        self.violation("Found TODO comment", file_path=cmd_file)
                    )
        return violations
```

Then reference it in `.skillsaw.yaml`:

```yaml
custom-rules:
  - ./my_custom_rules.py

rules:
  no-todo-comments:
    enabled: true
    severity: warning
```

## Scaffolding

`skillsaw add` scaffolds marketplaces, plugins, and components with best-practice structure, CI, and branding out of the box.

### Initialize a Marketplace

```bash
# Interactive (prompts for name, owner, colors)
skillsaw add marketplace

# Non-interactive
skillsaw add marketplace --name my-plugins --owner myuser --color-scheme ocean-blue
```

This creates the full marketplace structure: `marketplace.json`, `settings.json`, GitHub Pages site, GitHub Actions CI, Makefile, and an example plugin.

### Add Components

```bash
# Add a plugin to a marketplace
skillsaw add plugin my-plugin

# Add a skill, command, agent, or hook
skillsaw add skill my-skill
skillsaw add command greet
skillsaw add agent helper
skillsaw add hook PreToolUse
```

### Context Detection

skillsaw automatically detects your repo type and places files in the right location:

- **Marketplace** — components go under `plugins/<name>/`
- **Single-plugin repo** — components go in the repo root
- **`.claude/` repo** — components go under `.claude/`

In a marketplace with multiple plugins, specify `--plugin <name>` or skillsaw will prompt interactively.

## Documentation Generation

skillsaw can generate documentation for your plugins, skills, and marketplaces:

```bash
# Generate HTML docs (default)
skillsaw docs

# Generate Markdown
skillsaw docs --format markdown

# Write to a specific file
skillsaw docs --format markdown -o docs/README.md

# Write to a directory
skillsaw docs -o my-docs/

# Custom title
skillsaw docs --title "My Plugin Docs"
```

The generated documentation includes plugin metadata, command descriptions,
skill summaries, and configuration details extracted from your repository.

## Exit Codes

- `0` - Success (no errors, or warnings only in non-strict mode)
- `1` - Failure (errors found, or warnings in strict mode)

## Example Output

```
Linting: /path/to/skills-repo

Errors:
  ✗ ERROR [skills/my-skill/SKILL.md]: Name 'My Skill' must contain only lowercase letters, numbers, and hyphens
  ✗ ERROR [plugins/git/.claude-plugin/plugin.json]: Missing plugin.json

Warnings:
  ⚠ WARNING [skills/helper/SKILL.md]: Description exceeds 1024 characters (1087)
  ⚠ WARNING [plugins/utils]: Missing README.md (recommended)

Summary:
  Errors:   2
  Warnings: 2
```

## Migrating from claudelint

This project was renamed from `claudelint` to `skillsaw`. To migrate:

1. Update your package: `pip install skillsaw` (instead of `pip install claudelint`)
2. Rename `.claudelint.yaml` to `.skillsaw.yaml` (the old name is still discovered as a fallback)
3. Update CLI usage: `skillsaw` (instead of `claudelint`)
4. Update imports in custom rules: `from skillsaw import ...` (the old `from claudelint import ...` still works)

The `claudelint` command still works as a shim but prints a deprecation warning.

### Removed rules

The following rules from `claudelint` have been removed in `skillsaw`:

| Rule ID | Reason |
|---------|--------|
| `commands-dir-required` | Claude Code now treats `skills/` and `commands/` as the same mechanism; requiring a `commands/` directory is no longer meaningful |
| `commands-exist` | Same as above — plugins don't need to have commands |

If your `.skillsaw.yaml` references these rule IDs, `skillsaw` will emit a warning about the unknown rule.

## Development

```bash
# Run tests
pytest tests/ -v

# Format code
black src/ tests/

# Build Docker image
docker build -t skillsaw .
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## See Also

- [agentskills.io Specification](https://agentskills.io/specification)
- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [Claude Code Plugins Reference](https://docs.claude.com/en/docs/claude-code/plugins-reference)
- [AI Helpers Marketplace](https://github.com/openshift-eng/ai-helpers) - Example marketplace using skillsaw

## Support

- **Issues**: https://github.com/stbenjam/skillsaw/issues
- **Discussions**: https://github.com/stbenjam/skillsaw/discussions
