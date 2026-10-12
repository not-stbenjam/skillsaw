"""Codex 0.162.1 selection and raw-byte loader regressions."""

import json
from pathlib import Path

import pytest

from skillsaw.blocks import AgentsMdBlock, ContentBlock
from skillsaw.codex_instructions import CodexInstructionsNode
from skillsaw.config import LinterConfig
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.formats.codex_instructions import CodexInstructionOptions, instruction_bytes
from skillsaw.linter import Linter
from skillsaw.rule import Severity
from tests.cli_runner import run_cli


def project(tmp_path, files, **options):
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    context = RepositoryContext(root, codex_instructions=CodexInstructionOptions(**options))
    return context, context.lint_tree.find(CodexInstructionsNode)[0].report(context.lint_tree)


@pytest.mark.parametrize("empty", [b"", b" \r\n\t", "\u2003"])
def test_empty_override_shadows_standard_and_fallback_without_charge(tmp_path, empty):
    _, report = project(
        tmp_path,
        {
            "AGENTS.override.md": empty,
            "AGENTS.md": "not selected",
            "TEAM.md": "not selected either",
            "child/AGENTS.md": "child",
        },
        cwd="child",
        project_doc_fallback_filenames=("TEAM.md",),
    )
    assert [e["path"] for e in report["selected"]] == ["AGENTS.override.md", "child/AGENTS.md"]
    assert [e["status"] for e in report["selected"]] == ["empty", "loaded"]
    assert report["charged_bytes"] == 5
    assert report["separator_bytes"] == 0


def test_fallback_order_empty_standard_and_directory_candidates(tmp_path):
    context, report = project(
        tmp_path,
        {
            "AGENTS.override.md/directory.txt": "not a regular file",
            "AGENTS.md": "",
            "TEAM.md": "shadowed",
            "child/SECOND.md": "second choice",
            "child/FIRST.md": "first choice",
        },
        cwd="child",
        project_doc_fallback_filenames=("FIRST.md", "SECOND.md"),
    )
    assert [e["path"] for e in report["selected"]] == ["AGENTS.md", "child/FIRST.md"]
    assert any(b.path.name == "FIRST.md" for b in context.lint_tree.find(ContentBlock))


def test_root_to_cwd_excludes_siblings_deeper_and_above_root(tmp_path):
    (tmp_path / "AGENTS.md").write_text("outside scope")
    _, report = project(
        tmp_path,
        {
            "AGENTS.md": "root",
            "a/AGENTS.override.md": "override",
            "a/AGENTS.md": "shadowed",
            "a/b/AGENTS.md": "cwd",
            "a/b/deeper/AGENTS.md": "deeper",
            "sibling/AGENTS.md": "sibling",
        },
        cwd="a/b",
    )
    assert [e["path"] for e in report["selected"]] == [
        "AGENTS.md",
        "a/AGENTS.override.md",
        "a/b/AGENTS.md",
    ]
    assert report["charged_bytes"] == 15
    assert report["rendered_project_bytes"] == 19


@pytest.mark.parametrize(
    "data,limit,charged,text,status,truncated",
    [
        (b"hello", 5, 5, 5, "loaded", False),
        ("éé".encode(), 3, 3, 5, "truncated", True),
        ("😀".encode(), 1, 1, 3, "truncated", True),
        (b"A\xffB", 3, 3, 5, "loaded", False),
        (b"\xef\xbb\xbfA\r\n", 6, 6, 6, "loaded", False),
        (b"   text", 3, 0, 0, "empty", True),
        (b"\x1c", 1, 1, 1, "loaded", False),
        (b"anything", 0, 0, 0, "omitted", False),
    ],
)
def test_raw_bytes_lossy_utf8_and_rust_whitespace(data, limit, charged, text, status, truncated):
    result = instruction_bytes(data, limit)
    assert (result.charged_bytes, result.text_bytes, result.status, result.truncated) == (
        charged,
        text,
        status,
        truncated,
    )


def test_whitespace_prefix_does_not_exhaust_child_budget(tmp_path):
    _, report = project(
        tmp_path,
        {"AGENTS.md": "   hidden", "child/AGENTS.md": "child"},
        cwd="child",
        project_doc_max_bytes=3,
    )
    assert [e["charged_bytes"] for e in report["selected"]] == [0, 3]
    assert report["affected_paths"] == ["AGENTS.md", "child/AGENTS.md"]


