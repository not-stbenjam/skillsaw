"""
Tests for APM manifest validation rules and detection
"""

from pathlib import Path

from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.config import LinterConfig
from skillsaw.rule import Severity
from skillsaw.rules.builtin.apm import (
    ApmManifestValidRule,
    ApmTargetValidRule,
    ApmTypeValidRule,
    ApmDependenciesValidRule,
    ApmCompilationValidRule,
)


# --- Detection tests ---


def test_detect_apm_yml(temp_dir):
    """apm.yml at root -> APM_PACKAGE"""
    repo = temp_dir / "my-pkg"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: my-pkg\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.APM_PACKAGE


def test_detect_apm_yaml(temp_dir):
    """apm.yaml at root -> APM_PACKAGE"""
    repo = temp_dir / "my-pkg"
    repo.mkdir()
    (repo / "apm.yaml").write_text("name: my-pkg\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.APM_PACKAGE


def test_detect_apm_not_present(temp_dir):
    """No apm.yml -> not APM_PACKAGE"""
    repo = temp_dir / "empty"
    repo.mkdir()

    context = RepositoryContext(repo)
    assert context.repo_type != RepositoryType.APM_PACKAGE


def test_plugin_takes_priority_over_apm(temp_dir):
    """Plugin detection wins when both .claude-plugin and apm.yml exist"""
    repo = temp_dir / "hybrid"
    repo.mkdir()
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin" / "plugin.json").write_text('{"name": "hybrid"}')
    (repo / "apm.yml").write_text("name: hybrid\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.SINGLE_PLUGIN


# --- apm-manifest-valid ---


def test_valid_manifest_passes(temp_dir):
    repo = temp_dir / "valid"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: my-package\nversion: 1.0.0\ndescription: A package\nauthor: Test\nlicense: MIT\n"
    )

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert len(violations) == 0


def test_missing_manifest_fails(temp_dir):
    repo = temp_dir / "no-manifest"
    repo.mkdir()
    # Force APM type detection by creating and removing
    context = RepositoryContext(repo)
    context.repo_type = RepositoryType.APM_PACKAGE

    violations = ApmManifestValidRule().check(context)
    assert len(violations) == 1
    assert "Missing apm.yml" in violations[0].message


def test_invalid_yaml_fails(temp_dir):
    repo = temp_dir / "bad-yaml"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\n  bad indent: true\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert len(violations) == 1
    assert "Invalid YAML" in violations[0].message


def test_missing_name_fails(temp_dir):
    repo = temp_dir / "no-name"
    repo.mkdir()
    (repo / "apm.yml").write_text("version: 1.0.0\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("name" in v.message for v in violations)


def test_missing_version_fails(temp_dir):
    repo = temp_dir / "no-version"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("version" in v.message for v in violations)


def test_non_semver_version_fails(temp_dir):
    repo = temp_dir / "bad-ver"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: latest\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("semver" in v.message for v in violations)
    v = [v for v in violations if "semver" in v.message][0]
    assert v.line == 2


def test_semver_with_prerelease_passes(temp_dir):
    repo = temp_dir / "prerelease"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0-beta.1\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert len(violations) == 0


def test_name_non_string_fails(temp_dir):
    repo = temp_dir / "bad-name"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: 123\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("'name' must be a string" in v.message for v in violations)


def test_description_non_string_fails(temp_dir):
    repo = temp_dir / "bad-desc"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ndescription: 123\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("description" in v.message and "string" in v.message for v in violations)


def test_author_non_string_fails(temp_dir):
    repo = temp_dir / "bad-author"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\nauthor: 123\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("author" in v.message and "string" in v.message for v in violations)


def test_license_non_string_fails(temp_dir):
    repo = temp_dir / "bad-license"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\nlicense: 123\n")

    context = RepositoryContext(repo)
    violations = ApmManifestValidRule().check(context)
    assert any("license" in v.message and "string" in v.message for v in violations)


# --- apm-target-valid ---


def test_valid_target_string(temp_dir):
    repo = temp_dir / "target-str"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntarget: claude\n")

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert len(violations) == 0


def test_valid_target_list(temp_dir):
    repo = temp_dir / "target-list"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntarget:\n  - claude\n  - vscode\n")

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert len(violations) == 0


def test_invalid_target_fails(temp_dir):
    repo = temp_dir / "bad-target"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntarget: invalid\n")

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert len(violations) == 1
    assert "Unknown target" in violations[0].message


def test_invalid_target_in_list_fails(temp_dir):
    repo = temp_dir / "bad-target-list"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ntarget:\n  - claude\n  - invalid\n"
    )

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert any("Unknown target" in v.message and "invalid" in v.message for v in violations)


def test_all_target_combined_fails(temp_dir):
    repo = temp_dir / "all-combined"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ntarget:\n  - all\n  - claude\n"
    )

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert any("cannot be combined" in v.message for v in violations)


