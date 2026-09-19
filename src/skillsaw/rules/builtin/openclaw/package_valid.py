"""Validate package.json's native OpenClaw entry declarations."""

from skillsaw.context import RepositoryContext
from skillsaw.lint_target import OpenClawPackageConfigNode
from skillsaw.repository_types import RepositoryType
from skillsaw.rule import Rule, RuleViolation, Severity
from typing import List
from skillsaw.formats.openclaw import read_package, runtime_extensions


class OpenClawPackageValidRule(Rule):
    """Validate extension declaration shapes without assuming built files exist."""

    since = "0.21.0"
    repo_types = frozenset({RepositoryType.OPENCLAW_PLUGIN})
    default_enabled = False

    @property
    def rule_id(self) -> str:
        return "openclaw-package-valid"

    @property
    def description(self) -> str:
        return "OpenClaw package metadata must declare valid extension entries"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for node in context.lint_tree.find(OpenClawPackageConfigNode):
            data, error = read_package(node.path)
            message = None
            if error or not isinstance(data, dict):
                message = f"Invalid package.json: {error or 'expected an object'}"
            else:
                metadata = data.get("openclaw")
                if metadata is not None and not isinstance(metadata, dict):
                    message = "'openclaw' must be an object"
                elif isinstance(metadata, dict):
                    entries = metadata.get("extensions")
                    if entries is not None and (
                        not isinstance(entries, list)
                        or any(not isinstance(entry, str) or not entry.strip() for entry in entries)
                    ):
                        message = "'openclaw.extensions' must be an array of non-empty strings"
                    else:
                        _, message = runtime_extensions(metadata)
            if message:
                violations.append(self.violation(message, file_path=node.path))
        return violations
