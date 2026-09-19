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


@pytest.mark.parametrize("prefix", ["packages", ".openclaw/extensions"])
def test_nested_discovery_and_exclusions(tmp_path, prefix):
    repo = tmp_path / "project"
    plugin = repo / prefix / "weather"
    shutil.copytree(FIXTURES / "valid", plugin)
    context = RepositoryContext(repo)
    assert context.repo_type == RepositoryType.OPENCLAW_PLUGIN
    assert len(context.lint_tree.find(OpenClawPluginNode)) == 1
    assert len(context.skills) == 1
    context = RepositoryContext(repo, exclude_patterns=[f"{prefix}/**"])
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
    assert all(path.is_relative_to(repo) for path in context.skills)
    if name == "guides":
        assert not context.skills
        expected = ("openclaw-resources", "escapes the plugin directory")
    else:
        assert {path.name for path in context.skills} == {"weather-report", "inactive"}
        expected = ("openclaw-manifest-valid", "Manifest escapes the plugin directory")
    assert any(v["rule_id"] == expected[0] and expected[1] in v["message"] for v in lint(repo)[1])


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
    assert [path.name for path in RepositoryContext(repo).skills] == ["weather-report"]


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
    assert not nodes
    assert len(context.lint_tree.find(OpenClawPackageConfigNode)) == 1


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


@pytest.mark.parametrize("prefix", [""])
def test_native_claim_preserves_other_hosts_and_portable_skills(tmp_path, prefix):
    repo = tmp_path / "repo"
    plugin = repo / prefix
    shutil.copytree(FIXTURES / "mixed", plugin)
    context = RepositoryContext(repo)
    assert {p.name for p in context.skills} == {
        "claude-weather",
        "shared-weather",
        "portable-weather",
    }
    assert RepositoryType.AGENTSKILLS in context.repo_types
    assert plugin in context.openclaw_plugin_roots()


@pytest.mark.parametrize(
    "metadata, claimed",
    [
        ({"extensions": ["index.ts"]}, True),
        (None, False),
        ({}, False),
        ({"hooks": ["hooks"]}, False),
    ],
)
def test_package_evidence_preserves_portable_skills(tmp_path, metadata, claimed):
    repo = copy_fixture("package-only", tmp_path)
    shutil.copytree(
        FIXTURES / "valid" / "guides" / "weather-report", repo / "skills" / "weather-report"
    )
    (repo / "package.json").write_text(json.dumps({"openclaw": metadata}))
    context = RepositoryContext(repo)
    assert [p.name for p in context.skills] == ["weather-report"]
    assert context.provenance(repo).openclaw is claimed


