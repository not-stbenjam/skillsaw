# Design: LLM-as-Judge Autofix Engine

**Bead:** hq-9hk
**Status:** Design proposal
**Date:** 2026-05-09

## 1. Module Structure

```
src/skillsaw/llm/
├── __init__.py          # Public API: LLMEngine, LLMTool, LLMFixResult
├── engine.py            # LLMEngine — conversation loop, tool dispatch, retries
├── tools.py             # Built-in tool definitions (read_file, write_file, etc.)
├── config.py            # LLMConfig — model selection, budget, iteration caps
└── _litellm.py          # LiteLLM wrapper — isolates the dependency behind a seam
```

The `_litellm.py` module is the only file that imports `litellm`. Everything
else talks to it through a `CompletionProvider` protocol, making the engine
testable without real API calls.

## 2. Key Interfaces

### 2.1 CompletionProvider (LiteLLM abstraction)

```python
from typing import Protocol, List, Dict, Any, Iterator

class CompletionProvider(Protocol):
    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
    ) -> "CompletionResult": ...

@dataclass
class CompletionResult:
    content: str | None
    tool_calls: List[ToolCall]
    usage: TokenUsage

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
```

The production implementation (`LiteLLMProvider` in `_litellm.py`) delegates to
`litellm.completion()`. Tests inject a `FakeProvider` that returns canned
responses.

### 2.2 LLMTool (tool protocol)

```python
from typing import Protocol, Dict, Any

class LLMTool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema for tool parameters."""
        ...

    def execute(self, **kwargs) -> str:
        """Run the tool and return a string result for the LLM."""
        ...
```

### 2.3 Built-in Tools

Defined in `tools.py`, scoped to a working directory:

| Tool | Purpose |
|------|---------|
| `read_file(path)` | Read full file contents |
| `write_file(path, content)` | Overwrite a file |
| `read_section(path, start_line, end_line)` | Read a line range |
| `replace_section(path, old_text, new_text)` | Surgical string replacement |

All paths are resolved relative to a sandbox root and validated to prevent
path traversal. Tools operate on real files — the engine is a side-effecting
loop, not a pure function.

```python
class ReadFileTool:
    name = "read_file"
    description = "Read the contents of a file"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to repo root"}
        },
        "required": ["path"],
    }

    def __init__(self, root: Path):
        self._root = root

    def execute(self, *, path: str) -> str:
        resolved = (self._root / path).resolve()
        if not resolved.is_relative_to(self._root):
            return "Error: path escapes repository root"
        if not resolved.exists():
            return f"Error: file not found: {path}"
        return resolved.read_text(encoding="utf-8")
```

### 2.4 LLMEngine

The engine manages a message-based conversation loop with tool use:

```python
@dataclass
class LLMConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    max_iterations: int = 5
    max_total_tokens: int = 500_000  # cost ceiling

class LLMEngine:
    def __init__(
        self,
        provider: CompletionProvider,
        tools: List[LLMTool],
        config: LLMConfig | None = None,
    ):
        self._provider = provider
        self._tools = {t.name: t for t in tools}
        self._config = config or LLMConfig()
        self._messages: List[Dict[str, Any]] = []
        self._total_usage = TokenUsage(0, 0)

    def run(self, system_prompt: str, user_message: str) -> LLMResult:
        """
        Run a single conversation to completion (until the LLM stops
        calling tools or budget is exhausted).

        Returns an LLMResult with the final text response, total token
        usage, and tool call log.
        """
        ...

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        """Convert tools to OpenAI-format tool definitions."""
        ...

    def _dispatch_tool(self, call: ToolCall) -> str:
        """Look up and execute a tool call, returning the result string."""
        ...
```

The `run()` loop:
1. Send messages + tool schemas to the provider
2. If response has tool_calls, execute each tool, append results as tool messages
3. Repeat until: no tool calls, or iteration/token budget exhausted
4. Return final text + usage stats

### 2.5 LLMResult

```python
@dataclass
class LLMResult:
    text: str | None
    usage: TokenUsage
    tool_calls: List[ToolCallRecord]
    iterations: int
    budget_exhausted: bool

@dataclass
class ToolCallRecord:
    name: str
    arguments: Dict[str, Any]
    result: str
```

## 3. Autofix Integration

### 3.1 New AutofixConfidence Level

Add `LLM` to the existing enum:

```python
class AutofixConfidence(Enum):
    SAFE = "safe"        # Deterministic, always correct
    SUGGEST = "suggest"  # Probably correct, review recommended
    LLM = "llm"         # LLM-generated, requires --llm flag and user confirmation
```