def test_target_wrong_type_fails(temp_dir):
    repo = temp_dir / "target-wrong-type"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntarget: 123\n")

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert any("string or list" in v.message for v in violations)


def test_no_target_passes(temp_dir):
    repo = temp_dir / "no-target"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    violations = ApmTargetValidRule().check(context)
    assert len(violations) == 0


# --- apm-type-valid ---


def test_valid_type(temp_dir):
    repo = temp_dir / "type-valid"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntype: skill\n")

    context = RepositoryContext(repo)
    violations = ApmTypeValidRule().check(context)
    assert len(violations) == 0


def test_invalid_type_fails(temp_dir):
    repo = temp_dir / "type-bad"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntype: custom\n")

    context = RepositoryContext(repo)
    violations = ApmTypeValidRule().check(context)
    assert len(violations) == 1
    assert "Unknown type" in violations[0].message


def test_type_non_string_fails(temp_dir):
    repo = temp_dir / "type-int"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ntype: 123\n")

    context = RepositoryContext(repo)
    violations = ApmTypeValidRule().check(context)
    assert any("string" in v.message for v in violations)


def test_no_type_passes(temp_dir):
    repo = temp_dir / "no-type"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    violations = ApmTypeValidRule().check(context)
    assert len(violations) == 0


# --- apm-dependencies-valid ---


def test_valid_apm_deps_string_form(temp_dir):
    repo = temp_dir / "deps-str"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  apm:\n    - microsoft/apm-sample\n    - owner/repo#v1.0.0\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert len(violations) == 0


def test_valid_apm_deps_object_form(temp_dir):
    repo = temp_dir / "deps-obj"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  apm:\n"
        "    - git: https://github.com/owner/repo.git\n"
        "      ref: v1.0.0\n"
        "      alias: my-dep\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert len(violations) == 0


def test_apm_dep_object_missing_git_and_path_fails(temp_dir):
    repo = temp_dir / "deps-no-git"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  apm:\n"
        "    - ref: v1.0.0\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("'git' or 'path'" in v.message for v in violations)


def test_apm_dep_object_with_path_passes(temp_dir):
    repo = temp_dir / "deps-path"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  apm:\n"
        "    - path: ./packages/my-skills\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert len(violations) == 0


def test_apm_dep_invalid_alias_fails(temp_dir):
    repo = temp_dir / "deps-bad-alias"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  apm:\n"
        "    - git: https://github.com/owner/repo.git\n"
        "      alias: invalid alias!\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("alias" in v.message for v in violations)


def test_apm_deps_not_list_fails(temp_dir):
    repo = temp_dir / "deps-not-list"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ndependencies:\n  apm: not-a-list\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("list" in v.message and "apm" in v.message for v in violations)


def test_valid_mcp_deps_string_form(temp_dir):
    repo = temp_dir / "mcp-str"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n    - io.github.github/github-mcp-server\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert len(violations) == 0


def test_valid_mcp_deps_object_form(temp_dir):
    repo = temp_dir / "mcp-obj"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: my-server\n"
        "      transport: stdio\n"
        "      command: npx my-server\n"
        "      registry: false\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert len(violations) == 0


def test_mcp_dep_missing_name_fails(temp_dir):
    repo = temp_dir / "mcp-no-name"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - transport: stdio\n"
        "      command: npx server\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("name" in v.message for v in violations)


def test_mcp_dep_invalid_transport_fails(temp_dir):
    repo = temp_dir / "mcp-bad-transport"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      transport: grpc\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("transport" in v.message for v in violations)


def test_mcp_self_defined_no_transport_fails(temp_dir):
    repo = temp_dir / "mcp-no-transport"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      registry: false\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("requires 'transport'" in v.message for v in violations)


def test_mcp_stdio_missing_command_fails(temp_dir):
    repo = temp_dir / "mcp-no-cmd"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      transport: stdio\n"
        "      registry: false\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("stdio" in v.message and "command" in v.message for v in violations)


def test_mcp_http_missing_url_fails(temp_dir):
    repo = temp_dir / "mcp-no-url"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      transport: http\n"
        "      registry: false\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("http" in v.message and "url" in v.message for v in violations)


def test_mcp_sse_missing_url_fails(temp_dir):
    repo = temp_dir / "mcp-sse-no-url"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      transport: sse\n"
        "      registry: false\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("sse" in v.message and "url" in v.message for v in violations)


def test_mcp_invalid_package_fails(temp_dir):
    repo = temp_dir / "mcp-bad-pkg"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      package: brew\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("package" in v.message for v in violations)


def test_mcp_env_not_dict_fails(temp_dir):
    repo = temp_dir / "mcp-bad-env"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      env: not-a-map\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("env" in v.message and "mapping" in v.message for v in violations)


