"""
Rules for validating Cursor .mdc rules files and legacy .cursorrules
"""

import re
from pathlib import Path
from typing import List, Optional

import yaml

from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.utils import read_text, frontmatter_key_line

_VALID_FRONTMATTER_KEYS = {"description", "globs", "alwaysApply"}

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)---[ \t]*\n?", re.DOTALL)


def _parse_mdc_frontmatter(content: str):
    """Parse YAML frontmatter from MDC content.

    Returns (frontmatter_dict, error_message). If no frontmatter is present,
    returns (None, None). If parsing fails, returns (None, error_string).
    """
    if not content.startswith("---"):
        return None, None

    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None, "Unterminated frontmatter (missing closing '---')"

    raw = m.group(1).rstrip("\n")
    try:
        data = yaml.safe_load(raw) if raw else None
    except yaml.YAMLError as e:
        return None, f"Invalid YAML in frontmatter: {e}"

    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, "Frontmatter must be a YAML mapping"
    return data, None


class CursorMdcValidRule(Rule):
    """Validate .cursor/rules/*.mdc files: valid frontmatter, known keys, correct types"""

    repo_types = None

    @property
    def rule_id(self) -> str:
        return "cursor-mdc-valid"

    @property
    def description(self) -> str:
        return (
            "Cursor .mdc rule files must have valid frontmatter with known keys and correct types"
        )

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def _find_cursor_rules_dir(self, context: RepositoryContext) -> Path:
        return context.root_path / ".cursor" / "rules"

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        rules_dir = self._find_cursor_rules_dir(context)
        if not rules_dir.is_dir():
            return violations

        for file_path in sorted(rules_dir.rglob("*")):
            if file_path.is_dir():
                continue

            if file_path.suffix.lower() != ".mdc":
                violations.append(
                    self.violation(
                        f"Non-.mdc file in .cursor/rules/: '{file_path.name}' "
                        f"(only .mdc files are loaded by Cursor)",
                        file_path=file_path,
                        severity=Severity.WARNING,
                    )
                )
                continue

            content = read_text(file_path)
            if content is None:
                violations.append(
                    self.violation(
                        f"Failed to read file: {file_path}",
                        file_path=file_path,
                    )
                )
                continue

            if not content.strip():
                violations.append(
                    self.violation(
                        "Empty .mdc file",
                        file_path=file_path,
                        severity=Severity.WARNING,
                    )
                )
                continue

            frontmatter, error = _parse_mdc_frontmatter(content)
            if error:
                violations.append(self.violation(error, file_path=file_path))
                continue

            if frontmatter is None:
                violations.append(
                    self.violation(
                        "Missing frontmatter: .mdc files require YAML frontmatter "
                        "with at least 'description', 'globs', or 'alwaysApply'",
                        file_path=file_path,
                        severity=Severity.WARNING,
                    )
                )
                continue

            self._check_frontmatter_keys(file_path, frontmatter, violations)
            self._check_description(file_path, frontmatter, violations)
            self._check_globs(file_path, frontmatter, violations)
            self._check_always_apply(file_path, frontmatter, violations)

        return violations

    def _check_frontmatter_keys(
        self,
        file_path: Path,
        frontmatter: dict,
        violations: List[RuleViolation],
    ) -> None:
        unknown_keys = set(frontmatter.keys()) - _VALID_FRONTMATTER_KEYS
        for key in sorted(unknown_keys):
            violations.append(
                self.violation(
                    f"Unknown frontmatter key '{key}'. "
                    f"Valid keys: description, globs, alwaysApply",
                    file_path=file_path,
                    line=frontmatter_key_line(file_path, key),
                    severity=Severity.WARNING,
                )
            )

    def _check_description(
        self,
        file_path: Path,
        frontmatter: dict,
        violations: List[RuleViolation],
    ) -> None:
        if "description" not in frontmatter:
            return

        desc = frontmatter["description"]
        line = frontmatter_key_line(file_path, "description")

        if not isinstance(desc, str):
            violations.append(
                self.violation(
                    f"'description' must be a string, got {type(desc).__name__}",
                    file_path=file_path,
                    line=line,
                )
            )
            return

        if not desc.strip():
            violations.append(
                self.violation(
                    "'description' is empty",
                    file_path=file_path,
                    line=line,
                    severity=Severity.WARNING,
                )
            )

    def _check_globs(
        self,
        file_path: Path,
        frontmatter: dict,
        violations: List[RuleViolation],
    ) -> None:
        if "globs" not in frontmatter:
            return

        globs = frontmatter["globs"]
        line = frontmatter_key_line(file_path, "globs")

        if not isinstance(globs, str):
            violations.append(
                self.violation(
                    f"'globs' must be a string (comma-separated patterns), "
                    f"got {type(globs).__name__}",
                    file_path=file_path,
                    line=line,
                )
            )
            return

        if not globs.strip():
            violations.append(
                self.violation(
                    "'globs' is empty",
                    file_path=file_path,
                    line=line,
                    severity=Severity.WARNING,
                )
            )
            return

        patterns = [p.strip() for p in globs.split(",")]
        for pattern in patterns:
            if not pattern:
                violations.append(
                    self.violation(
                        "Empty glob pattern in comma-separated 'globs' value",
                        file_path=file_path,
                        line=line,
                        severity=Severity.WARNING,
                    )
                )

    def _check_always_apply(
        self,
        file_path: Path,
        frontmatter: dict,
        violations: List[RuleViolation],
    ) -> None:
        if "alwaysApply" not in frontmatter:
            return

        value = frontmatter["alwaysApply"]
        line = frontmatter_key_line(file_path, "alwaysApply")

        if not isinstance(value, bool):
            violations.append(
                self.violation(
                    f"'alwaysApply' must be a boolean (true/false), " f"got {type(value).__name__}",
                    file_path=file_path,
                    line=line,
                )
            )


class CursorRulesDeprecatedRule(Rule):
    """Warn about legacy .cursorrules file (deprecated in favor of .cursor/rules/)"""

    repo_types = None

    @property
    def rule_id(self) -> str:
        return "cursor-rules-deprecated"

    @property
    def description(self) -> str:
        return "Legacy .cursorrules file is deprecated; migrate to .cursor/rules/*.mdc"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations: List[RuleViolation] = []

        cursorrules = context.root_path / ".cursorrules"
        if not cursorrules.exists():
            return violations

        content = read_text(cursorrules)
        if content is None:
            violations.append(
                self.violation(
                    "Failed to read .cursorrules file",
                    file_path=cursorrules,
                )
            )
            return violations

        if not content.strip():
            violations.append(
                self.violation(
                    ".cursorrules file is empty",
                    file_path=cursorrules,
                )
            )
            return violations

        violations.append(
            self.violation(
                ".cursorrules is deprecated. "
                "Migrate to .cursor/rules/*.mdc for per-rule control, "
                "glob-based auto-attachment, and better organization",
                file_path=cursorrules,
            )
        )

        return violations
