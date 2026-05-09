"""
Tests for Cursor .mdc rules validation and legacy .cursorrules deprecation
"""

import pytest
from pathlib import Path

from skillsaw.rules.builtin.cursor import CursorMdcValidRule, CursorRulesDeprecatedRule
from skillsaw.rule import Severity
from skillsaw.context import RepositoryContext


@pytest.fixture
def repo_with_cursor_rules(temp_dir):
    """Create a repo with .cursor/rules/ directory"""
    cursor_dir = temp_dir / ".cursor"
    cursor_dir.mkdir()
    rules_dir = cursor_dir / "rules"
    rules_dir.mkdir()
    return temp_dir


def _write_mdc(temp_dir, name, content, subdir=None):
    """Helper to write a .mdc file in .cursor/rules/"""
    rules_dir = temp_dir / ".cursor" / "rules"
    if subdir:
        rules_dir = rules_dir / subdir
        rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / name
    path.write_text(content)
    return path


# --- CursorMdcValidRule tests ---


class TestCursorMdcValid:
    def test_valid_always_apply_rule(self, repo_with_cursor_rules):
        content = (
            "---\n"
            "description: Code style guidelines\n"
            "alwaysApply: true\n"
            "---\n\n"
            "# Code Style\n\n"
            "Use consistent formatting.\n"
        )
        _write_mdc(repo_with_cursor_rules, "code-style.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_valid_auto_attach_rule(self, repo_with_cursor_rules):
        content = (
            "---\n"
            "description: TypeScript conventions\n"
            "globs: src/**/*.ts, src/**/*.tsx\n"
            "alwaysApply: false\n"
            "---\n\n"
            "# TypeScript Rules\n"
        )
        _write_mdc(repo_with_cursor_rules, "typescript.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_valid_agent_rule(self, repo_with_cursor_rules):
        content = (
            "---\n"
            "description: Database migration guidelines\n"
            "---\n\n"
            "# Database Migrations\n"
        )
        _write_mdc(repo_with_cursor_rules, "db-migrations.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_valid_minimal_frontmatter(self, repo_with_cursor_rules):
        content = "---\nalwaysApply: true\n---\n\nDo something.\n"
        _write_mdc(repo_with_cursor_rules, "minimal.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_no_cursor_rules_dir(self, temp_dir):
        context = RepositoryContext(temp_dir)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_empty_cursor_rules_dir(self, repo_with_cursor_rules):
        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_non_mdc_file_warns(self, repo_with_cursor_rules):
        _write_mdc(repo_with_cursor_rules, "notes.txt", "some notes")

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "Non-.mdc" in violations[0].message
        assert "notes.txt" in violations[0].message

    def test_empty_mdc_file_warns(self, repo_with_cursor_rules):
        _write_mdc(repo_with_cursor_rules, "empty.mdc", "")

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "Empty" in violations[0].message

    def test_whitespace_only_mdc_warns(self, repo_with_cursor_rules):
        _write_mdc(repo_with_cursor_rules, "blank.mdc", "   \n\n  \n")

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "Empty" in violations[0].message

    def test_missing_frontmatter_warns(self, repo_with_cursor_rules):
        content = "# Just Markdown\n\nNo frontmatter here.\n"
        _write_mdc(repo_with_cursor_rules, "no-fm.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "Missing frontmatter" in violations[0].message

    def test_invalid_yaml_frontmatter(self, repo_with_cursor_rules):
        content = "---\ndescription: [unclosed\n---\n\n# Bad YAML\n"
        _write_mdc(repo_with_cursor_rules, "bad-yaml.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.ERROR
        assert "Invalid YAML" in violations[0].message

    def test_unterminated_frontmatter(self, repo_with_cursor_rules):
        content = "---\ndescription: test\nThis never closes\n"
        _write_mdc(repo_with_cursor_rules, "open.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "Unterminated frontmatter" in violations[0].message

    def test_frontmatter_not_a_mapping(self, repo_with_cursor_rules):
        content = "---\n- item1\n- item2\n---\n\n# List\n"
        _write_mdc(repo_with_cursor_rules, "list.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "must be a YAML mapping" in violations[0].message

    def test_unknown_frontmatter_key_warns(self, repo_with_cursor_rules):
        content = "---\n" "description: test\n" "priority: 5\n" "---\n\n" "# Rules\n"
        _write_mdc(repo_with_cursor_rules, "unknown-key.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "priority" in violations[0].message
        assert violations[0].line == 3

    def test_description_not_string(self, repo_with_cursor_rules):
        content = "---\ndescription: 42\n---\n\n# Rules\n"
        _write_mdc(repo_with_cursor_rules, "bad-desc.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "must be a string" in violations[0].message
        assert "int" in violations[0].message

    def test_description_empty_warns(self, repo_with_cursor_rules):
        content = "---\ndescription: ''\n---\n\n# Rules\n"
        _write_mdc(repo_with_cursor_rules, "empty-desc.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "'description' is empty" in violations[0].message

    def test_globs_not_string(self, repo_with_cursor_rules):
        content = "---\nglobs:\n  - '*.ts'\n  - '*.tsx'\n---\n\n# Rules\n"
        _write_mdc(repo_with_cursor_rules, "globs-list.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "must be a string" in violations[0].message
        assert "comma-separated" in violations[0].message

    def test_globs_empty_warns(self, repo_with_cursor_rules):
        content = "---\nglobs: ''\n---\n\n# Rules\n"
        _write_mdc(repo_with_cursor_rules, "empty-globs.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "'globs' is empty" in violations[0].message

    def test_globs_trailing_comma_warns(self, repo_with_cursor_rules):
        content = "---\nglobs: '*.ts, *.tsx,'\n---\n\n# Rules\n"
        _write_mdc(repo_with_cursor_rules, "trailing-comma.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "Empty glob pattern" in violations[0].message

    def test_always_apply_not_bool(self, repo_with_cursor_rules):
        content = "---\nalwaysApply: 1\n---\n\n# Rules\n"
        _write_mdc(repo_with_cursor_rules, "bad-bool.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "must be a boolean" in violations[0].message

    def test_always_apply_string_true(self, repo_with_cursor_rules):
        content = '---\nalwaysApply: "true"\n---\n\n# Rules\n'
        _write_mdc(repo_with_cursor_rules, "string-bool.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "must be a boolean" in violations[0].message

    def test_multiple_valid_mdc_files(self, repo_with_cursor_rules):
        _write_mdc(
            repo_with_cursor_rules,
            "a.mdc",
            "---\ndescription: Rule A\nalwaysApply: true\n---\n\nA\n",
        )
        _write_mdc(
            repo_with_cursor_rules,
            "b.mdc",
            "---\ndescription: Rule B\nglobs: '*.py'\n---\n\nB\n",
        )

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_multiple_errors(self, repo_with_cursor_rules):
        content = (
            "---\n" "description: 42\n" "globs:\n  - bad\n" "alwaysApply: 1\n" "---\n\n" "# Rules\n"
        )
        _write_mdc(repo_with_cursor_rules, "multi-bad.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 3

    def test_mdc_in_subdirectory(self, repo_with_cursor_rules):
        content = "---\ndescription: Nested rule\nalwaysApply: false\n---\n\n# Nested\n"
        _write_mdc(repo_with_cursor_rules, "nested.mdc", content, subdir="category")

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_empty_frontmatter_block(self, repo_with_cursor_rules):
        content = "---\n---\n\n# Empty frontmatter\n"
        _write_mdc(repo_with_cursor_rules, "empty-fm.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_rule_metadata(self):
        rule = CursorMdcValidRule()
        assert rule.rule_id == "cursor-mdc-valid"
        assert "mdc" in rule.description.lower()
        assert rule.default_severity() == Severity.ERROR

    def test_valid_single_glob(self, repo_with_cursor_rules):
        content = "---\nglobs: '**/*.py'\n---\n\n# Python Rules\n"
        _write_mdc(repo_with_cursor_rules, "python.mdc", content)

        context = RepositoryContext(repo_with_cursor_rules)
        rule = CursorMdcValidRule()
        violations = rule.check(context)
        assert len(violations) == 0


# --- CursorRulesDeprecatedRule tests ---


class TestCursorRulesDeprecated:
    def test_no_cursorrules_file(self, temp_dir):
        context = RepositoryContext(temp_dir)
        rule = CursorRulesDeprecatedRule()
        violations = rule.check(context)
        assert len(violations) == 0

    def test_cursorrules_present(self, temp_dir):
        (temp_dir / ".cursorrules").write_text("You are a helpful assistant.\n")

        context = RepositoryContext(temp_dir)
        rule = CursorRulesDeprecatedRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING
        assert "deprecated" in violations[0].message.lower()
        assert ".cursor/rules/" in violations[0].message

    def test_empty_cursorrules(self, temp_dir):
        (temp_dir / ".cursorrules").write_text("")

        context = RepositoryContext(temp_dir)
        rule = CursorRulesDeprecatedRule()
        violations = rule.check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_rule_metadata(self):
        rule = CursorRulesDeprecatedRule()
        assert rule.rule_id == "cursor-rules-deprecated"
        assert "deprecated" in rule.description.lower()
        assert rule.default_severity() == Severity.WARNING

    def test_both_cursorrules_and_mdc(self, repo_with_cursor_rules):
        (repo_with_cursor_rules / ".cursorrules").write_text("Legacy rules here.\n")
        _write_mdc(
            repo_with_cursor_rules,
            "new.mdc",
            "---\ndescription: New rule\nalwaysApply: true\n---\n\n# New\n",
        )

        context = RepositoryContext(repo_with_cursor_rules)

        mdc_rule = CursorMdcValidRule()
        mdc_violations = mdc_rule.check(context)
        assert len(mdc_violations) == 0

        deprecated_rule = CursorRulesDeprecatedRule()
        dep_violations = deprecated_rule.check(context)
        assert len(dep_violations) == 1
        assert "deprecated" in dep_violations[0].message.lower()
