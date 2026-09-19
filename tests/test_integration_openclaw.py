"""Native plugin discovery, isolation and CLI regression coverage."""

import json
import shutil
from pathlib import Path

import pytest

from skillsaw.context import RepositoryContext
from skillsaw.repository_types import RepositoryType
from skillsaw.lint_target import (
    OpenClawPluginConfigNode,
    OpenClawPackageConfigNode,
    OpenClawPluginNode,
)
from skillsaw.blocks import McpBlock
from tests.cli_runner import run_cli

FIXTURES = Path(__file__).parent / "fixtures" / "openclaw"
RULES = "openclaw-manifest-valid,openclaw-package-valid,openclaw-resources"


def copy_fixture(name, tmp_path):
    return Path(shutil.copytree(FIXTURES / name, tmp_path / "repo"))


def lint(repo, *args):
    result = run_cli(
        [
            "lint",
            str(repo),
            "--format",
            "json",
            *[arg for rule in RULES.split(",") for arg in ("--rule", rule)],
            *args,
        ]
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)["violations"]


def test_native_json5_and_declared_skills(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.OPENCLAW_PLUGIN
    assert [p.name for p in context.skills] == ["weather-report"]
    assert context.provenance(repo).ecosystems == frozenset({"openclaw"})
    assert len(context.lint_tree.find(OpenClawPackageConfigNode)) == 1
    assert len(context.lint_tree.find(McpBlock)) == 1
    assert lint(repo) == (0, [])


def test_errors_are_separate_and_file_level(tmp_path):
    repo = copy_fixture("invalid", tmp_path)
    rc, violations = lint(repo)
    assert rc == 1
    assert {v["rule_id"] for v in violations} == set(RULES.split(","))
    assert sum(v["rule_id"] == "openclaw-manifest-valid" for v in violations) == 2
    assert all(not v.get("line") for v in violations)


def test_package_only_requires_native_manifest(tmp_path):
    repo = copy_fixture("package-only", tmp_path)
    rc, violations = lint(repo)
    assert rc == 1
    assert [v["rule_id"] for v in violations] == ["openclaw-manifest-valid"]


def test_forced_type_reports_missing_manifest(tmp_path):
    rc, violations = lint(tmp_path, "--type", "openclaw-plugin")
    assert rc == 1
    assert [v["rule_id"] for v in violations] == ["openclaw-manifest-valid"]


def test_nested_discovery_and_exclusions(tmp_path):
    repo = tmp_path / "project"
    plugin = repo / "packages" / "weather"
    shutil.copytree(FIXTURES / "valid", plugin)
    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.OPENCLAW_PLUGIN
    assert len(context.lint_tree.find(OpenClawPluginNode)) == 1
    assert len(context.skills) == 1
    context = RepositoryContext(repo, exclude_patterns=["packages/**"])
    assert not context.openclaw_plugin_roots()
    assert not context.skills


def test_provenance_survives_unrelated_type_override(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    context = RepositoryContext(repo, repo_types=[RepositoryType.MARKETPLACE])
    assert context.provenance(repo).openclaw
    assert len(context.skills) == 1
    assert len(context.lint_tree.find(OpenClawPackageConfigNode)) == 1


def test_dual_manifest_retains_claude_identity(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    marker = repo / ".claude-plugin"
    marker.mkdir()
    (marker / "plugin.json").write_text('{"name":"weather"}')
    context = RepositoryContext(repo)
    assert context.provenance(repo).ecosystems == frozenset({"openclaw", "claude"})
    assert len(context.skills) == 2
    assert lint(repo) == (0, [])


@pytest.mark.parametrize("name", ["openclaw.plugin.json", "guides"])
def test_external_symlinks_are_not_read(tmp_path, name):
    repo = copy_fixture("valid", tmp_path)
    target = repo / name
    external = tmp_path / "external"
    target.rename(external)
    target.symlink_to(external, target_is_directory=external.is_dir())
    context = RepositoryContext(repo)
    assert not context.skills
    assert lint(repo)[1]


def test_entrypoint_check_is_optional(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    assert lint(repo) == (0, [])
    (repo / ".skillsaw.yaml").write_text(
        "rules:\n  openclaw-resources:\n    check-entrypoints-exist: true\n"
    )
    assert any("dist/index.js" in v["message"] for v in lint(repo)[1])


def test_rules_are_opt_in(tmp_path):
    repo = copy_fixture("invalid", tmp_path)
    result = run_cli(["lint", str(repo), "--format", "json"])
    assert not any(
        v["rule_id"].startswith("openclaw-") for v in json.loads(result.stdout)["violations"]
    )


def test_missing_manifest_without_package(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    (repo / "package.json").unlink()
    assert lint(repo) == (0, [])


@pytest.mark.parametrize(
    "manifest", ["[]", "{", '{"id":42,"configSchema":{}}', '{"id":"NODE-MCP","configSchema":{}}']
)
def test_rejected_manifest_shapes(tmp_path, manifest):
    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text(manifest)
    assert lint(repo)[0] == 1


def test_schema_and_optional_fields_remain_forward_compatible(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text('{"id":"MixedCase","configSchema":{},"future":17}')
    assert lint(repo) == (0, [])
    assert not RepositoryContext(repo).skills


def test_single_skill_root_and_deduplication(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text(
        json.dumps(
            {
                "id": "weather",
                "configSchema": {},
                "skills": ["guides", "guides/weather-report", "guides"],
            }
        )
    )
    assert len(RepositoryContext(repo).skills) == 1


def test_manifest_exclusion_is_respected_with_package_claim(tmp_path):
    repo = copy_fixture("invalid", tmp_path)
    context = RepositoryContext(repo, exclude_patterns=["openclaw.plugin.json"])
    nodes = context.lint_tree.find(OpenClawPluginConfigNode)
    assert all(isinstance(n, OpenClawPackageConfigNode) for n in nodes)


def test_late_directory_exclusion_prunes_tree_and_skills(tmp_path):
    repo = tmp_path / "project"
    shutil.copytree(FIXTURES / "valid", repo / "plugins" / "weather")
    context = RepositoryContext(repo)
    assert context.skills
    context.exclude_patterns.append("plugins/**")
    context.apply_excludes()
    assert not context.openclaw_plugin_roots()
    assert not context.skills
    assert not context.lint_tree.find(OpenClawPluginConfigNode)


def test_mcp_policy_reaches_native_manifest(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    (repo / ".skillsaw.yaml").write_text("rules:\n  mcp-prohibited:\n    enabled: true\n")
    result = run_cli(["lint", str(repo), "--format", "json", "--rule", "mcp-prohibited"])
    assert any(v["rule_id"] == "mcp-prohibited" for v in json.loads(result.stdout)["violations"])
