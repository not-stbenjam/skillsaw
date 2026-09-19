"""Cursor recursive selectors stay bounded without changing selected resources."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from skillsaw.blocks import CursorRuleBlock
from skillsaw.context import RepositoryContext
from skillsaw.discovery.cursor_globs import contained_glob
from skillsaw.formats.cursor import component_paths
from tests.test_integration import copy_fixture


def test_repeated_recursive_glob_cli_finishes_and_keeps_matches(tmp_path):
    repo = copy_fixture("cursor-plugins/recursive-globs", tmp_path)
    # A subprocess deadline ensures a traversal regression cannot hang pytest.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "skillsaw",
            "lint",
            str(repo),
            "--no-custom-rules",
            "--no-plugins",
            "--rule",
            "cursor-plugin-json-valid",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    paths = {
        b.path.relative_to(repo).as_posix()
        for b in RepositoryContext(repo).lint_tree.find(CursorRuleBlock)
    }
    assert paths == {"x/" * 22 + "review.md", "guidance/nested/check.md", "guidance/.hidden.md"}


@pytest.mark.parametrize(
    "pattern",
    [
        "*",
        "*/",
        "**",
        "**/",
        "**/*",
        "**/*.md",
        "guidance/*",
        "guidance/*/",
        "guidance/.*",
        "guidance/[n]ested/*.md",
        "**/x/**/x/*.md",
        "**/missing/*.md",
        "guidance/./nested/*.md",
        "**/**/review.md",
    ],
)
def test_globs_preserve_pathlib_matches(tmp_path, pattern):
    repo = copy_fixture("cursor-plugins/recursive-globs", tmp_path)
    assert contained_glob(repo, pattern) == set(repo.glob(pattern))


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX symlinks")
@pytest.mark.parametrize("pattern", ["**", "**/", "**/*", "*/**/*.md", "link/*.md", "link/**"])
def test_globs_preserve_internal_symlinks_and_never_escape(tmp_path, pattern):
    repo = copy_fixture("cursor-plugins/recursive-globs", tmp_path)
    (repo / "link").symlink_to("guidance", target_is_directory=True)
    external = tmp_path / "outside"
    external.mkdir()
    (external / "secret.md").write_text("External content must not be loaded.\n")
    (repo / "escape").symlink_to(external, target_is_directory=True)
    expected = {p for p in repo.glob(pattern) if p.resolve().is_relative_to(repo)}
    assert component_paths(repo, {"rules": pattern}, "rules") == sorted(expected)


def test_excluded_glob_components_stay_excluded(tmp_path):
    repo = copy_fixture("cursor-plugins/recursive-globs", tmp_path)
    blocks = RepositoryContext(repo, exclude_patterns=["guidance/**"]).lint_tree.find(
        CursorRuleBlock
    )
    assert {b.path.relative_to(repo).as_posix() for b in blocks} == {"x/" * 22 + "review.md"}
