"""A forced format selects checks without declaring another skill consumer."""

import json

import pytest

from skillsaw.blocks import SkillBlock, HooksBlock, SettingsBlock
from skillsaw.blocks.cursor import CursorPluginBlock, CursorPluginHooksBlock
from skillsaw.blocks.pi import PiSkillBlock
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.rules.builtin.cursor.plugin_valid import CursorPluginValidRule
from tests.cli_runner import run_cli
from tests.test_integration import copy_fixture


@pytest.mark.parametrize("forced", [None, {RepositoryType.CURSOR_PLUGIN}])
def test_pi_native_skill_keeps_declared_owner(tmp_path, forced):
    root = copy_fixture("cursor-plugins/forced-pi-provenance", tmp_path)
    context = RepositoryContext(root, repo_types=forced)
    assert context.provenance(root).ecosystems == frozenset({"pi"})
    assert [b.path for b in context.lint_tree.find(PiSkillBlock)] == [
        root / "skills/review/SKILL.md"
    ]
    assert not context.lint_tree.find(SkillBlock)
    if forced:
        assert context.lint_tree.find(CursorPluginBlock)
        assert CursorPluginValidRule().check(context)


def test_forced_cursor_cli_preserves_native_skill_validation(tmp_path):
    root = copy_fixture("cursor-plugins/forced-pi-provenance", tmp_path)
    result = run_cli(
        [
            "lint",
            str(root),
            "--no-custom-rules",
            "--type",
            "cursor-plugin",
            "--rule",
            "agentskill-valid",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["violations"] == []


@pytest.mark.parametrize("forced", [None, {RepositoryType.CURSOR_PLUGIN}])
def test_real_dual_claim_retains_portable_validation(tmp_path, forced):
    root = copy_fixture("pi/dual-cursor", tmp_path)
    context = RepositoryContext(root, repo_types=forced)
    assert context.provenance(root).ecosystems == frozenset({"pi", "cursor"})
    assert context.lint_tree.find(SkillBlock)
    assert not context.lint_tree.find(PiSkillBlock)


def test_forced_empty_root_reports_missing_manifest_without_claim(tmp_path):
    context = RepositoryContext(tmp_path, repo_types={RepositoryType.CURSOR_PLUGIN})
    assert not context.provenance(tmp_path).ecosystems
    findings = CursorPluginValidRule().check(context)
    assert len(findings) == 1
    assert findings[0].file_path == tmp_path / ".cursor-plugin/plugin.json"


def test_forced_unclaimed_root_keeps_cursor_config_dialect(tmp_path):
    root = copy_fixture("cursor-plugins/forced-unclaimed", tmp_path)
    context = RepositoryContext(root, repo_types={RepositoryType.CURSOR_PLUGIN})
    assert not context.provenance(root).ecosystems
    hooks = context.lint_tree.find(HooksBlock)
    assert len(hooks) == 1
    assert isinstance(hooks[0], CursorPluginHooksBlock)
    assert not context.lint_tree.find(SettingsBlock)
