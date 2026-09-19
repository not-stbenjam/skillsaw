"""Native Cursor packages: CLI coverage and cross-ecosystem tree invariants."""

import json
from pathlib import Path

import pytest

from skillsaw.blocks import CursorRuleBlock, CursorCommandBlock, SkillBlock, HooksBlock, McpBlock
from skillsaw.blocks.cursor import CursorAgentBlock, CursorPluginBlock
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.rules.builtin.cursor.plugin_valid import CursorPluginValidRule
from skillsaw.rules.builtin.cursor.marketplace_valid import CursorMarketplaceValidRule
from tests.test_integration import copy_fixture, run_lint


def test_cursor_native_components(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.CURSOR_MARKETPLACE
    assert RepositoryType.MARKETPLACE not in context.repo_types
    tree = context.lint_tree
    for cls in (
        CursorRuleBlock,
        CursorCommandBlock,
        CursorAgentBlock,
        SkillBlock,
        CursorPluginBlock,
    ):
        assert len(tree.find(cls)) == 1, cls
    assert len(tree.find(HooksBlock)) == 1
    assert len(tree.find(McpBlock)) == 2
    assert all("ignored" not in str(b.path) for b in tree.find(SkillBlock))
    assert not CursorPluginValidRule().check(context)
    assert not CursorMarketplaceValidRule().check(context)
    result = run_lint(repo)
    assert result["rc"] == 0, result


def test_cursor_broken_cli(tmp_path):
    repo = copy_fixture("cursor-plugins/broken", tmp_path)
    result = run_lint(repo)
    assert result["rc"] == 1, result
    rules = {v["rule_id"] for v in result["out"]["violations"]}
    assert {"cursor-plugin-json-valid", "cursor-marketplace-json-valid", "hooks-dangerous"} <= rules


@pytest.mark.parametrize("forced", [RepositoryType.MARKETPLACE, RepositoryType.CURSOR_PLUGIN])
def test_cursor_provenance_survives_override(tmp_path, forced):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    context = RepositoryContext(repo, repo_types={forced})
    plugin = repo / "packages/review"
    assert context.provenance(plugin).ecosystems == frozenset({"cursor"})
    assert len(context.lint_tree.find(CursorRuleBlock)) == 1
    assert len(context.lint_tree.find(SkillBlock)) == 1


def test_cursor_forced_missing_manifest(tmp_path):
    context = RepositoryContext(tmp_path, repo_types={RepositoryType.CURSOR_PLUGIN})
    assert CursorPluginValidRule().check(context)


def test_cursor_component_escape(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    plugin = repo / "packages/review"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.mdc").write_text("Do not read this outside the plugin.\n")
    (plugin / "guidance").rename(plugin / "old-guidance")
    (plugin / "guidance").symlink_to(outside, target_is_directory=True)
    context = RepositoryContext(repo)
    assert not context.lint_tree.find(CursorRuleBlock)
    assert CursorPluginValidRule().check(context)


def test_cursor_excluded_catalog_drops_claim(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    # Remove the standalone marker: only the catalog now claims the plugin.
    manifest = repo / "packages/review/.cursor-plugin/plugin.json"
    manifest.unlink()
    context = RepositoryContext(repo, exclude_patterns=[".cursor-plugin"])
    assert not context.cursor_plugin_roots()


def test_cursor_late_excludes_drop_catalog_only_skills(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    manifest = repo / "packages/review/.cursor-plugin/plugin.json"
    manifest.unlink()
    context = RepositoryContext(repo)
    assert context.cursor_plugin_roots()
    context.exclude_patterns.append(".cursor-plugin")
    context.apply_excludes()
    assert not context.cursor_plugin_roots()
    assert not context.lint_tree.find(CursorPluginBlock)
    assert not context.lint_tree.find(SkillBlock)


def test_cursor_dual_manifest_preserves_claude_scope(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    plugin = repo / "packages/review"
    (plugin / ".claude-plugin").mkdir()
    (plugin / ".claude-plugin/plugin.json").write_text('{"name":"review"}')
    context = RepositoryContext(repo)
    assert context.provenance(plugin).ecosystems == frozenset({"claude", "cursor"})
    assert len(context.lint_tree.find(CursorPluginBlock)) == 1
    assert len(context.lint_tree.find(CursorRuleBlock)) == 1
    assert len(context.lint_tree.find(SkillBlock)) == 2


def test_cursor_default_and_root_skill(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    plugin = repo / "packages/review"
    manifest = plugin / ".cursor-plugin/plugin.json"
    manifest.write_text('{"name":"review"}')
    context = RepositoryContext(plugin)
    assert context.skills == [plugin / "skills/ignored"]
    # With no default directory, use the root skill.
    (plugin / "skills").rename(plugin / "unused-skills")
    (plugin / "SKILL.md").write_text((plugin / "capabilities/review/SKILL.md").read_text())
    context = RepositoryContext(plugin)
    assert context.skills == [plugin]
    manifest.write_text('{"name":"review","skills":[]}')
    from skillsaw.utils import invalidate_read_caches

    invalidate_read_caches(manifest)
    assert not RepositoryContext(plugin).skills


def test_cursor_nested_marketplace_and_excluded_component(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    context = RepositoryContext(tmp_path, exclude_patterns=["**/guidance"])
    assert context.cursor_marketplace_paths() == [repo / ".cursor-plugin/marketplace.json"]
    assert not context.lint_tree.find(CursorRuleBlock)
    assert len(context.lint_tree.find(CursorAgentBlock)) == 1


@pytest.mark.parametrize(
    "payload", ["[]", "{", '{"name":null}', '{"name":"ok","variables":{"type":"string"}}']
)
def test_cursor_malformed_manifest(tmp_path, payload):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    (repo / "packages/review/.cursor-plugin/plugin.json").write_text(payload)
    assert CursorPluginValidRule().check(RepositoryContext(repo))


def test_cursor_inline_mcp_array_keeps_every_server(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    path = repo / "packages/review/.cursor-plugin/plugin.json"
    data = json.loads(path.read_text())
    data["mcpServers"] = [{"one": {"command": "first"}}, {"two": {"command": "second"}}]
    path.write_text(json.dumps(data))
    blocks = RepositoryContext(repo).lint_tree.find(McpBlock)
    assert {s.name for block in blocks for s in block.servers} == {"one", "two"}


def test_cursor_project_agents_detected_without_other_components(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    project = tmp_path / "project"
    directory = project / ".cursor/agents"
    directory.mkdir(parents=True)
    (directory / "review.md").write_text(
        (repo / "packages/review/reviewers/security.markdown").read_text()
    )
    context = RepositoryContext(project)
    assert RepositoryType.CURSOR in context.repo_types
    assert len(context.lint_tree.find(CursorAgentBlock)) == 1


def test_cursor_catalog_inline_hooks_keep_source_location(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    context = RepositoryContext(repo)
    hooks = context.lint_tree.find(HooksBlock)
    assert hooks[0].path == repo / ".cursor-plugin/marketplace.json"


@pytest.mark.parametrize(
    "source", ["C:\\outside", "../outside", "/outside", "https://example.com/repo.git"]
)
def test_cursor_source_containment_and_remote_sources(tmp_path, source):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    catalog = repo / ".cursor-plugin/marketplace.json"
    catalog.write_text(
        json.dumps({"name": "catalog", "plugins": [{"name": "one", "source": source}]})
    )
    findings = CursorMarketplaceValidRule().check(RepositoryContext(repo))
    assert bool(findings) == (not source.startswith("https://"))


def test_cursor_plugin_mcp_duplicate_keys_keep_last_value(tmp_path):
    repo = copy_fixture("cursor-plugins/clean", tmp_path)
    path = repo / "packages/review/config/mcp.json"
    path.write_text('{"mcpServers":{"local":{"command":"old","command":"new"}}}')
    blocks = RepositoryContext(repo).lint_tree.find(McpBlock)
    block = next(b for b in blocks if b.path == path)
    assert block.parse_error is None
    assert block.servers[0].command == "new"
