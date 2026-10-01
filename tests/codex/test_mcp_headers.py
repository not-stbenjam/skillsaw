"""Codex 0.159.3 ignores ``headers`` in HTTP MCP server tables."""

import json

import pytest

from skillsaw.context import RepositoryContext
from skillsaw.rule import Severity
from skillsaw.rules.builtin.codex.mcp_headers import CodexMcpHeadersRule
from tests.cli_runner import run_cli

from ._helpers import copy_fixture


def _check(tmp_path, body, config=None):
    directory = tmp_path / ".codex"
    directory.mkdir()
    (directory / "config.toml").write_text(body, encoding="utf-8")
    return CodexMcpHeadersRule(config).check(RepositoryContext(tmp_path))


@pytest.mark.parametrize("value", ['{ "X-Client" = "release-review" }', "{}", "[]", "false", "42"])
def test_ignored_header_values_warn_without_echoing_them(tmp_path, value):
    findings = _check(
        tmp_path,
        '[mcp_servers.catalog]\nurl = "https://catalog.example.test/mcp"\n' f"headers = {value}\n",
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity is Severity.WARNING
    assert finding.line is None
    assert "MCP server 'catalog'" in finding.message
    assert "'http_headers'" in finding.message
    assert "'env_http_headers'" in finding.message
    assert "release-review" not in finding.message
    assert finding.fixable is False


@pytest.mark.parametrize(
    "extra",
    [
        'http_headers = { "X-Client" = "canonical" }\n',
        "enabled = false\n",
        'type = "stdio"\n',  # Codex ignores type; URL selects HTTP.
    ],
)
def test_other_fields_do_not_hide_an_ignored_header(tmp_path, extra):
    findings = _check(
        tmp_path,
        '[mcp_servers.catalog]\nurl = ""\nheaders = {}\n' + extra,
    )

    assert len(findings) == 1


@pytest.mark.parametrize(
    "body",
    [
        '[mcp_servers.catalog]\nurl = "https://catalog.example.test/mcp"\n'
        'http_headers = { "X-Client" = "release-review" }\n'
        'env_http_headers = { Authorization = "CATALOG_AUTHORIZATION" }\n',
        '[mcp_servers.catalog]\nurl = "https://catalog.example.test/mcp"\nunknown = true\n',
        '[mcp_servers.catalog]\ncommand = "node"\nheaders = {}\n',
        '[mcp_servers.catalog]\ncommand = ""\nurl = "https://example.test"\nheaders = {}\n',
        '[mcp_servers.catalog]\ncommand = []\nurl = "https://example.test"\nheaders = {}\n',
        "[mcp_servers.catalog]\nurl = 42\nheaders = {}\n",
        "[mcp_servers.catalog]\nheaders = {}\n",
        "[mcp_servers]\ncatalog = 42\n",
        "mcp_servers = []\n",
        "headers = {}\n",
        "[mcp_servers.catalog\n",  # Existing syntax owner reports this.
    ],
)
def test_canonical_fields_and_deliberate_shape_omissions_stay_silent(tmp_path, body):
    assert _check(tmp_path, body) == []


def test_diagnostic_sanitizes_server_names_and_never_exposes_header_values(tmp_path):
    findings = _check(
        tmp_path,
        '[mcp_servers."catalog\\nspoof"]\nurl = "https://example.test"\n'
        'headers = { Authorization = "Bearer private-header-value" }\n',
    )

    assert len(findings) == 1
    assert "\n" not in findings[0].message
    assert "private-header-value" not in findings[0].message


@pytest.mark.parametrize("severity", ["info", "error"])
def test_configured_severity_is_respected(tmp_path, severity):
    findings = _check(
        tmp_path,
        '[mcp_servers.catalog]\nurl = "https://example.test"\nheaders = {}\n',
        {"severity": severity},
    )

    assert [v.severity.value for v in findings] == [severity]


@pytest.mark.integration
class TestMcpHeadersCli:
    def test_auto_reports_root_and_nested_project_layers(self, tmp_path):
        repo = copy_fixture("codex/mcp-headers-broken", tmp_path)
        result = run_cli(["lint", str(repo), "--format", "json"])
        report = json.loads(result.stdout)
        findings = [v for v in report["violations"] if v["rule_id"] == "codex-mcp-headers"]

        assert result.returncode == 0
        assert {v["file_path"] for v in findings} == {
            ".codex/config.toml",
            "services/catalog/.codex/config.toml",
        }
        assert all(v["severity"] == "warning" and v["line"] is None for v in findings)
        strict = run_cli(["lint", str(repo), "--rule", "codex-mcp-headers", "--strict"])
        assert strict.returncode == 1

    def test_canonical_fields_and_claude_json_headers_are_accepted(self, tmp_path):
        repo = copy_fixture("codex/mcp-headers-clean", tmp_path)
        result = run_cli(["lint", str(repo), "--rule", "codex-mcp-headers", "--format", "json"])

        assert result.returncode == 0
        assert json.loads(result.stdout)["violations"] == []

    def test_fix_does_not_activate_ignored_headers(self, tmp_path):
        repo = copy_fixture("codex/mcp-headers-broken", tmp_path)
        before = {p: p.read_bytes() for p in repo.rglob("config.toml")}

        result = run_cli(["fix", str(repo), "--rule", "codex-mcp-headers", "--suggest"])

        assert result.returncode == 0
        assert {p: p.read_bytes() for p in before} == before

    def test_excluded_layers_are_not_checked(self, tmp_path):
        repo = copy_fixture("codex/mcp-headers-broken", tmp_path)
        (repo / ".skillsaw.yaml").write_text("exclude:\n  - services/**\n", encoding="utf-8")
        result = run_cli(["lint", str(repo), "--rule", "codex-mcp-headers", "--format", "json"])

        assert result.returncode == 0
        findings = json.loads(result.stdout)["violations"]
        assert [v["file_path"] for v in findings] == [".codex/config.toml"]

    def test_configured_severity_changes_the_cli_exit_code(self, tmp_path):
        repo = copy_fixture("codex/mcp-headers-broken", tmp_path)
        (repo / ".skillsaw.yaml").write_text(
            "rules:\n  codex-mcp-headers:\n    severity: error\n", encoding="utf-8"
        )
        result = run_cli(["lint", str(repo), "--rule", "codex-mcp-headers", "--format", "json"])

        assert result.returncode == 1
        assert {v["severity"] for v in json.loads(result.stdout)["violations"]} == {"error"}