def test_project_layers_merge_before_validation_and_apply_to_entire_chain(tmp_path):
    _, report = project(
        tmp_path,
        {
            ".codex/config.toml": 'project_doc_max_bytes = "shadowed"\nproject_doc_fallback_filenames = ["ROOT.md"]\n',
            "child/.codex/config.toml": 'project_doc_max_bytes = 7\nproject_doc_fallback_filenames = [" TEAM.md ", "TEAM.md", "AGENTS.md", "../outside.md", ""]\n',
            "TEAM.md": "root",
            "ROOT.md": "wrong",
            "child/TEAM.md": "abcdef",
        },
        cwd="child",
    )
    assert report["complete"]
    assert [e["path"] for e in report["selected"]] == ["TEAM.md", "child/TEAM.md"]
    assert [e["charged_bytes"] for e in report["selected"]] == [4, 3]
    assert report["candidate_filenames"] == ["AGENTS.override.md", "AGENTS.md", "TEAM.md"]
    assert report["ignored_fallback_filenames"] == ["../outside.md"]
    assert report["limit_source"] == "child/.codex/config.toml"
    assert report["rendered_project_bytes"] == 9


def test_explicit_inputs_override_local_config_and_empty_fallback_list(tmp_path):
    _, report = project(
        tmp_path,
        {
            ".codex/config.toml": 'project_doc_max_bytes = 1\nproject_doc_fallback_filenames = ["TEAM.md"]\n',
            "TEAM.md": "not selected",
            "child/AGENTS.md": "abcdef",
        },
        cwd="child",
        project_doc_max_bytes=65536,
        project_doc_fallback_filenames=(),
    )
    assert report["project_doc_max_bytes"] == 65536
    assert [e["path"] for e in report["selected"]] == ["child/AGENTS.md"]
    assert report["affected_paths"] == []


@pytest.mark.parametrize(
    "text",
    [
        "project_doc_max_bytes = -1",
        "project_doc_max_bytes = true",
        'project_doc_fallback_filenames = "TEAM.md"',
        "not valid toml = [",
    ],
)
def test_bad_local_config_is_incomplete(tmp_path, text):
    _, report = project(tmp_path, {".codex/config.toml": text, "AGENTS.md": "root"})
    assert not report["complete"]
    assert report["charged_bytes"] is None
    assert report["issues"]


def test_exclusion_does_not_fall_through_to_standard(tmp_path):
    context, _ = project(tmp_path, {"AGENTS.override.md": "override", "AGENTS.md": "standard"})
    context.exclude_patterns = ["AGENTS.override.md"]
    context.apply_excludes()
    report = context.lint_tree.find(CodexInstructionsNode)[0].report(context.lint_tree)
    assert not report["complete"]
    assert [e["path"] for e in report["selected"]] == ["AGENTS.override.md"]


def test_symlink_escape_never_reads_external_instructions_or_config(tmp_path, monkeypatch):
    context, _ = project(tmp_path, {"AGENTS.md": "standard"})
    external = tmp_path / "external"
    external.mkdir()
    (external / "config.toml").write_text("project_doc_max_bytes = 1")
    (external / "secret.md").write_text("external")
    (context.root_path / ".codex").symlink_to(external, target_is_directory=True)
    (context.root_path / "AGENTS.override.md").symlink_to(external / "secret.md")
    original = Path.open

    def contained_open(path, *args, **kwargs):
        assert not path.resolve().is_relative_to(external), f"outside read: {path}"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", contained_open)
    context.rebuild_lint_tree()
    report = context.lint_tree.find(CodexInstructionsNode)[0].report(context.lint_tree)
    assert not report["complete"]
    assert report["project_doc_max_bytes"] == 32768
    assert [e["path"] for e in report["selected"]] == ["AGENTS.override.md"]


def test_in_scope_symlink_charged_per_directory_but_content_checked_once(tmp_path):
    context, _ = project(
        tmp_path, {"AGENTS.md": "root", "child/keep": ""}, cwd="child", project_doc_max_bytes=7
    )
    (context.root_path / "child/AGENTS.md").symlink_to("../AGENTS.md")
    context.rebuild_lint_tree()
    tree = context.lint_tree
    report = tree.find(CodexInstructionsNode)[0].report(tree)
    assert [e["charged_bytes"] for e in report["selected"]] == [4, 3]
    assert len(tree.find(AgentsMdBlock)) == 1


