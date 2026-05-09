"""
Rules for validating GitHub Copilot instruction files
(.github/copilot-instructions.md and .instructions.md)
"""

import fnmatch
import re
from pathlib import Path
from typing import List

from skillsaw.rule import Rule, RuleViolation, Severity, AutofixResult, AutofixConfidence
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.utils import read_text, parse_frontmatter, frontmatter_key_line
from skillsaw.rules.builtin.content_analysis import (
    weak_language_detector,
    dead_ref_scanner,
    dead_command_scanner,
    tautological_detector,
    critical_position_analyzer,
)

_VALID_FRONTMATTER_KEYS = {"applyTo", "description", "globs"}

_CODE_REVIEW_TRUNCATION = 4000
_CODE_REVIEW_WARN = 3500

_RECOMMENDED_MIN_LINES = 60
_RECOMMENDED_MAX_LINES = 150


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


def _copilot_files(context: RepositoryContext) -> List[Path]:
    """Collect all copilot instruction files in the repo."""
    files = []
    main = context.root_path / ".github" / "copilot-instructions.md"
    if main.exists():
        files.append(main)
    files.extend(context.root_path.rglob(".instructions.md"))
    return files


class CopilotFrontmatterValidRule(Rule):
    """Check that .instructions.md only uses valid frontmatter keys"""

    @property
    def rule_id(self) -> str:
        return "copilot-frontmatter-valid"

    @property
    def description(self) -> str:
        return ".instructions.md only allows applyTo, description, and globs as frontmatter keys"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in context.root_path.rglob(".instructions.md"):
            content = read_text(file_path)
            if content is None:
                continue
            frontmatter, _ = parse_frontmatter(content)
            if frontmatter is None:
                continue
            for key in frontmatter:
                if key not in _VALID_FRONTMATTER_KEYS:
                    line = frontmatter_key_line(file_path, key)
                    violations.append(
                        self.violation(
                            f"Unknown frontmatter key '{key}' — Copilot silently ignores it (valid keys: {', '.join(sorted(_VALID_FRONTMATTER_KEYS))})",
                            file_path=file_path,
                            line=line,
                        )
                    )
        return violations

    def fix(
        self,
        context: RepositoryContext,
        violations: List[RuleViolation],
    ) -> List[AutofixResult]:
        results = []
        files_seen = set()
        for v in violations:
            if v.file_path is None or v.file_path in files_seen:
                continue
            files_seen.add(v.file_path)
            content = read_text(v.file_path)
            if content is None:
                continue
            frontmatter, body = parse_frontmatter(content)
            if frontmatter is None:
                continue
            cleaned = {k: v for k, v in frontmatter.items() if k in _VALID_FRONTMATTER_KEYS}
            if cleaned == frontmatter:
                continue
            import yaml

            fm_str = yaml.dump(cleaned, default_flow_style=False, sort_keys=False).rstrip("\n")
            fixed = f"---\n{fm_str}\n---\n{body}"
            file_violations = [vv for vv in violations if vv.file_path == v.file_path]
            results.append(
                AutofixResult(
                    rule_id=self.rule_id,
                    file_path=v.file_path,
                    confidence=AutofixConfidence.SAFE,
                    original_content=content,
                    fixed_content=fixed,
                    description=f"Removed invalid frontmatter keys from {v.file_path.name}",
                    violations_fixed=file_violations,
                )
            )
        return results


class CopilotApplyToValidRule(Rule):
    """Check that applyTo globs are valid and match existing files"""

    @property
    def rule_id(self) -> str:
        return "copilot-apply-to-valid"

    @property
    def description(self) -> str:
        return "applyTo globs must be syntactically valid and match files in the repo"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in context.root_path.rglob(".instructions.md"):
            content = read_text(file_path)
            if content is None:
                continue
            frontmatter, _ = parse_frontmatter(content)
            if frontmatter is None or "applyTo" not in frontmatter:
                continue
            apply_to = frontmatter["applyTo"]
            apply_to_line = frontmatter_key_line(file_path, "applyTo")
            patterns = (
                [apply_to]
                if isinstance(apply_to, str)
                else apply_to if isinstance(apply_to, list) else []
            )

            for pattern in patterns:
                if not isinstance(pattern, str) or not pattern.strip():
                    continue
                if not _is_valid_glob(pattern):
                    violations.append(
                        self.violation(
                            f"Invalid glob syntax: '{pattern}'",
                            file_path=file_path,
                            line=apply_to_line,
                        )
                    )
                    continue
                if pattern in ("*", "**", "**/*"):
                    violations.append(
                        self.violation(
                            f"Overly broad applyTo pattern '{pattern}' matches all files — use .github/copilot-instructions.md for repo-wide instructions instead",
                            file_path=file_path,
                            line=apply_to_line,
                            severity=Severity.WARNING,
                        )
                    )
                    continue
                from pathlib import PurePosixPath

                matched = any(
                    PurePosixPath(p.relative_to(context.root_path)).match(pattern)
                    for p in context.root_path.rglob("*")
                    if p.is_file()
                    and not any(
                        part.startswith(".") for part in p.relative_to(context.root_path).parts
                    )
                )
                if not matched:
                    violations.append(
                        self.violation(
                            f"applyTo pattern '{pattern}' does not match any files in the repo",
                            file_path=file_path,
                            line=apply_to_line,
                            severity=Severity.INFO,
                        )
                    )
        return violations


