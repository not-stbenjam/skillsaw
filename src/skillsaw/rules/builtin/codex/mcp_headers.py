"""Warn about the ignored HTTP MCP ``headers`` key in Codex project TOML."""

from typing import List

from skillsaw.blocks.codex import CodexConfigBlock
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.diagnostics import safe_display
from skillsaw.rule import Rule, RuleViolation, Severity


class CodexMcpHeadersRule(Rule):
    """Catch one known cross-host spelling without a general shape validator."""

    since = "0.21.0"
    repo_types = frozenset({RepositoryType.CODEX_PROJECT})

    @property
    def rule_id(self) -> str:
        return "codex-mcp-headers"

    @property
    def description(self) -> str:
        return "Codex HTTP MCP servers must use http_headers instead of ignored headers"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for block in context.lint_tree.find(CodexConfigBlock):
            for name, server in block.server_entries():
                # Released 0.159.3 derives HTTP from a string URL without
                # command. Leave malformed transports and all other shape
                # checks to Codex; this rule only diagnoses the ignored key.
                if (
                    not isinstance(server, dict)
                    or "command" in server
                    or not isinstance(server.get("url"), str)
                    or "headers" not in server
                ):
                    continue
                violations.append(
                    self.violation(
                        f"Codex ignores 'headers' on MCP server '{safe_display(name)}'; "
                        "use 'http_headers' for literal headers or 'env_http_headers' "
                        "for environment-variable names",
                        block=block,
                    )
                )
        return violations
