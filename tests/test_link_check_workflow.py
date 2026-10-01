"""Regression coverage for scheduled broken-link reporting."""

import os
from pathlib import Path
import re
import shlex
import subprocess

import pytest
from ruamel.yaml import YAML


@pytest.fixture
def steps():
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/link-check.yml"
    return YAML(typ="safe").load(workflow.read_text())["jobs"]["lychee"]["steps"]


@pytest.mark.parametrize("exit_code", ["0", "2", "", "1", "3", "127"])
def test_link_check_result_handling(steps, exit_code):
    validate = next(s for s in steps if s["name"] == "Validate link-check result")
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", validate["run"]],
        env={**os.environ, "LYCHEE_EXIT_CODE": exit_code},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert (result.returncode == 0) == (exit_code in {"0", "2"})
    if result.returncode:
        assert "::error::" in result.stdout

    issue = next(s for s in steps if s["name"] == "Open broken-link issue")
    # Missing outputs and tooling failures must never satisfy this condition.
    assert issue["if"] == "steps.lychee.outputs.exit_code == '2'"


@pytest.mark.parametrize(
    ("url", "excluded"),
    [
        (
            "file:///home/runner/work/skillsaw/skillsaw/docs/overrides/partials/"
            "%7B%7B%20config.extra.homepage%20|%20d(nav.homepage.url,%20true)"
            "%20|%20url%20%7D%7D",
            True,
        ),
        ("file:///repo/docs/{{ config.site_url }}", True),
        ("file:///repo/docs/%7b%7b%20config.site_url%20%7d%7d", True),
        ("file:///repo/docs/missing.html", False),
        ("file:///repo/docs/missing%20page.html", False),
        ("https://example.com/missing", False),
    ],
)
def test_template_exclusion_preserves_real_links(steps, url, excluded):
    lychee = next(s for s in steps if s.get("id") == "lychee")
    args = shlex.split(lychee["with"]["args"])
    patterns = [args[i + 1] for i, arg in enumerate(args) if arg == "--exclude"]
    assert any(re.search(pattern, url) for pattern in patterns) == excluded