class CopilotCodeReviewTruncationRule(Rule):
    """Warn when content exceeds Copilot code review truncation limit"""

    @property
    def rule_id(self) -> str:
        return "copilot-code-review-truncation"

    @property
    def description(self) -> str:
        return "Copilot code review silently truncates instructions beyond 4000 characters"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in _copilot_files(context):
            content = read_text(file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            char_count = len(body)
            if char_count >= _CODE_REVIEW_TRUNCATION:
                trunc_line = None
                running = 0
                for i, line in enumerate(body.splitlines(), 1):
                    running += len(line) + 1
                    if running >= _CODE_REVIEW_TRUNCATION:
                        trunc_line = i
                        break
                violations.append(
                    self.violation(
                        f"Content is {char_count} chars — Copilot code review truncates at {_CODE_REVIEW_TRUNCATION}. Content after line ~{trunc_line} will be silently dropped",
                        file_path=file_path,
                        line=trunc_line,
                        severity=Severity.ERROR,
                    )
                )
            elif char_count >= _CODE_REVIEW_WARN:
                violations.append(
                    self.violation(
                        f"Content is {char_count} chars — approaching Copilot code review truncation limit ({_CODE_REVIEW_TRUNCATION})",
                        file_path=file_path,
                    )
                )
        return violations


class CopilotInstructionHierarchyRule(Rule):
    """Check for contradictions and redundancy between parent/child .instructions.md files"""

    @property
    def rule_id(self) -> str:
        return "copilot-instruction-hierarchy"

    @property
    def description(self) -> str:
        return "Check for contradictions and redundancy between parent and child .instructions.md files"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        instruction_files = list(context.root_path.rglob(".instructions.md"))
        if len(instruction_files) < 2:
            return violations

        file_contents = {}
        for fp in instruction_files:
            content = read_text(fp)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            file_contents[fp] = body.strip()

        for child_path, child_body in file_contents.items():
            if not child_body:
                continue
            parent = child_path.parent.parent
            while parent >= context.root_path:
                parent_file = parent / ".instructions.md"
                if parent_file in file_contents and file_contents[parent_file]:
                    parent_body = file_contents[parent_file]
                    child_lines = set(
                        line.strip().lower()
                        for line in child_body.splitlines()
                        if line.strip() and not line.strip().startswith("#")
                    )
                    parent_lines = set(
                        line.strip().lower()
                        for line in parent_body.splitlines()
                        if line.strip() and not line.strip().startswith("#")
                    )
                    overlap = child_lines & parent_lines
                    if overlap:
                        try:
                            rel = child_path.relative_to(context.root_path)
                            par_rel = parent_file.relative_to(context.root_path)
                        except ValueError:
                            rel = child_path
                            par_rel = parent_file
                        violations.append(
                            self.violation(
                                f"{rel} duplicates {len(overlap)} instruction(s) from parent {par_rel}",
                                file_path=child_path,
                            )
                        )
                    break
                parent = parent.parent

        return violations


class CopilotDeadFileRefsRule(Rule):
    """Check for references to non-existent files in copilot instructions"""

    @property
    def rule_id(self) -> str:
        return "copilot-dead-file-refs"

    @property
    def description(self) -> str:
        return "File paths referenced in copilot instructions must exist"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in _copilot_files(context):
            content = read_text(file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            for ref in dead_ref_scanner(body, context.root_path):
                violations.append(
                    self.violation(
                        f"Referenced file '{ref.ref}' does not exist",
                        file_path=file_path,
                        line=ref.line,
                    )
                )
        return violations


class CopilotDeadCommandRefsRule(Rule):
    """Check for references to non-existent commands/scripts"""

    @property
    def rule_id(self) -> str:
        return "copilot-dead-command-refs"

    @property
    def description(self) -> str:
        return "Commands referenced in copilot instructions must exist in package.json or Makefile"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in _copilot_files(context):
            content = read_text(file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            for ref in dead_command_scanner(body, context.root_path):
                violations.append(
                    self.violation(
                        f"Referenced command '{ref.ref}' not found in project scripts",
                        file_path=file_path,
                        line=ref.line,
                    )
                )
        return violations


class CopilotWeakLanguageRule(Rule):
    """Detect weak/hedging language in copilot instructions"""

    @property
    def rule_id(self) -> str:
        return "copilot-weak-language"

    @property
    def description(self) -> str:
        return "Copilot instructions should use direct, actionable language instead of hedging"

    def default_severity(self) -> Severity:
        return Severity.INFO

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in _copilot_files(context):
            content = read_text(file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            for match in weak_language_detector(body):
                violations.append(
                    self.violation(
                        f"Weak language '{match.text}' — {match.suggestion}",
                        file_path=file_path,
                        line=match.line,
                    )
                )
        return violations

    def fix(
        self,
        context: RepositoryContext,
        violations: List[RuleViolation],
    ) -> List[AutofixResult]:
        return []


class CopilotSizeLimitRule(Rule):
    """Warn when copilot-instructions.md exceeds recommended size"""

    @property
    def rule_id(self) -> str:
        return "copilot-size-limit"

    @property
    def description(self) -> str:
        return ".github/copilot-instructions.md should be 60-150 lines for best effectiveness"

    def default_severity(self) -> Severity:
        return Severity.INFO

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        file_path = context.root_path / ".github" / "copilot-instructions.md"
        if not file_path.exists():
            return violations
        content = read_text(file_path)
        if content is None:
            return violations
        line_count = len(content.splitlines())
        if line_count > _RECOMMENDED_MAX_LINES:
            violations.append(
                self.violation(
                    f"copilot-instructions.md is {line_count} lines — GitHub's analysis of 2500+ repos shows 60-150 lines is most effective",
                    file_path=file_path,
                )
            )
        return violations


class CopilotTautologicalRule(Rule):
    """Detect self-evident instructions that waste context tokens"""

    @property
    def rule_id(self) -> str:
        return "copilot-tautological"

    @property
    def description(self) -> str:
        return (
            "Remove self-evident instructions (e.g. 'write clean code') that waste context tokens"
        )

    def default_severity(self) -> Severity:
        return Severity.INFO

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in _copilot_files(context):
            content = read_text(file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            for match in tautological_detector(body):
                violations.append(
                    self.violation(
                        f"Tautological instruction '{match.text}' — {match.suggestion}",
                        file_path=file_path,
                        line=match.line,
                    )
                )
        return violations

    def fix(
        self,
        context: RepositoryContext,
        violations: List[RuleViolation],
    ) -> List[AutofixResult]:
        results = []
        files_seen = set()
        for v in violations:
            if v.file_path is None or v.file_path in files_seen:
                continue
            files_seen.add(v.file_path)
            content = read_text(v.file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            matches = tautological_detector(body)
            if not matches:
                continue
            lines = body.splitlines(keepends=True)
            lines_to_remove = set()
            for m in matches:
                idx = m.line - 1
                if 0 <= idx < len(lines) and lines[idx].strip():
                    line_text = lines[idx].strip()
                    if line_text.lower() == m.text.lower() or len(line_text) < len(m.text) + 20:
                        lines_to_remove.add(idx)
            if not lines_to_remove:
                continue
            new_lines = [l for i, l in enumerate(lines) if i not in lines_to_remove]
            new_body = "".join(new_lines)
            frontmatter, _ = parse_frontmatter(content)
            if frontmatter is not None:
                import yaml

                fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip(
                    "\n"
                )
                fixed = f"---\n{fm_str}\n---\n{new_body}"
            else:
                fixed = new_body
            file_violations = [vv for vv in violations if vv.file_path == v.file_path]
            results.append(
                AutofixResult(
                    rule_id=self.rule_id,
                    file_path=v.file_path,
                    confidence=AutofixConfidence.SAFE,
                    original_content=content,
                    fixed_content=fixed,
                    description=f"Removed {len(lines_to_remove)} tautological instruction(s)",
                    violations_fixed=file_violations,
                )
            )
        return results


class CopilotCriticalPositionRule(Rule):
    """Check that critical instructions are not buried in the middle of the file"""

    @property
    def rule_id(self) -> str:
        return "copilot-critical-position"

    @property
    def description(self) -> str:
        return (
            "Critical instructions (MUST/NEVER/ALWAYS) should be near the top or bottom of the file"
        )

    def default_severity(self) -> Severity:
        return Severity.INFO

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for file_path in _copilot_files(context):
            content = read_text(file_path)
            if content is None:
                continue
            _, body = parse_frontmatter(content)
            for issue in critical_position_analyzer(body):
                violations.append(
                    self.violation(
                        f"Critical instruction buried at line {issue.line}/{issue.total_lines} — {issue.recommendation}",
                        file_path=file_path,
                        line=issue.line,
                    )
                )
        return violations

    def fix(
        self,
        context: RepositoryContext,
        violations: List[RuleViolation],
    ) -> List[AutofixResult]:
        return []
