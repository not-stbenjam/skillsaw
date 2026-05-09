"""Tests for Copilot instruction file validation rules"""

import pytest
from pathlib import Path
import tempfile
import shutil

from skillsaw.context import RepositoryContext
from skillsaw.rule import Severity, AutofixConfidence
from skillsaw.rules.builtin.copilot_instructions import (
    CopilotInstructionsValidRule,
    CopilotDotInstructionsValidRule,
    CopilotFrontmatterValidRule,
    CopilotApplyToValidRule,
    CopilotCodeReviewTruncationRule,
    CopilotInstructionHierarchyRule,
    CopilotDeadFileRefsRule,
    CopilotDeadCommandRefsRule,
    CopilotWeakLanguageRule,
    CopilotSizeLimitRule,
    CopilotTautologicalRule,
    CopilotCriticalPositionRule,
)


@pytest.fixture
def temp_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


class TestCopilotInstructionsValidRule:
    def test_rule_metadata(self):
        rule = CopilotInstructionsValidRule()
        assert rule.rule_id == "copilot-instructions-valid"
        assert rule.default_severity() == Severity.WARNING
        assert rule.repo_types is None

    def test_no_file_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionsValidRule().check(context)
        assert len(violations) == 0

    def test_valid_file_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "# Copilot Instructions\nUse TypeScript.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionsValidRule().check(context)
        assert len(violations) == 0

    def test_empty_file_fails(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("")
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_whitespace_only_file_fails(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("   \n\n  \n")
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_invalid_encoding_fails(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_bytes(b"\x80\x81\x82\x83")
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert (
            "encoding" in violations[0].message.lower() or "read" in violations[0].message.lower()
        )


class TestCopilotDotInstructionsValidRule:
    def test_rule_metadata(self):
        rule = CopilotDotInstructionsValidRule()
        assert rule.rule_id == "copilot-dot-instructions-valid"
        assert rule.default_severity() == Severity.WARNING
        assert rule.repo_types is None

    def test_no_files_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 0

    def test_valid_single_glob_passes(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\n---\nUse type hints.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 0

    def test_valid_glob_list_passes(self, temp_dir):
        content = '---\napplyTo:\n  - "**/*.py"\n  - "**/*.js"\n---\nBe helpful.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 0

    def test_nested_instructions_file(self, temp_dir):
        subdir = temp_dir / "src" / "components"
        subdir.mkdir(parents=True)
        content = '---\napplyTo: "*.tsx"\n---\nUse React hooks.\n'
        (subdir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 0

    def test_empty_file_fails(self, temp_dir):
        (temp_dir / ".instructions.md").write_text("")
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_invalid_encoding_fails(self, temp_dir):
        (temp_dir / ".instructions.md").write_bytes(b"\x80\x81\x82\x83")
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert (
            "encoding" in violations[0].message.lower() or "read" in violations[0].message.lower()
        )

    def test_missing_frontmatter_fails(self, temp_dir):
        (temp_dir / ".instructions.md").write_text("Just some text without frontmatter.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "frontmatter" in violations[0].message.lower()

    def test_missing_apply_to_fails(self, temp_dir):
        content = "---\ntitle: Instructions\n---\nSome content.\n"
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "applyTo" in violations[0].message

    def test_apply_to_wrong_type_fails(self, temp_dir):
        content = "---\napplyTo: 42\n---\nSome content.\n"
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "string or list" in violations[0].message.lower()

    def test_apply_to_empty_pattern_fails(self, temp_dir):
        content = '---\napplyTo: ""\n---\nSome content.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "empty pattern" in violations[0].message.lower()

    def test_apply_to_list_with_non_string_fails(self, temp_dir):
        content = '---\napplyTo:\n  - "**/*.py"\n  - 42\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert "non-string" in violations[0].message.lower()

    def test_apply_to_line_number_reported(self, temp_dir):
        content = "---\ntitle: Test\napplyTo: 42\n---\nContent.\n"
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 1
        assert violations[0].line == 3

    def test_multiple_files_validated(self, temp_dir):
        (temp_dir / ".instructions.md").write_text("No frontmatter.\n")
        subdir = temp_dir / "src"
        subdir.mkdir()
        (subdir / ".instructions.md").write_text("")
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 2

    def test_valid_complex_globs_pass(self, temp_dir):
        content = '---\napplyTo:\n  - "src/**/*.{ts,tsx}"\n  - "tests/*.test.js"\n  - "docs/**"\n---\nInstructions.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotDotInstructionsValidRule().check(context)
        assert len(violations) == 0


class TestCopilotFrontmatterValidRule:
    def test_rule_metadata(self):
        rule = CopilotFrontmatterValidRule()
        assert rule.rule_id == "copilot-frontmatter-valid"
        assert rule.default_severity() == Severity.WARNING
        assert rule.supports_autofix

    def test_no_files_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = CopilotFrontmatterValidRule().check(context)
        assert len(violations) == 0

    def test_valid_keys_passes(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\ndescription: Python rules\nglobs:\n  - "*.py"\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotFrontmatterValidRule().check(context)
        assert len(violations) == 0

    def test_unknown_key_fails(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\ntitle: Bad key\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotFrontmatterValidRule().check(context)
        assert len(violations) == 1
        assert "title" in violations[0].message
        assert "silently ignores" in violations[0].message

    def test_multiple_unknown_keys(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\ntitle: Bad\nauthor: Also bad\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotFrontmatterValidRule().check(context)
        assert len(violations) == 2

    def test_line_number_reported(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\ntitle: Bad key\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotFrontmatterValidRule().check(context)
        assert violations[0].line == 3

    def test_autofix_removes_invalid_keys(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\ntitle: Bad key\n---\nContent.\n'
        fp = temp_dir / ".instructions.md"
        fp.write_text(content)
        context = RepositoryContext(temp_dir)
        rule = CopilotFrontmatterValidRule()
        violations = rule.check(context)
        fixes = rule.fix(context, violations)
        assert len(fixes) == 1
        assert fixes[0].confidence == AutofixConfidence.SAFE
        assert "title" not in fixes[0].fixed_content
        assert "applyTo" in fixes[0].fixed_content


class TestCopilotApplyToValidRule:
    def test_rule_metadata(self):
        rule = CopilotApplyToValidRule()
        assert rule.rule_id == "copilot-apply-to-valid"
        assert rule.default_severity() == Severity.WARNING

    def test_no_files_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = CopilotApplyToValidRule().check(context)
        assert len(violations) == 0

    def test_valid_glob_matching_files_passes(self, temp_dir):
        src = temp_dir / "src"
        src.mkdir()
        (src / "app.py").write_text("pass")
        content = '---\napplyTo: "**/*.py"\n---\nUse type hints.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotApplyToValidRule().check(context)
        assert len(violations) == 0

    def test_overly_broad_pattern_warns(self, temp_dir):
        content = '---\napplyTo: "**"\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotApplyToValidRule().check(context)
        assert len(violations) == 1
        assert "overly broad" in violations[0].message.lower()

    def test_star_pattern_warns(self, temp_dir):
        content = '---\napplyTo: "*"\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotApplyToValidRule().check(context)
        assert len(violations) == 1
        assert "overly broad" in violations[0].message.lower()

    def test_no_matching_files_info(self, temp_dir):
        content = '---\napplyTo: "**/*.xyz"\n---\nContent.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotApplyToValidRule().check(context)
        assert len(violations) == 1
        assert "does not match" in violations[0].message.lower()
        assert violations[0].severity == Severity.INFO


class TestCopilotCodeReviewTruncationRule:
    def test_rule_metadata(self):
        rule = CopilotCodeReviewTruncationRule()
        assert rule.rule_id == "copilot-code-review-truncation"
        assert rule.default_severity() == Severity.WARNING

    def test_short_content_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Short content.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotCodeReviewTruncationRule().check(context)
        assert len(violations) == 0

    def test_warning_near_limit(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        content = "x" * 3600
        (github_dir / "copilot-instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotCodeReviewTruncationRule().check(context)
        assert len(violations) == 1
        assert "approaching" in violations[0].message.lower()

    def test_error_over_limit(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        content = "x" * 4100
        (github_dir / "copilot-instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotCodeReviewTruncationRule().check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.ERROR
        assert "truncates" in violations[0].message.lower()

    def test_under_warning_threshold_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        content = "x" * 3400
        (github_dir / "copilot-instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotCodeReviewTruncationRule().check(context)
        assert len(violations) == 0

    def test_truncation_line_reported(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = ["Line " + str(i) + " " * 50 + "\n" for i in range(100)]
        content = "".join(lines)
        (github_dir / "copilot-instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotCodeReviewTruncationRule().check(context)
        assert len(violations) == 1
        assert violations[0].line is not None


class TestCopilotInstructionHierarchyRule:
    def test_rule_metadata(self):
        rule = CopilotInstructionHierarchyRule()
        assert rule.rule_id == "copilot-instruction-hierarchy"
        assert rule.default_severity() == Severity.WARNING

    def test_single_file_passes(self, temp_dir):
        content = '---\napplyTo: "**/*.py"\n---\nUse type hints.\n'
        (temp_dir / ".instructions.md").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionHierarchyRule().check(context)
        assert len(violations) == 0

    def test_no_overlap_passes(self, temp_dir):
        (temp_dir / ".instructions.md").write_text('---\napplyTo: "**/*"\n---\nUse TypeScript.\n')
        subdir = temp_dir / "src"
        subdir.mkdir()
        (subdir / ".instructions.md").write_text('---\napplyTo: "*.tsx"\n---\nUse React hooks.\n')
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionHierarchyRule().check(context)
        assert len(violations) == 0

    def test_duplicated_instructions_detected(self, temp_dir):
        (temp_dir / ".instructions.md").write_text(
            '---\napplyTo: "**/*"\n---\nUse TypeScript.\nFollow PEP 8.\n'
        )
        subdir = temp_dir / "src"
        subdir.mkdir()
        (subdir / ".instructions.md").write_text('---\napplyTo: "*.tsx"\n---\nUse TypeScript.\n')
        context = RepositoryContext(temp_dir)
        violations = CopilotInstructionHierarchyRule().check(context)
        assert len(violations) == 1
        assert "duplicates" in violations[0].message.lower()


class TestCopilotDeadFileRefsRule:
    def test_rule_metadata(self):
        rule = CopilotDeadFileRefsRule()
        assert rule.rule_id == "copilot-dead-file-refs"
        assert rule.default_severity() == Severity.WARNING

    def test_no_refs_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("No file refs here.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadFileRefsRule().check(context)
        assert len(violations) == 0

    def test_valid_ref_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (temp_dir / "src" / "app.py").parent.mkdir(parents=True)
        (temp_dir / "src" / "app.py").write_text("pass")
        (github_dir / "copilot-instructions.md").write_text("See `src/app.py` for details.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadFileRefsRule().check(context)
        assert len(violations) == 0

    def test_dead_ref_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "See `src/nonexistent.py` for details.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadFileRefsRule().check(context)
        assert len(violations) == 1
        assert "nonexistent.py" in violations[0].message

    def test_line_number_reported(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "Line 1\nLine 2\nSee `src/missing.py` here.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadFileRefsRule().check(context)
        assert len(violations) == 1
        assert violations[0].line == 3


class TestCopilotDeadCommandRefsRule:
    def test_rule_metadata(self):
        rule = CopilotDeadCommandRefsRule()
        assert rule.rule_id == "copilot-dead-command-refs"
        assert rule.default_severity() == Severity.WARNING

    def test_no_commands_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("No commands here.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadCommandRefsRule().check(context)
        assert len(violations) == 0

    def test_valid_npm_script_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        import json

        (temp_dir / "package.json").write_text(
            json.dumps({"scripts": {"test": "jest", "lint": "eslint ."}})
        )
        (github_dir / "copilot-instructions.md").write_text(
            "Run `npm run test` before committing.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadCommandRefsRule().check(context)
        assert len(violations) == 0

    def test_dead_npm_script_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        import json

        (temp_dir / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
        (github_dir / "copilot-instructions.md").write_text(
            "Run `npm run nonexistent` before committing.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadCommandRefsRule().check(context)
        assert len(violations) == 1
        assert "nonexistent" in violations[0].message

    def test_valid_make_target_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (temp_dir / "Makefile").write_text("build:\n\tgo build ./...\n\ntest:\n\tgo test ./...\n")
        (github_dir / "copilot-instructions.md").write_text("Run `make test` first.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadCommandRefsRule().check(context)
        assert len(violations) == 0

    def test_dead_make_target_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (temp_dir / "Makefile").write_text("build:\n\tgo build ./...\n")
        (github_dir / "copilot-instructions.md").write_text("Run `make nonexistent` first.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotDeadCommandRefsRule().check(context)
        assert len(violations) == 1
        assert "nonexistent" in violations[0].message


class TestCopilotWeakLanguageRule:
    def test_rule_metadata(self):
        rule = CopilotWeakLanguageRule()
        assert rule.rule_id == "copilot-weak-language"
        assert rule.default_severity() == Severity.INFO

    def test_direct_language_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "Use TypeScript for all new files.\nAlways add type annotations.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotWeakLanguageRule().check(context)
        assert len(violations) == 0

    def test_weak_try_to_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Try to use TypeScript.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotWeakLanguageRule().check(context)
        assert len(violations) == 1
        assert "try to" in violations[0].message.lower()

    def test_weak_be_careful_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Be careful with database queries.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotWeakLanguageRule().check(context)
        assert len(violations) == 1
        assert "be careful" in violations[0].message.lower()

    def test_weak_where_possible_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Use async/await where possible.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotWeakLanguageRule().check(context)
        assert len(violations) == 1
        assert "where possible" in violations[0].message.lower()

    def test_suggestion_provided(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Try to use TypeScript.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotWeakLanguageRule().check(context)
        assert len(violations) == 1
        assert "imperative" in violations[0].message.lower()


class TestCopilotSizeLimitRule:
    def test_rule_metadata(self):
        rule = CopilotSizeLimitRule()
        assert rule.rule_id == "copilot-size-limit"
        assert rule.default_severity() == Severity.INFO

    def test_no_file_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = CopilotSizeLimitRule().check(context)
        assert len(violations) == 0

    def test_good_size_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = ["Line " + str(i) + "\n" for i in range(100)]
        (github_dir / "copilot-instructions.md").write_text("".join(lines))
        context = RepositoryContext(temp_dir)
        violations = CopilotSizeLimitRule().check(context)
        assert len(violations) == 0

    def test_too_long_warns(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = ["Line " + str(i) + "\n" for i in range(200)]
        (github_dir / "copilot-instructions.md").write_text("".join(lines))
        context = RepositoryContext(temp_dir)
        violations = CopilotSizeLimitRule().check(context)
        assert len(violations) == 1
        assert "200 lines" in violations[0].message
        assert "60-150" in violations[0].message

    def test_exactly_150_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = ["Line " + str(i) + "\n" for i in range(150)]
        (github_dir / "copilot-instructions.md").write_text("".join(lines))
        context = RepositoryContext(temp_dir)
        violations = CopilotSizeLimitRule().check(context)
        assert len(violations) == 0


class TestCopilotTautologicalRule:
    def test_rule_metadata(self):
        rule = CopilotTautologicalRule()
        assert rule.rule_id == "copilot-tautological"
        assert rule.default_severity() == Severity.INFO
        assert rule.supports_autofix

    def test_non_tautological_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "Use the project's custom logger, not console.log.\n"
        )
        context = RepositoryContext(temp_dir)
        violations = CopilotTautologicalRule().check(context)
        assert len(violations) == 0

    def test_write_clean_code_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Write clean code.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotTautologicalRule().check(context)
        assert len(violations) == 1
        assert "write clean code" in violations[0].message.lower()

    def test_follow_best_practices_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("Follow best practices.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotTautologicalRule().check(context)
        assert len(violations) == 1
        assert "follow best practices" in violations[0].message.lower()

    def test_you_are_an_ai_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("You are an AI assistant.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotTautologicalRule().check(context)
        assert len(violations) == 1
        assert "you are an ai" in violations[0].message.lower()

    def test_autofix_removes_tautology(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "Use TypeScript.\nWrite clean code.\nAdd tests.\n"
        )
        context = RepositoryContext(temp_dir)
        rule = CopilotTautologicalRule()
        violations = rule.check(context)
        fixes = rule.fix(context, violations)
        assert len(fixes) == 1
        assert "write clean code" not in fixes[0].fixed_content.lower()
        assert "Use TypeScript" in fixes[0].fixed_content


class TestCopilotCriticalPositionRule:
    def test_rule_metadata(self):
        rule = CopilotCriticalPositionRule()
        assert rule.rule_id == "copilot-critical-position"
        assert rule.default_severity() == Severity.INFO

    def test_short_file_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text("You MUST use TypeScript.\n")
        context = RepositoryContext(temp_dir)
        violations = CopilotCriticalPositionRule().check(context)
        assert len(violations) == 0

    def test_critical_at_top_passes(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = ["You MUST use TypeScript.\n"]
        lines.extend([f"Regular line {i}.\n" for i in range(30)])
        (github_dir / "copilot-instructions.md").write_text("".join(lines))
        context = RepositoryContext(temp_dir)
        violations = CopilotCriticalPositionRule().check(context)
        assert len(violations) == 0

    def test_critical_buried_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = [f"Regular line {i}.\n" for i in range(15)]
        lines.append("You MUST use TypeScript.\n")
        lines.extend([f"More regular line {i}.\n" for i in range(15)])
        (github_dir / "copilot-instructions.md").write_text("".join(lines))
        context = RepositoryContext(temp_dir)
        violations = CopilotCriticalPositionRule().check(context)
        assert len(violations) == 1
        assert "buried" in violations[0].message.lower()

    def test_never_keyword_detected(self, temp_dir):
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        lines = [f"Regular line {i}.\n" for i in range(15)]
        lines.append("NEVER use var in JavaScript.\n")
        lines.extend([f"More regular line {i}.\n" for i in range(15)])
        (github_dir / "copilot-instructions.md").write_text("".join(lines))
        context = RepositoryContext(temp_dir)
        violations = CopilotCriticalPositionRule().check(context)
        assert len(violations) == 1
        assert violations[0].line == 16


class TestContentAnalysisModule:
    """Tests for the shared content_analysis utilities."""

    def test_weak_language_skips_headings(self):
        from skillsaw.rules.builtin.content_analysis import weak_language_detector

        text = "# Try to understand\nUse direct language.\n"
        matches = weak_language_detector(text)
        assert len(matches) == 0

    def test_dead_ref_scanner_skips_urls(self):
        from skillsaw.rules.builtin.content_analysis import dead_ref_scanner

        text = "See https://example.com/path/file.py for details.\n"
        refs = dead_ref_scanner(text, Path("/nonexistent"))
        assert len(refs) == 0

    def test_dead_ref_scanner_skips_globs(self):
        from skillsaw.rules.builtin.content_analysis import dead_ref_scanner

        text = "Match all `*.py` files.\n"
        refs = dead_ref_scanner(text, Path("/nonexistent"))
        assert len(refs) == 0

    def test_tautological_detector_finds_multiple(self):
        from skillsaw.rules.builtin.content_analysis import tautological_detector

        text = "You are an AI.\nWrite clean code.\nFollow best practices.\n"
        matches = tautological_detector(text)
        assert len(matches) == 3

    def test_critical_position_ignores_short_files(self):
        from skillsaw.rules.builtin.content_analysis import critical_position_analyzer

        text = "You MUST do this.\nNEVER do that.\n"
        issues = critical_position_analyzer(text)
        assert len(issues) == 0

    def test_dead_command_scanner_no_package_json(self, temp_dir):
        from skillsaw.rules.builtin.content_analysis import dead_command_scanner

        text = "Run `npm run test` to check.\n"
        refs = dead_command_scanner(text, temp_dir)
        assert len(refs) == 0
