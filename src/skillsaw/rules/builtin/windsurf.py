"""
Rule for validating Windsurf .windsurfrules instruction file.
"""

from typing import List

from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.utils import read_text

WINDSURF_RULES_FILE = ".windsurfrules"
WINDSURF_CHAR_LIMIT = 12_000


class WindsurfRulesValidRule(Rule):
    """Check that .windsurfrules is valid UTF-8, non-empty, and within the 12K character limit"""

    @property
    def rule_id(self) -> str:
        return "windsurf-rules-valid"

    @property
    def description(self) -> str:
        return ".windsurfrules must be valid UTF-8, non-empty, and within the 12K character limit"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        file_path = context.root_path / WINDSURF_RULES_FILE
        if not file_path.exists():
            return violations

        content = read_text(file_path)
        if content is None:
            violations.append(
                self.violation(
                    f"Failed to read {WINDSURF_RULES_FILE} (invalid encoding or I/O error)",
                    file_path=file_path,
                )
            )
            return violations

        if not content.strip():
            violations.append(
                self.violation(f"{WINDSURF_RULES_FILE} is empty", file_path=file_path)
            )
            return violations

        if len(content) > WINDSURF_CHAR_LIMIT:
            violations.append(
                self.violation(
                    f"{WINDSURF_RULES_FILE} is {len(content):,} characters, "
                    f"exceeding the 12,000 character limit",
                    file_path=file_path,
                )
            )

        return violations