@pytest.mark.parametrize(
    "prefix",
    ['{"id":"weather","configSchema":{},"padding":"', "{id:'weather',configSchema:{},padding:'"],
)
def test_manifest_byte_limit_rejects_before_json5(tmp_path, monkeypatch, prefix):
    from skillsaw.formats import openclaw

    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text(prefix + "é" * (openclaw.MAX_MANIFEST_BYTES // 2))

    def unexpected_parse(*args, **kwargs):
        pytest.fail("oversized manifests must not reach JSON5")

    monkeypatch.setattr(openclaw.json5, "loads", unexpected_parse)
    rc, violations = lint(repo)
    assert rc == 1
    assert any(
        v["rule_id"] == "openclaw-manifest-valid" and "262144-byte limit" in v["message"]
        for v in violations
    )


def test_jsonc_fast_path_and_exact_byte_limit(tmp_path, monkeypatch):
    from skillsaw.formats import openclaw

    path = tmp_path / openclaw.MANIFEST
    content = '// comment\n{"id":"weather","configSchema":{},}'
    path.write_text(content + " " * (openclaw.MAX_MANIFEST_BYTES - len(content)))

    def unexpected_parse(*args, **kwargs):
        pytest.fail("JSONC must not reach JSON5")

    monkeypatch.setattr(openclaw.json5, "loads", unexpected_parse)
    assert openclaw.read_manifest(path) == ({"id": "weather", "configSchema": {}}, None)


def test_mcp_normalization_matches_native_loader_boundary(tmp_path):
    from skillsaw.formats.openclaw import inline_mcp_servers

    repo = copy_fixture("valid", tmp_path)
    manifest = {
        "id": "weather",
        "configSchema": {},
        "mcpServers": {
            " weather ": {"command": "weather"},
            "__proto__": {"command": "ignored"},
            "prototype": {"command": "ignored"},
            "constructor": {"command": "ignored"},
            " ": {"command": "ignored"},
            "bad": 4,
        },
    }
    (repo / "openclaw.plugin.json").write_text(json.dumps(manifest))
    assert inline_mcp_servers(repo) == {"weather": {"command": "weather"}}
    assert len(RepositoryContext(repo).lint_tree.find(McpBlock)) == 1


@pytest.mark.parametrize(
    "package, message",
    [
        ("{", "Invalid package.json"),
        ("[]", "expected an object"),
        ('{"openclaw":42}', "'openclaw' must be an object"),
        ('{"openclaw":{"extensions":[42]}}', "array of non-empty strings"),
        ('{"openclaw":{"extensions":[]}}', "empty extension list"),
        ('{"openclaw":{"extensions":["../outside.js"]}}', "escapes the plugin directory"),
    ],
)
def test_package_diagnostics(tmp_path, package, message):
    repo = copy_fixture("valid", tmp_path)
    (repo / "package.json").write_text(package)
    assert any(message in v["message"] for v in lint(repo)[1])


def test_config_activation_and_optional_skill_existence(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text(
        '{"id":"weather","configSchema":{},"skills":["missing"]}'
    )
    (repo / ".skillsaw.yaml").write_text(
        "rules:\n  openclaw-resources:\n    enabled: true\n    check-skills-exist: false\n"
    )
    result = run_cli(["lint", str(repo), "--format", "json"])
    assert not any(
        v["rule_id"] == "openclaw-resources" for v in json.loads(result.stdout)["violations"]
    )
    (repo / "openclaw.plugin.json").write_text('{"id":"weather","configSchema":{},"skills":42}')
    result = run_cli(["lint", str(repo), "--format", "json"])
    assert any(
        v["rule_id"] == "openclaw-resources" and "must be an array" in v["message"]
        for v in json.loads(result.stdout)["violations"]
    )


def test_nested_package_claim_preserves_portable_skill(tmp_path):
    repo = tmp_path / "repo"
    plugin = repo / "packages" / "weather"
    shutil.copytree(FIXTURES / "package-only", plugin)
    shutil.copytree(
        FIXTURES / "valid" / "guides" / "weather-report", plugin / "skills" / "weather-report"
    )
    context = RepositoryContext(repo)
    assert [p.name for p in context.skills] == ["weather-report"]
    assert plugin in context.openclaw_plugin_roots()


def test_native_claim_preserves_root_skill(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    shutil.copyfile(repo / "guides/weather-report/SKILL.md", repo / "SKILL.md")
    assert repo in RepositoryContext(repo).skills


def test_dual_agent_plugin_container_retains_identity(tmp_path):
    from skillsaw.lint_target import AgentPluginNode

    root = tmp_path / "project"
    repo = root / "plugins" / "weather"
    shutil.copytree(FIXTURES / "valid", repo)
    (repo / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/v1/plugin.schema.json","name":"weather"}'
    )
    context = RepositoryContext(root)
    assert context.provenance(repo).ecosystems == frozenset({"openclaw", "agent-plugin"})
    assert len(context.lint_tree.find(AgentPluginNode)) == 1
    assert len(context.lint_tree.find(OpenClawPluginConfigNode)) == 1


def test_multi_root_counts_native_plugins(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    shutil.copytree(FIXTURES / "valid", first)
    shutil.copytree(FIXTURES / "valid", second)
    result = run_cli(
        ["lint", str(first), str(second), "--format", "json", "--rule", "openclaw-manifest-valid"]
    )
    data = json.loads(result.stdout)
    assert data["stats"]["plugins"] == 2


def test_tightened_excludes_do_not_reprobe_ordinary_packages(tmp_path, monkeypatch):
    from skillsaw.discovery import openclaw

    repo = copy_fixture("valid", tmp_path)
    ordinary = repo / "packages" / "ordinary"
    ordinary.mkdir(parents=True)
    (ordinary / "package.json").write_text('{"name":"ordinary"}')
    context = RepositoryContext(repo)
    assert context.openclaw_plugin_roots() == [repo]
    original = openclaw.declares_extensions

    def probe(path):
        assert path.parent != ordinary, "negative package evidence must survive tighter exclusions"
        return original(path)

    monkeypatch.setattr(openclaw, "declares_extensions", probe)
    context.exclude_patterns.append("dist/**")
    assert context.openclaw_plugin_roots() == [repo]


def test_relaxed_excludes_rediscover_native_package_roots(tmp_path):
    repo = copy_fixture("package-only", tmp_path)
    context = RepositoryContext(repo, exclude_patterns=["package.json"])
    assert not context.openclaw_plugin_roots()
    context.exclude_patterns.clear()
    assert context.openclaw_plugin_roots() == [repo]
    context.exclude_patterns.append("package.json")
    assert not context.openclaw_plugin_roots()


@pytest.mark.parametrize("outside", [False, True])
def test_package_evidence_symlink_containment(tmp_path, outside):
    from skillsaw.discovery.openclaw import discover_plugins

    repo = copy_fixture("package-only", tmp_path)
    package = repo / "package.json"
    target = (tmp_path if outside else repo) / "metadata.json"
    package.rename(target)
    package.symlink_to(target)
    assert discover_plugins([], [package], lambda _: False) == ([] if outside else [repo])


@pytest.mark.parametrize("terminator", ["\n", "\r", "\u2028", "\u2029"])
def test_json5_line_comments_preserve_mcp_policy(tmp_path, terminator):
    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text(
        '{"id":"weather","configSchema":{},// comment'
        + terminator
        + '"mcpServers":{"weather":{"command":"echo"}}\n}'
    )
    result = run_cli(["lint", str(repo), "--format", "json", "--rule", "mcp-prohibited"])
    assert result.returncode == 1, result.stderr
    assert [v["rule_id"] for v in json.loads(result.stdout)["violations"]] == ["mcp-prohibited"]


def test_unterminated_json5_block_comment_is_rejected(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    (repo / "openclaw.plugin.json").write_text('{"id":"weather","configSchema":{}} /* unfinished')
    rc, violations = lint(repo)
    assert rc == 1
    assert any(
        v["rule_id"] == "openclaw-manifest-valid" and "Cannot parse JSON5" in v["message"]
        for v in violations
    )


def test_explicit_plugin_root_keeps_declared_skills_child(tmp_path):
    repo = copy_fixture("declared-root", tmp_path)
    assert RepositoryContext(repo).skills == [repo / "skills"]
    result = run_cli(["lint", str(repo), "--format", "json", "--rule", "agentskill-name"])
    assert result.returncode == 1, result.stderr
    assert any(v["rule_id"] == "agentskill-name" for v in json.loads(result.stdout)["violations"])


@pytest.mark.parametrize("output_format", ["json", "sarif", "text"])
@pytest.mark.parametrize("resource", ["skill", "entrypoint", "escape"])
def test_resource_diagnostics_redact_url_credentials(tmp_path, output_format, resource):
    repo = copy_fixture("valid", tmp_path)
    value = "https://reader:credential-canary@private.example.org/resource"
    manifest = {"id": "weather", "configSchema": {}}
    if resource == "entrypoint":
        (repo / "package.json").write_text(json.dumps({"openclaw": {"extensions": [value]}}))
        (repo / ".skillsaw.yaml").write_text(
            "rules:\n  openclaw-resources:\n    check-entrypoints-exist: true\n"
        )
    else:
        manifest["skills"] = [("/" if resource == "escape" else "") + value]
    (repo / "openclaw.plugin.json").write_text(json.dumps(manifest))
    result = run_cli(["lint", str(repo), "--format", output_format, "--rule", "openclaw-resources"])
    assert result.stdout, result.stderr
    assert "credential-canary" not in result.stdout
    assert "[redacted]" in result.stdout


def test_oversized_resource_values_have_bounded_diagnostics(tmp_path):
    repo = copy_fixture("valid", tmp_path)
    value = "https://reader:" + "credential" * 1000 + "@private.example.org/resource"
    (repo / "openclaw.plugin.json").write_text(
        json.dumps({"id": "weather", "configSchema": {}, "skills": [value]})
    )
    violations = lint(repo)[1]
    assert len(violations) == 1
    assert "credential" not in violations[0]["message"]
    assert len(violations[0]["message"]) < 650


@pytest.mark.parametrize("credential_url", [False, True])
def test_native_mcp_shape_deferral_retains_credential_checks(tmp_path, credential_url):
    repo = copy_fixture("valid", tmp_path)
    url = (
        "https://example.org/mcp"
        if not credential_url
        else "https://user:credential-canary@example.org/mcp"
    )
    (repo / "openclaw.plugin.json").write_text(
        json.dumps(
            {
                "id": "weather",
                "configSchema": {},
                "mcpServers": {"weather": {"type": "native-host-field", "url": url}},
            }
        )
    )
    result = run_cli(["lint", str(repo), "--format", "json", "--rule", "mcp-valid-json"])
    assert result.stdout, result.stderr
    violations = json.loads(result.stdout)["violations"]
    if credential_url:
        assert len(violations) == 1
        assert violations[0]["rule_id"] == "mcp-valid-json"
        assert "credential-canary" not in result.stdout
    else:
        assert violations == []


@pytest.mark.parametrize(
    "name, retained",
    [
        ("0", True),
        ("1", True),
        ("4294967294", True),
        ("4294967295", False),
        ("01", False),
        ("-0", False),
        ("１", False),
    ],
)
def test_mcp_name_collisions_follow_host_property_order(tmp_path, name, retained):
    from skillsaw.formats.openclaw import inline_mcp_servers

    repo = copy_fixture("valid", tmp_path)
    credential_url = "https://user:credential-canary@example.org/mcp"
    clean_url = "https://example.org/mcp"
    (repo / "openclaw.plugin.json").write_text(
        json.dumps(
            {
                "id": "weather",
                "configSchema": {},
                "mcpServers": {" " + name + " ": {"url": credential_url}, name: {"url": clean_url}},
            }
        )
    )
    assert inline_mcp_servers(repo)[name]["url"] == (credential_url if retained else clean_url)
    result = run_cli(["lint", str(repo), "--format", "json", "--rule", "mcp-valid-json"])
    violations = json.loads(result.stdout)["violations"]
    assert len(violations) == int(retained)
    assert "credential-canary" not in result.stdout


@pytest.mark.parametrize(
    "content, claimed",
    [
        (b'{"\\u006fpenclaw":{"extensions":["index.js"]}}', True),
        (b'{"name":"ordinary"}', False),
        (b"\xff", False),
    ],
)
def test_package_probe_handles_escaped_keys_and_invalid_utf8(tmp_path, content, claimed):
    repo = copy_fixture("package-only", tmp_path)
    (repo / "package.json").write_bytes(content)
    assert RepositoryContext(repo).provenance(repo).openclaw is claimed


def test_oversized_package_probe_is_bounded_and_reported(tmp_path, monkeypatch):
    from skillsaw.formats import openclaw
    from skillsaw.discovery.openclaw import declares_extensions

    repo = copy_fixture("valid", tmp_path)
    package = repo / "package.json"
    with package.open("wb") as stream:
        stream.write(b'{"openclaw":{"extensions":[]},"padding":"')
        stream.seek(openclaw.MAX_PACKAGE_BYTES)
        stream.write(b'"}')

    def unexpected_json(*args, **kwargs):
        pytest.fail("oversized packages must not reach the JSON parser")

    monkeypatch.setattr(openclaw.json, "loads", unexpected_json)
    assert openclaw.read_package(package)[1].endswith("16777216-byte limit")
    assert not declares_extensions(package)
    monkeypatch.undo()
    assert any(
        v["rule_id"] == "openclaw-package-valid" and "16777216-byte limit" in v["message"]
        for v in lint(repo)[1]
    )


def test_package_probe_reads_metadata_after_initial_chunk(tmp_path):
    repo = copy_fixture("package-only", tmp_path)
    (repo / "package.json").write_text(
        json.dumps({"padding": "x" * (64 * 1024), "openclaw": {"extensions": ["index.js"]}})
    )
    assert RepositoryContext(repo).provenance(repo).openclaw


@pytest.mark.parametrize("nested", [False, True])
def test_cursor_and_openclaw_share_plugin_without_losing_configs(tmp_path, nested):
    from skillsaw.blocks.cursor import CursorPluginBlock

    repo = tmp_path / "repo"
    plugin = repo / "packages" / "weather" if nested else repo
    shutil.copytree(FIXTURES / "valid", plugin)
    marker = plugin / ".cursor-plugin"
    marker.mkdir()
    (marker / "plugin.json").write_text(
        json.dumps(
            {
                "name": "weather",
                "skills": "guides",
                "mcpServers": {"cursor-weather": {"command": "echo"}},
            }
        )
    )
    context = RepositoryContext(repo)
    assert context.provenance(plugin).ecosystems == frozenset({"cursor", "openclaw"})
    assert len(context.lint_tree.find(CursorPluginBlock)) == 1
    assert len(context.lint_tree.find(OpenClawPluginConfigNode)) == 1
    assert len(context.lint_tree.find(McpBlock)) == 2
    assert plugin / "guides" / "weather-report" in context.skills
    result = run_cli(["lint", str(repo), "--format", "json", "--rule", "mcp-prohibited"])
    assert result.returncode == 1, result.stderr
    assert len(json.loads(result.stdout)["violations"]) == 2
    context.exclude_patterns.append(marker.relative_to(repo).as_posix() + "/**")
    context.apply_excludes()
    assert plugin / "guides" / "weather-report" in context.skills
    assert len(context.lint_tree.find(OpenClawPluginConfigNode)) == 1
    assert not context.lint_tree.find(CursorPluginBlock)


def test_multi_root_counts_cursor_and_openclaw_plugins(tmp_path):
    native = copy_fixture("valid", tmp_path)
    cursor = tmp_path / "cursor"
    shutil.copytree(FIXTURES.parent / "cursor-plugins" / "clean", cursor)
    result = run_cli(
        ["lint", str(native), str(cursor), "--format", "json", "--rule", "openclaw-manifest-valid"]
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["stats"]["plugins"] == 2


def test_declared_skill_stat_errors_become_diagnostics(tmp_path, monkeypatch):
    import errno

    repo = copy_fixture("valid", tmp_path)
    original = Path.is_dir
    calls = []

    def is_dir(path):
        if path == repo / "guides":
            calls.append(path)
            raise OSError(errno.ENAMETOOLONG, "File name too long")
        return original(path)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    _, violations = lint(repo)
    assert calls
    assert any(
        v["rule_id"] == "openclaw-resources" and "not an existing skill directory" in v["message"]
        for v in violations
    )


@pytest.mark.parametrize("nested", [False, True])
def test_pi_and_openclaw_preserve_native_and_portable_skill_roles(tmp_path, nested):
    from skillsaw.blocks import SkillBlock
    from skillsaw.blocks.pi import PiPackageBlock, PiSkillBlock

    repo = tmp_path / "repo"
    plugin = repo / "packages" / "weather" if nested else repo
    shutil.copytree(FIXTURES / "valid", plugin)
    package = json.loads((plugin / "package.json").read_text())
    package["pi"] = {"skills": ["guides", "flat.md"]}
    (plugin / "package.json").write_text(json.dumps(package))
    (plugin / "flat.md").write_text(
        "---\nname: forecast\ndescription: Summarize the weather forecast.\n---\nRead the supplied forecast and report expected rain.\n"
    )
    context = RepositoryContext(repo)
    assert context.provenance(plugin).ecosystems == frozenset({"pi", "openclaw"})
    assert len(context.lint_tree.find(PiPackageBlock)) == 1
    assert len(context.lint_tree.find(OpenClawPluginConfigNode)) == 1
    assert plugin / "guides" / "weather-report" / "SKILL.md" in {
        b.path for b in context.lint_tree.find(SkillBlock)
    }
    assert [b.path for b in context.lint_tree.find(PiSkillBlock)] == [plugin / "flat.md"]
    result = run_cli(
        [
            "lint",
            str(repo),
            "--format",
            "json",
            "--rule",
            "openclaw-manifest-valid",
            "--rule",
            "pi-config-valid",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["violations"] == []