### 3.2 Rule Integration: `llm_fix_prompt`

Rules opt into LLM-powered fixing by defining an `llm_fix_prompt` property:

```python
class ContentWeakLanguageRule(Rule):
    @property
    def llm_fix_prompt(self) -> str | None:
        return """You are a technical writing assistant fixing AI coding assistant
instruction files. Your job is to replace weak, hedging language with direct,
actionable instructions.

Rules:
- Replace "try to X" with "X"
- Replace "consider doing X" with "do X" or remove the line
- Replace "if possible" with explicit conditions
- Replace vague adverbs (properly, correctly, appropriately) with specific behavior
- Do NOT change the meaning or intent of the instruction
- Do NOT add new instructions
- Preserve markdown formatting
"""
```

Rules without `llm_fix_prompt` (the default `None`) are skipped during
LLM autofix. The prompt is rule-specific guidance — the engine provides the
file content and violation list as structured context.

### 3.3 The Fix Loop

The LLM autofix loop lives in the `Linter`, not the engine:

```python
# In linter.py
def llm_fix(
    self,
    engine: LLMEngine,
    max_iterations: int = 3,
    callback: Callable[[int, int, List[RuleViolation]], None] | None = None,
) -> LLMFixResult:
    """
    Run the lint-fix-relint loop using an LLM engine.

    1. Run lint, collect violations from rules that have llm_fix_prompt
    2. Group violations by file
    3. For each file: give the LLM the content + violations + rule prompts
    4. LLM uses tools to edit the file
    5. Re-lint the file
    6. Repeat until clean or max_iterations
    """
    ...
```

The system prompt sent to the LLM per-file:

```
You are fixing lint violations in the file {path}.

{combined_rule_prompts}

Current violations:
{formatted_violations}

Use the read_file and replace_section tools to fix these violations.
Do not change anything unrelated to the violations listed above.
When done, respond with a summary of changes made.
```

### 3.4 LLMFixResult

```python
@dataclass
class LLMFixResult:
    files_modified: List[Path]
    violations_before: int
    violations_after: int
    iterations_used: int
    total_usage: TokenUsage
    diffs: Dict[Path, str]  # unified diff per file
    success: bool  # True if violations_after < violations_before
```

## 4. CLI UX Flow

### 4.1 New CLI Flag

```
skillsaw fix --llm [--model MODEL] [--max-iterations N] [--yes]
```

- `--llm` / `--ai`: Enable LLM-powered fixes (required — never runs implicitly)
- `--model MODEL`: Override model (default: from config or `claude-sonnet-4-20250514`)
- `--max-iterations N`: Cap fix iterations (default: 3)
- `--yes` / `-y`: Auto-apply without confirmation prompt

### 4.2 User-Facing Output

```
$ skillsaw fix --llm

Linting: /path/to/repo

Found 5 LLM-fixable violations across 2 files

Iteration 1/3:
  ✎ CLAUDE.md — fixing 3 violations (weak-language, tautological)
  ✎ .cursor/rules/testing.mdc — fixing 2 violations (negative-only)
  ⟳ Re-linting...
  ✓ 4 violations resolved, 1 remaining

Iteration 2/3:
  ✎ .cursor/rules/testing.mdc — fixing 1 violation (negative-only)
  ⟳ Re-linting...
  ✓ All violations resolved

── Changes ────────────────────────────────────────

--- CLAUDE.md (before)
+++ CLAUDE.md (after)
@@ -12,3 +12,3 @@
-Try to use descriptive variable names where possible.
+Use descriptive variable names that reflect the value's purpose.

--- .cursor/rules/testing.mdc (before)
+++ .cursor/rules/testing.mdc (after)
@@ -5,3 +5,3 @@
-Don't use mocks for database tests.
+Use real database connections for integration tests.

Token usage: ~2,400 tokens (prompt: 1,800 / completion: 600)

Apply these changes? [y/N]
```

### 4.3 Error/Degrade Scenarios

| Scenario | Behavior |
|----------|----------|
| No API key configured | Error: "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or configure model in .skillsaw.yaml" |
| LLM makes violations worse | Revert file to pre-iteration state, report "LLM fix degraded file, reverting" |
| Budget exhausted mid-fix | Stop, show partial results, report remaining violations |
| LiteLLM not installed | Error: "Install litellm: pip install skillsaw[llm]" with clean exit |
| Rate limit / API error | Retry with exponential backoff (3 attempts), then fail gracefully |

