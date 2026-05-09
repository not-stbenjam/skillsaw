"""Tests for Cline .clinerules validation rule"""

import pytest
from pathlib import Path
import tempfile
import shutil

from skillsaw.context import RepositoryContext
from skillsaw.rule import Severity
from skillsaw.rules.builtin.cline import ClineRulesValidRule


@pytest.fixture
def temp_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


class TestClineRulesValidRule:
    def test_rule_metadata(self):
        rule = ClineRulesValidRule()
        assert rule.rule_id == "cline-rules-valid"
        assert rule.default_severity() == Severity.WARNING
        assert rule.repo_types is None

    def test_no_clinerules_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 0

    # --- File form ---

    def test_valid_file_passes(self, temp_dir):
        (temp_dir / ".clinerules").write_text("# Coding Style\nUse 4 spaces.\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 0

    def test_empty_file_fails(self, temp_dir):
        (temp_dir / ".clinerules").write_text("")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_whitespace_only_file_fails(self, temp_dir):
        (temp_dir / ".clinerules").write_text("   \n\n  \n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_invalid_encoding_file_fails(self, temp_dir):
        (temp_dir / ".clinerules").write_bytes(b"\x80\x81\x82\x83")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "utf-8" in violations[0].message.lower()

    # --- Directory form ---

    def test_valid_directory_passes(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-coding-style.md").write_text("# Coding Style\n")
        (rules_dir / "02-docs.md").write_text("# Documentation\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 0

    def test_empty_directory_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_non_markdown_file_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-style.txt").write_text("Some rules\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "non-markdown" in violations[0].message.lower()

    def test_missing_numbered_prefix_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "coding-style.md").write_text("# Style\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "numbered prefix" in violations[0].message.lower()

    def test_duplicate_number_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-coding-style.md").write_text("# Style\n")
        (rules_dir / "01-other.md").write_text("# Other\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "duplicate" in violations[0].message.lower()

    def test_gap_in_numbering_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-style.md").write_text("# Style\n")
        (rules_dir / "03-docs.md").write_text("# Docs\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "gap" in violations[0].message.lower()
        assert "02" in violations[0].message

    def test_empty_file_in_directory_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-empty.md").write_text("")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_invalid_encoding_in_directory_fails(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-bad.md").write_bytes(b"\x80\x81\x82")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 1
        assert (
            "read" in violations[0].message.lower() or "encoding" in violations[0].message.lower()
        )

    def test_hidden_files_ignored(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / ".hidden").write_text("ignored\n")
        (rules_dir / "01-style.md").write_text("# Style\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 0

    def test_multiple_violations(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-style.md").write_text("# Style\n")
        (rules_dir / "notes.txt").write_text("notes\n")
        (rules_dir / "no-prefix.md").write_text("# No prefix\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) >= 2

    def test_single_file_no_gap(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "01-only.md").write_text("# Only file\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 0

    def test_numbering_starting_from_zero(self, temp_dir):
        rules_dir = temp_dir / ".clinerules"
        rules_dir.mkdir()
        (rules_dir / "00-intro.md").write_text("# Intro\n")
        (rules_dir / "01-style.md").write_text("# Style\n")
        context = RepositoryContext(temp_dir)
        violations = ClineRulesValidRule().check(context)
        assert len(violations) == 0
