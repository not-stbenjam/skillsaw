"""Tests for Windsurf .windsurfrules validation rule"""

import pytest
from pathlib import Path
import tempfile
import shutil

from skillsaw.context import RepositoryContext
from skillsaw.rule import Severity
from skillsaw.rules.builtin.windsurf import WindsurfRulesValidRule, WINDSURF_CHAR_LIMIT


@pytest.fixture
def temp_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


class TestWindsurfRulesValidRule:
    def test_rule_metadata(self):
        rule = WindsurfRulesValidRule()
        assert rule.rule_id == "windsurf-rules-valid"
        assert rule.default_severity() == Severity.WARNING
        assert rule.repo_types is None

    def test_no_file_passes(self, temp_dir):
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 0

    def test_valid_file_passes(self, temp_dir):
        (temp_dir / ".windsurfrules").write_text("# Project Rules\nUse TypeScript.\n")
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 0

    def test_empty_file_fails(self, temp_dir):
        (temp_dir / ".windsurfrules").write_text("")
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_whitespace_only_file_fails(self, temp_dir):
        (temp_dir / ".windsurfrules").write_text("   \n\n  \n")
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_invalid_encoding_fails(self, temp_dir):
        (temp_dir / ".windsurfrules").write_bytes(b"\x80\x81\x82\x83")
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 1
        assert "read" in violations[0].message.lower() or "encoding" in violations[0].message.lower()

    def test_under_char_limit_passes(self, temp_dir):
        content = "x" * (WINDSURF_CHAR_LIMIT - 1)
        (temp_dir / ".windsurfrules").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 0

    def test_at_char_limit_passes(self, temp_dir):
        content = "x" * WINDSURF_CHAR_LIMIT
        (temp_dir / ".windsurfrules").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 0

    def test_over_char_limit_warns(self, temp_dir):
        content = "x" * (WINDSURF_CHAR_LIMIT + 1)
        (temp_dir / ".windsurfrules").write_text(content)
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 1
        assert "12,000" in violations[0].message or "12000" in violations[0].message
        assert violations[0].severity == Severity.WARNING

    def test_file_path_reported(self, temp_dir):
        (temp_dir / ".windsurfrules").write_text("")
        context = RepositoryContext(temp_dir)
        violations = WindsurfRulesValidRule().check(context)
        assert len(violations) == 1
        assert violations[0].file_path == temp_dir / ".windsurfrules"