## 5. Configuration Schema

### 5.1 `.skillsaw.yaml` additions

```yaml
# LLM-powered autofix settings
llm:
  model: "claude-sonnet-4-20250514"  # Any LiteLLM-supported model string
  max_iterations: 3                   # Per-file fix loop cap
  max_tokens: 500000                  # Total token budget per run
  confirm: true                       # Prompt before applying (--yes overrides)
```

### 5.2 Environment Variables

| Variable | Purpose |
|----------|---------|
| `SKILLSAW_MODEL` | Override model (highest priority) |
| `ANTHROPIC_API_KEY` | API key for Anthropic models |
| `OPENAI_API_KEY` | API key for OpenAI models |
| (LiteLLM-supported vars) | LiteLLM handles routing per model prefix |

### 5.3 LinterConfig Integration

```python
@dataclass
class LLMSettings:
    model: str = "claude-sonnet-4-20250514"
    max_iterations: int = 3
    max_tokens: int = 500_000
    confirm: bool = True

@dataclass
class LinterConfig:
    # ... existing fields ...
    llm: LLMSettings = field(default_factory=LLMSettings)
```

Loaded from the `llm:` key in `.skillsaw.yaml`. The `SKILLSAW_MODEL` env var
overrides `llm.model`.

## 6. Dependency Strategy

LiteLLM is an **optional dependency** via extras:

```toml
[project.optional-dependencies]
llm = ["litellm>=1.40"]
dev = [
    # ... existing dev deps ...
    "litellm>=1.40",  # Also in dev for testing
]
```

The `_litellm.py` module does a lazy import:

```python
def _get_litellm():
    try:
        import litellm
        return litellm
    except ImportError:
        raise ImportError(
            "LLM features require litellm. Install with: pip install skillsaw[llm]"
        )
```

Users install with `pip install skillsaw[llm]`. The base `skillsaw` package
remains dependency-light (only PyYAML).

## 7. Test Strategy

### 7.1 Unit Tests (no API calls)

**FakeProvider:** A `CompletionProvider` that returns scripted responses:

```python
class FakeProvider:
    def __init__(self, responses: List[CompletionResult]):
        self._responses = iter(responses)

    def complete(self, messages, tools, model, max_tokens=4096):
        return next(self._responses)
```

Test cases:
- **Engine conversation loop:** Verify tool dispatch, message accumulation,
  iteration capping, budget enforcement
- **Tool execution:** Path traversal prevention, file read/write correctness,
  replace_section edge cases (no match, multiple matches)
- **Config loading:** YAML parsing, env var override, default fallback
- **Integration with Rule:** Verify `llm_fix_prompt` plumbing, violation
  grouping, re-lint loop
- **Error handling:** Provider exceptions, malformed tool calls, budget exhaust

### 7.2 Integration Tests (optional, gated)

Gated behind `SKILLSAW_LLM_TEST=1` env var (never in CI):

```python
@pytest.mark.skipunless(os.environ.get("SKILLSAW_LLM_TEST"), "LLM integration tests disabled")
def test_llm_fix_weak_language_real():
    """End-to-end: LLM fixes weak language in a CLAUDE.md file."""
    ...
```

### 7.3 Snapshot Tests

For the fix loop, use deterministic fake responses and assert:
- Correct diffs produced
- Correct number of iterations
- Token usage accounting
- Proper revert on degradation

### 7.4 What NOT to Test

- LiteLLM internals (their responsibility)
- Actual model quality (non-deterministic, changes with model versions)
- Network behavior (mock the provider boundary)

## 8. Future Extensibility

The engine is deliberately generic. Future uses:

| Feature | How It Uses the Engine |
|---------|----------------------|
| `skillsaw explain <rule>` | Engine with read-only tools, explains why a violation matters |
| `skillsaw suggest` | Engine analyzes repo structure, suggests new rules to enable |
| Custom rule authoring | Engine generates rule skeleton from natural language description |
| Cross-file refactoring | Engine with multi-file tool access for coordinated edits |

All of these are different system prompts + tool sets passed to the same
`LLMEngine.run()`.

## 9. Security Considerations

- **Path traversal:** All file tools validate paths stay within repo root
- **No network tools:** The LLM cannot make HTTP requests or access external resources
- **No shell execution:** The LLM cannot run arbitrary commands
- **Token budget:** Hard ceiling prevents runaway costs
- **Confirmation by default:** Changes shown as diff, user must approve (unless `--yes`)
- **API keys:** Never logged, never included in error messages
