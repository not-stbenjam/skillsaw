"""
Rules for validating GitHub Copilot instruction files
(.github/copilot-instructions.md and .instructions.md)
"""

import fnmatch
import re
from typing import List

from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.utils import read_text, parse_frontmatter, frontmatter_key_line


class CopilotInstructionsValidRule(Rule):
    """Check that .github/copilot-instructions.md is valid UTF-8 and non-empty"""

    @property
    def rule_id(self) -> str:
        return "copilot-instructions-valid"

    @property
    def description(self) -> str:
        return ".github/copilot-instructions.md must be valid UTF-8 and non-empty"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        file_path = context.root_path / ".github" / "copilot-instructions.md"
        if not file_path.exists():
            return violations

        content = read_text(file_path)
        if content is None:
            violations.append(
                self.violation(
                    "Failed to read .github/copilot-instructions.md (invalid encoding or I/O error)",
                    file_path=file_path,
                )
            )
            return violations

        if not content.strip():
            violations.append(
                self.violation(
                    ".github/copilot-instructions.md is empty",
                    file_path=file_path,
                )
            )

        return violations


def _is_valid_glob(pattern: str) -> bool:
    """Check whether a glob pattern is syntactically valid."""
    try:
        re.compile(fnmatch.translate(pattern))
        return True
    except re.error:
        return False


class CopilotDotInstructionsValidRule(Rule):
    """Check that .instructions.md files have valid YAML frontmatter with applyTo globs"""

    @property
    def rule_id(self) -> str:
        return "copilot-dot-instructions-valid"

    @property
    def description(self) -> str:
        return ".instructions.md files must have valid YAML frontmatter with applyTo glob patterns"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []

        for file_path in context.root_path.rglob(".instructions.md"):
            content = read_text(file_path)
            if content is None:
                violations.append(
                    self.violation(
                        f"Failed to read {file_path.name} (invalid encoding or I/O error)",
                        file_path=file_path,
                    )
                )
                continue

            if not content.strip():
                violations.append(
                    self.violation(
                        f"{file_path.name} is empty",
                        file_path=file_path,
                    )
                )
                continue

            frontmatter, _ = parse_frontmatter(content)
            if frontmatter is None:
                violations.append(
                    self.violation(
                        f"{file_path.name} is missing YAML frontmatter",
                        file_path=file_path,
                        line=1,
                    )
                )
                continue

            if "applyTo" not in frontmatter:
                violations.append(
                    self.violation(
                        f"{file_path.name} frontmatter is missing required 'applyTo' field",
                        file_path=file_path,
                        line=1,
                    )
                )
                continue

            apply_to = frontmatter["applyTo"]
            apply_to_line = frontmatter_key_line(file_path, "applyTo")

            if isinstance(apply_to, str):
                patterns = [apply_to]
            elif isinstance(apply_to, list):
                patterns = apply_to
            else:
                violations.append(
                    self.violation(
                        f"{file_path.name} 'applyTo' must be a string or list of strings",
                        file_path=file_path,
                        line=apply_to_line,
                    )
                )
                continue

            for pattern in patterns:
                if not isinstance(pattern, str):
                    violations.append(
                        self.violation(
                            f"{file_path.name} 'applyTo' contains non-string value: {pattern!r}",
                            file_path=file_path,
                            line=apply_to_line,
                        )
                    )
                elif not pattern.strip():
                    violations.append(
                        self.violation(
                            f"{file_path.name} 'applyTo' contains empty pattern",
                            file_path=file_path,
                            line=apply_to_line,
                        )
                    )
                elif not _is_valid_glob(pattern):
                    violations.append(
                        self.violation(
                            f"{file_path.name} 'applyTo' contains invalid glob pattern: {pattern!r}",
                            file_path=file_path,
                            line=apply_to_line,
                        )
                    )

        return violations
