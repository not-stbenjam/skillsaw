"""Pi YAML core semantics, flat selection, and source-preserving content fixes."""

import json
from pathlib import Path
import shutil

import pytest

from skillsaw.blocks import SkillBlock
from skillsaw.blocks.pi import PiSkillBlock
from skillsaw.blocks.pi_frontmatter import parse_pi_frontmatter
from skillsaw.context import RepositoryContext
from skillsaw.utils import parse_frontmatter
from tests.cli_runner import run_cli

FIXTURE = Path(__file__).parent / "fixtures/pi/yaml-core"


def copy_fixture(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE, root)
    return root


def test_cli_pi_yaml_core_contract(tmp_path):
    root = copy_fixture(tmp_path)
    result = run_cli(
        [
            "lint",
            str(root),
            "--no-custom-rules",
            "--rule",
            "pi-skill-valid",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    violations = json.loads(result.stdout)["violations"]
    findings = {v["file_path"]: v for v in violations}
    assert set(findings) == {
        f"skills/{name}/SKILL.md"
        for name in (
            "duplicate",
            "nested-duplicate",
            "merge",
            "malformed",
            "null",
            "sequence",
            "boolean",
            "number",
        )
    }
    assert findings["skills/duplicate/SKILL.md"]["line"] == 3
    assert findings["skills/nested-duplicate/SKILL.md"]["line"] == 5
    assert findings["skills/null/SKILL.md"]["line"] == 2
    assert findings["skills/merge/SKILL.md"].get("line") is None


def test_flat_eligibility_uses_same_pi_parser(tmp_path):
    root = copy_fixture(tmp_path)
    context = RepositoryContext(root)
    flat = {
        block.path.name
        for block in context.lint_tree.find(PiSkillBlock)
        if block.path.parent.name == "flat"
    }
    assert flat == {"no.md", "date.md", "alias.md", "quoted.md"}
    portable = context.lint_tree.find(SkillBlock)
    assert len(portable) == 1
    assert portable[0].field_value("description") is False
    assert not context.lint_tree_errors


@pytest.mark.parametrize("value", ["no", "yes", "on", "off", "2026-09-18", "1_000", "0b10", "1:30"])
def test_core_strings_remain_strings(value):
    parsed = parse_pi_frontmatter(f"---\ndescription: {value}\n---\nReview compatibility.\n")
    assert parsed.error is None
    assert parsed.data["description"] == value


@pytest.mark.parametrize(
    "value,expected",
    [("01", 1), ("0o17", 15), ("0x10", 16), ("1e3", 1000.0), ("true", True), ("null", None)],
)
def test_core_nonstring_scalars(value, expected):
    parsed = parse_pi_frontmatter(f"---\ndescription: {value}\n---\nReview compatibility.\n")
    assert parsed.error is None
    assert parsed.data["description"] == expected


def test_portable_yaml_resolver_and_duplicate_behavior_unchanged():
    text = "---\ndescription: no\n---\nReview compatibility.\n"
    assert parse_pi_frontmatter(text).data["description"] == "no"
    assert parse_frontmatter(text)[0]["description"] is False
    duplicate = "---\ndescription: first\ndescription: second\n---\nReview compatibility.\n"
    assert parse_pi_frontmatter(duplicate).error
    assert parse_frontmatter(duplicate)[0]["description"] == "second"


@pytest.mark.parametrize("closing", ["---\n", "--- continued\n"])
def test_native_delimiter_preserves_key_lines_and_body_spans(closing):
    text = "---\ndescription: no\n" + closing + "\nReview compatibility.\n"
    parsed = parse_pi_frontmatter(text)
    assert parsed.key_lines == {"description": 2}
    assert text.endswith(parsed.body)
    prefix = text[: len(text) - len(parsed.body)]
    assert prefix.count("\n") == parsed.line_offset
    assert parsed.body.endswith("\nReview compatibility.\n")


def test_native_content_fix_preserves_metadata_lines_and_idempotency(tmp_path):
    root = copy_fixture(tmp_path)
    skill = root / "skills/body-fix/SKILL.md"
    before = skill.read_text()
    args = ["fix", str(root), "--no-custom-rules", "--rule", "content-unlinked-internal-reference"]
    first = run_cli(args)
    assert first.returncode == 0, first.stdout + first.stderr
    after = skill.read_text()
    assert "Read [./references/guide.md](./references/guide.md)" in after
    assert before.split("---\n", 2)[1] == after.split("---\n", 2)[1]
    assert before.count("\n") == after.count("\n")
    assert run_cli(args).returncode == 0
    assert skill.read_text() == after
    lint = run_cli(
        [
            "lint",
            str(root),
            "--no-custom-rules",
            "--rule",
            "content-unlinked-internal-reference",
            "--format",
            "json",
        ]
    )
    assert json.loads(lint.stdout)["violations"] == []


def test_native_body_write_uses_dialect_preflight(tmp_path):
    root = copy_fixture(tmp_path)
    block = next(
        b
        for b in RepositoryContext(root).lint_tree.find(PiSkillBlock)
        if b.path == root / "skills/no/SKILL.md"
    )
    from skillsaw.blocks.frontmatter import BodyContent

    body = block.find(BodyContent)[0]
    before = block.path.read_text()
    prefix = before[: len(before) - len(body.body)]
    body.write_body("Review response compatibility before changing the API.\n")
    assert (
        block.path.read_text()
        == prefix + "Review response compatibility before changing the API.\n"
    )
    assert block.field_value("description") == "no"
    assert block.key_line("description") == 2


@pytest.mark.parametrize(
    "first,second,duplicate",
    [
        (".nan", ".nan", False),
        ("1", "1.0", True),
        ("0", "-0.0", True),
        ("9007199254740992", "9007199254740993", True),
        ("1e400", ".inf", True),
        ("9" * 400, ".inf", True),
        ("-" + "9" * 400, "-.inf", True),
        ("true", "1", False),
        ('"1"', "1", False),
    ],
)
def test_numeric_key_equality_matches_pi(first, second, duplicate):
    text = (
        "---\ndescription: Use when reviewing changes.\nmetadata:\n"
        f"  {first}: first\n  {second}: second\n---\nReview the changes.\n"
    )
    parsed = parse_pi_frontmatter(text)
    assert bool(parsed.error) is duplicate
    if duplicate:
        assert parsed.error_line == 5
    else:
        assert parsed.data["description"] == "Use when reviewing changes."


@pytest.mark.parametrize("tag", ["set", "seq", "map", "omap", "pairs"])
def test_malformed_tagged_key_is_a_parse_error(tag):
    parsed = parse_pi_frontmatter(
        f"---\n? !!{tag} x\n: value\ndescription: Review changes.\n---\nBody\n"
    )
    assert parsed.error == "Invalid YAML frontmatter"
    assert parsed.error_line == 2
