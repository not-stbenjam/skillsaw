"""Configured Pi prompts retain existing skill and plugin prose ownership."""

import json

import pytest

from skillsaw.blocks import BodyContent, CommandBlock, CursorCommandBlock, SkillBlock
from skillsaw.blocks.pi import PiPromptBlock, PiSkillBlock
from skillsaw.context import RepositoryContext
from tests.cli_runner import run_cli
from tests.test_integration import copy_fixture


def blocks_at(context, block_type, path):
    return [block for block in context.lint_tree.find(block_type) if block.path == path]


@pytest.mark.parametrize("source", ["package", "project"])
def test_prompt_selection_preserves_portable_metadata_diagnostic(tmp_path, source):
    repo = copy_fixture("pi/prompt-ownership", tmp_path)
    if source == "project":
        data = json.loads((repo / "package.json").read_text())
        settings = repo / ".pi/settings.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({"prompts": ["../" + p for p in data["pi"]["prompts"]]}))
        (repo / "package.json").unlink()
    path = repo / "skills/review/SKILL.md"
    path.write_text("---\nname: review\n---\nReview changed response schemas.\n")
    context = RepositoryContext(repo)
    assert len(blocks_at(context, SkillBlock, path)) == 1
    assert len(blocks_at(context, BodyContent, path)) == 1
    assert not blocks_at(context, PiPromptBlock, path)
    assert len(blocks_at(context, PiPromptBlock, repo / "prompts/review.md")) == 1
    assert not context.lint_tree_errors

    result = run_cli(
        ["lint", repo, "--no-custom-rules", "--rule", "agentskill-valid", "--format", "json"]
    )
    assert result.returncode == 1, result.stdout + result.stderr
    findings = json.loads(result.stdout)["violations"]
    assert len(findings) == 1
    assert findings[0]["file_path"] == "skills/review/SKILL.md"
    assert findings[0]["message"] == "Missing required 'description' field"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("dual", [False, True])
def test_parent_prompts_preserve_nested_owners(tmp_path, monkeypatch, reverse, dual):
    repo = copy_fixture("pi/prompt-ownership", tmp_path)
    nested = repo / "packages/native"
    if dual:
        marker = nested / ".claude-plugin/plugin.json"
        marker.parent.mkdir()
        marker.write_text('{"name":"native-scan"}')
    context = RepositoryContext(repo)
    roots = context.pi_discovery_roots()
    assert len(roots) == 2
    monkeypatch.setattr(context, "pi_discovery_roots", lambda: sorted(roots, reverse=reverse))
    skill = nested / "skills/scan/SKILL.md"
    command = nested / "commands/review.md"
    expected = SkillBlock if dual else PiSkillBlock
    assert len(blocks_at(context, expected, skill)) == 1
    assert len(blocks_at(context, BodyContent, skill)) == 1
    assert not blocks_at(context, PiPromptBlock, skill)
    assert len(blocks_at(context, CommandBlock, command)) == 1
    assert len(blocks_at(context, BodyContent, command)) == 1
    assert not blocks_at(context, PiPromptBlock, command)
    assert blocks_at(context, CommandBlock, command)[0].plugin_owner == nested
    assert len(blocks_at(context, PiPromptBlock, repo / "prompts/review.md")) == 1
    assert not context.lint_tree_errors


def test_prompt_overlap_runs_shared_content_checks_once(tmp_path):
    repo = copy_fixture("pi/prompt-ownership", tmp_path)
    secret = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    targets = ["skills/review/SKILL.md", "prompts/review.md"]
    for relative in targets:
        path = repo / relative
        with path.open("a") as stream:
            stream.write(f"\nAccess token: {secret}\n")
    result = run_cli(
        [
            "lint",
            repo,
            "--no-custom-rules",
            "--rule",
            "content-embedded-secrets",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 1, result.stdout + result.stderr
    findings = json.loads(result.stdout)["violations"]
    assert len(findings) == 2
    assert sorted(v["file_path"] for v in findings) == sorted(targets)
    for finding in findings:
        expected_line = len((repo / finding["file_path"]).read_text().splitlines())
        assert finding["line"] == expected_line


def test_parent_prompt_preserves_configured_cursor_command(tmp_path):
    repo = copy_fixture("pi/prompt-ownership", tmp_path)
    nested = repo / "packages/native"
    (nested / "package.json").unlink()
    (nested / "commands").rename(nested / "actions")
    marker = nested / ".cursor-plugin/plugin.json"
    marker.parent.mkdir()
    marker.write_text('{"name":"review-actions","commands":"actions"}')
    (repo / "package.json").write_text('{"pi":{"prompts":["packages/native/actions"]}}')
    context = RepositoryContext(repo)
    command = nested / "actions/review.md"
    assert len(blocks_at(context, CursorCommandBlock, command)) == 1
    assert len(blocks_at(context, BodyContent, command)) == 1
    assert not blocks_at(context, PiPromptBlock, command)
    assert blocks_at(context, CursorCommandBlock, command)[0].plugin_owner == nested
    assert not context.lint_tree_errors