def test_read_failure_marks_rest_of_chain_unknown(tmp_path, monkeypatch):
    context, _ = project(tmp_path, {"AGENTS.md": "root", "child/AGENTS.md": "child"}, cwd="child")
    original = Path.read_bytes

    def fail_root(path):
        if path == context.root_path / "AGENTS.md":
            raise PermissionError("permission denied")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", fail_root)
    report = context.lint_tree.find(CodexInstructionsNode)[0].report(context.lint_tree)
    assert not report["complete"]
    assert [e["status"] for e in report["selected"]] == ["unknown", "unknown"]


@pytest.mark.parametrize("cwd", ["../outside", "missing", "AGENTS.md"])
def test_cwd_must_be_directory_in_requested_root(tmp_path, cwd):
    _, report = project(tmp_path, {"AGENTS.md": "root"}, cwd=cwd)
    assert not report["complete"]
    assert "cwd" in report["issues"][0]


def test_config_roundtrip_nulls_and_validation(tmp_path):
    config = LinterConfig.default()
    config.codex_instructions = CodexInstructionOptions("child", 0, ())
    path = tmp_path / ".skillsaw.yaml"
    config.save(path)
    restored = LinterConfig.from_file(path)
    assert restored.codex_instructions == config.codex_instructions
    assert restored.to_dict()["codex-instructions"] == config.codex_instructions.to_dict()
    assert (
        CodexInstructionOptions.from_mapping({"cwd": None, "project_doc_max_bytes": None})
        == CodexInstructionOptions()
    )
    for invalid in [
        [],
        {"cwd": 3},
        {"project_doc_max_bytes": True},
        {"project_doc_max_bytes": -1},
        {"project_doc_fallback_filenames": [1]},
        {"typo": 1},
    ]:
        with pytest.raises(ValueError):
            CodexInstructionOptions.from_mapping(invalid)


def test_default_lint_and_other_ecosystems_unaffected(tmp_path):
    context, _ = project(
        tmp_path, {"CLAUDE.md": "c" * 20000, "GEMINI.md": "g" * 20000, "QWEN.md": "q" * 20000}
    )
    linter = Linter(context, no_plugins=True)
    assert not any(rule.rule_id == "codex-project-instructions" for rule in linter.rules)
    assert not context.lint_tree.find(CodexInstructionsNode)
    Linter(context, rule_ids={"codex-project-instructions"}, no_plugins=True)
    report = context.lint_tree.find(CodexInstructionsNode)[0].report(context.lint_tree)
    assert report["selected"] == []


def test_override_only_repository_gets_content_coverage(tmp_path):
    context, _ = project(tmp_path, {"a/AGENTS.override.md": "Override instructions"})
    assert RepositoryType.CODEX_PROJECT in context.repo_types
    assert len(context.lint_tree.find(AgentsMdBlock)) == 1


def test_severity_override(tmp_path):
    context, _ = project(tmp_path, {"AGENTS.md": "text"})
    config = LinterConfig.default()
    config.codex_instructions = CodexInstructionOptions(project_doc_max_bytes=1)
    config.rules["codex-project-instructions"] = {"enabled": True, "severity": "info"}
    linter = Linter(
        context, config=config, rule_ids={"codex-project-instructions"}, no_plugins=True
    )
    rule = next(rule for rule in linter.rules if rule.rule_id == "codex-project-instructions")
    assert rule.check(context)[0].severity == Severity.INFO


def test_global_config_not_read(tmp_path, monkeypatch):
    secret_home = tmp_path / "home"
    secret_home.mkdir()
    (secret_home / "config.toml").write_text("project_doc_max_bytes = 1")
    monkeypatch.setenv("CODEX_HOME", str(secret_home))
    _, report = project(tmp_path, {"AGENTS.md": "root"})
    assert report["project_doc_max_bytes"] == 32768
    assert "assumed" in report["limit_source"]


@pytest.mark.parametrize(
    "args", [["--cwd", "."], ["--format", "json"], ["--codex-instructions", "--format", "dot"]]
)
def test_invalid_tree_flag_combinations(tmp_path, args):
    result = run_cli(["tree", str(tmp_path), *args])
    assert result.returncode == 2


def test_cli_projection_no_files(tmp_path):
    result = run_cli(["tree", str(tmp_path), "--codex-instructions", "--format", "json"])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["selected"] == []


def test_text_inspection_preserves_lines_and_all_assumptions(tmp_path):
    project(tmp_path, {"AGENTS.md": "root"})
    result = run_cli(["tree", str(tmp_path / "repo"), "--codex-instructions"])
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) > 10
    assert "Global/user/thread instructions" in result.stdout
    assert "AGENTS.md: loaded" in result.stdout
