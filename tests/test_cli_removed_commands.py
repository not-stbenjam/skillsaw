"""Removal of the repository documentation generator in 0.21.0."""

import argparse

from skillsaw.cli import _SUBCOMMANDS
from skillsaw.cli._parser import _build_parser
from tests.cli_runner import run_cli


def test_docs_is_not_a_builtin_command():
    parser = _build_parser()
    subcommands = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert "docs" not in subcommands.choices
    assert "docs" not in _SUBCOMMANDS


def test_former_docs_arguments_cannot_generate_output(tmp_path):
    output = tmp_path / "generated.md"
    result = run_cli(["docs", tmp_path, "--format", "markdown", "-o", output])
    assert result.returncode == 2
    assert not output.exists()


def test_docs_directory_is_a_lint_path(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "SKILL.md").write_text(
        "---\nname: docs\ndescription: Review documentation before publishing changes\n---\n\n"
        "# Documentation review\n\nCheck the documentation for outdated examples.\n",
        encoding="utf-8",
    )
    result = run_cli(["docs", "--rule", "agentskill-name"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "skillsaw-docs").exists()
