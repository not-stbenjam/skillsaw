"""
Rules for validating Cline .clinerules file or directory
"""

import re
from pathlib import Path
from typing import List

from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.utils import read_text

_NUMBERED_PREFIX_RE = re.compile(r"^(\d+)-")


class ClineRulesValidRule(Rule):
    """Validate .clinerules file or .clinerules/ directory"""

    @property
    def rule_id(self) -> str:
        return "cline-rules-valid"

    @property
    def description(self) -> str:
        return ".clinerules file must be valid UTF-8 and non-empty; .clinerules/ directory files must be markdown with numbered prefixes"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        clinerules = context.root_path / ".clinerules"

        if not clinerules.exists():
            return []

        if clinerules.is_file():
            return self._check_file(clinerules)

        if clinerules.is_dir():
            return self._check_directory(clinerules)

        return []

    def _check_file(self, file_path: Path) -> List[RuleViolation]:
        violations = []

        content = read_text(file_path)
        if content is None:
            violations.append(
                self.violation(
                    ".clinerules is not valid UTF-8",
                    file_path=file_path,
                )
            )
            return violations

        if not content.strip():
            violations.append(
                self.violation(
                    ".clinerules is empty",
                    file_path=file_path,
                )
            )

        return violations

    def _check_directory(self, dir_path: Path) -> List[RuleViolation]:
        violations = []
        seen_numbers: dict[int, Path] = {}

        files = sorted(f for f in dir_path.iterdir() if f.is_file() and not f.name.startswith("."))

        if not files:
            violations.append(
                self.violation(
                    ".clinerules/ directory is empty",
                    file_path=dir_path,
                )
            )
            return violations

        for file_path in files:
            if file_path.suffix.lower() != ".md":
                violations.append(
                    self.violation(
                        f"Non-markdown file in .clinerules/: '{file_path.name}' (expected .md)",
                        file_path=file_path,
                    )
                )
                continue

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

            match = _NUMBERED_PREFIX_RE.match(file_path.stem)
            if not match:
                violations.append(
                    self.violation(
                        f"'{file_path.name}' missing numbered prefix (expected pattern: 01-name.md)",
                        file_path=file_path,
                    )
                )
            else:
                num = int(match.group(1))
                if num in seen_numbers:
                    violations.append(
                        self.violation(
                            f"Duplicate number prefix {match.group(1)} in '{file_path.name}' "
                            f"and '{seen_numbers[num].name}'",
                            file_path=file_path,
                        )
                    )
                else:
                    seen_numbers[num] = file_path

        if seen_numbers:
            numbers = sorted(seen_numbers.keys())
            expected_start = numbers[0]
            expected = list(range(expected_start, expected_start + len(numbers)))
            if numbers != expected:
                missing = set(expected) - set(numbers)
                if missing:
                    missing_strs = [f"{n:02d}" for n in sorted(missing)]
                    violations.append(
                        self.violation(
                            f"Gap in .clinerules/ numbering: missing {', '.join(missing_strs)}",
                            file_path=dir_path,
                        )
                    )

        return violations