def test_mcp_tools_not_list_fails(temp_dir):
    repo = temp_dir / "mcp-bad-tools"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "dependencies:\n  mcp:\n"
        "    - name: server\n"
        "      tools: not-a-list\n"
    )

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("tools" in v.message and "list" in v.message for v in violations)


def test_dependencies_not_dict_fails(temp_dir):
    repo = temp_dir / "deps-not-dict"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ndependencies: bad\n")

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert any("mapping" in v.message for v in violations)


def test_no_dependencies_passes(temp_dir):
    repo = temp_dir / "no-deps"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    violations = ApmDependenciesValidRule().check(context)
    assert len(violations) == 0


# --- apm-compilation-valid ---


def test_valid_compilation(temp_dir):
    repo = temp_dir / "comp-valid"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\n"
        "compilation:\n"
        "  strategy: single-file\n"
        "  output: AGENTS.md\n"
        "  target: claude\n"
        "  resolve_links: true\n"
        "  source_attribution: false\n"
        "  exclude:\n    - '*.draft.md'\n"
        "  placement:\n"
        "    min_instructions_per_file: 3\n"
    )

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert len(violations) == 0


def test_invalid_compilation_strategy_fails(temp_dir):
    repo = temp_dir / "comp-bad-strat"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ncompilation:\n  strategy: merged\n"
    )

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert any("strategy" in v.message for v in violations)


def test_compilation_not_dict_fails(temp_dir):
    repo = temp_dir / "comp-bad"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\ncompilation: bad\n")

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert any("mapping" in v.message for v in violations)


def test_compilation_invalid_target_fails(temp_dir):
    repo = temp_dir / "comp-bad-target"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ncompilation:\n  target: invalid\n"
    )

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert any("target" in v.message for v in violations)


def test_compilation_resolve_links_non_bool_fails(temp_dir):
    repo = temp_dir / "comp-bad-resolve"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ncompilation:\n  resolve_links: maybe\n"
    )

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert any("resolve_links" in v.message and "boolean" in v.message for v in violations)


def test_compilation_exclude_not_list_fails(temp_dir):
    repo = temp_dir / "comp-bad-exclude"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ncompilation:\n  exclude: not-a-list\n"
    )

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert any("exclude" in v.message and "list" in v.message for v in violations)


def test_compilation_placement_not_dict_fails(temp_dir):
    repo = temp_dir / "comp-bad-placement"
    repo.mkdir()
    (repo / "apm.yml").write_text(
        "name: test\nversion: 1.0.0\ncompilation:\n  placement: bad\n"
    )

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert any("placement" in v.message and "mapping" in v.message for v in violations)


def test_no_compilation_passes(temp_dir):
    repo = temp_dir / "no-comp"
    repo.mkdir()
    (repo / "apm.yml").write_text("name: test\nversion: 1.0.0\n")

    context = RepositoryContext(repo)
    violations = ApmCompilationValidRule().check(context)
    assert len(violations) == 0


# --- Config defaults ---


def test_apm_rules_default_to_auto():
    config = LinterConfig.default()
    for rule_id in [
        "apm-manifest-valid",
        "apm-target-valid",
        "apm-type-valid",
        "apm-dependencies-valid",
        "apm-compilation-valid",
    ]:
        assert config.get_rule_config(rule_id).get("enabled") == "auto"


def test_apm_manifest_valid_default_severity():
    rule = ApmManifestValidRule()
    assert rule.default_severity() == Severity.ERROR


def test_apm_compilation_default_severity():
    rule = ApmCompilationValidRule()
    assert rule.default_severity() == Severity.WARNING


# --- Scaffolding ---


def test_add_apm_creates_manifest(temp_dir):
    from skillsaw.marketplace.add import add_apm

    result = add_apm(
        path=temp_dir,
        name="test-pkg",
        version="1.2.3",
        description="Test package",
        author="Test Author",
        license_id="MIT",
        target="claude",
    )

    assert result.exists()
    content = result.read_text()
    assert "name: test-pkg" in content
    assert "version: 1.2.3" in content
    assert "description: Test package" in content
    assert "author: Test Author" in content
    assert "license: MIT" in content
    assert "target: claude" in content


def test_add_apm_defaults(temp_dir):
    from skillsaw.marketplace.add import add_apm

    result = add_apm(path=temp_dir)

    assert result.exists()
    content = result.read_text()
    assert "version: 0.1.0" in content
    assert "TODO" in content


def test_add_apm_already_exists_fails(temp_dir):
    import pytest
    from skillsaw.marketplace.add import add_apm

    (temp_dir / "apm.yml").write_text("name: existing\n")

    with pytest.raises(FileExistsError):
        add_apm(path=temp_dir)
