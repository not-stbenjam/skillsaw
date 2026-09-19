"""Pi discovery and CLI regression tests against repository fixtures."""

import json
import shutil
from pathlib import Path

import pytest

from skillsaw.blocks import SkillBlock
from skillsaw.blocks.pi import (
    PiPackageBlock,
    PiSettingsBlock,
    PiSkillBlock,
    PiPromptBlock,
    PiExtensionNode,
)
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.rules.builtin.pi.config_valid import PiConfigValidRule
from skillsaw.rules.builtin.pi.resource_paths import PiResourcePathsRule
from tests.cli_runner import run_cli
from skillsaw.utils import invalidate_read_caches

FIXTURES = Path(__file__).parent / "fixtures" / "pi"


def copy_fixture(name, tmp_path):
    root = tmp_path / name
    shutil.copytree(FIXTURES / name, root)
    return root


def paths(context, cls):
    return {str(p.path.relative_to(context.root_path)) for p in context.lint_tree.find(cls)}


def test_package_selection_and_native_skill_dialect(tmp_path):
    root = copy_fixture("package", tmp_path)
    ctx = RepositoryContext(root)
    assert ctx.repo_type is RepositoryType.PI_PACKAGE
    assert paths(ctx, PiSkillBlock) == {
        "custom/skills/flat.md",
        "custom/skills/review/SKILL.md",
        "custom/skills/keep/SKILL.md",
    }
    assert paths(ctx, PiPromptBlock) == {
        "custom/prompts/review.md",
        "custom/prompts/nested/check.md",
    }
    assert not paths(ctx, SkillBlock)
    assert paths(ctx, PiExtensionNode) == {"extensions/index.ts"}
    assert not ctx.lint_tree_errors


def test_project_relative_paths_and_local_conventions(tmp_path):
    ctx = RepositoryContext(copy_fixture("project", tmp_path))
    assert {RepositoryType.PI, RepositoryType.PI_PACKAGE} <= ctx.repo_types
    assert paths(ctx, PiSkillBlock) == {
        ".pi/skills/flat.md",
        "custom/scan/SKILL.md",
        "local/skills/flat.md",
    }
    assert paths(ctx, PiPromptBlock) == {".pi/prompts/direct.md", "templates/nested/review.md"}
    assert paths(ctx, PiSettingsBlock) == {".pi/settings.json"}
    assert not ctx.lint_tree_errors


def test_empty_manifest_does_not_fall_back(tmp_path):
    ctx = RepositoryContext(copy_fixture("empty", tmp_path))
    assert not paths(ctx, PiSkillBlock)
    assert not paths(ctx, SkillBlock)


def test_keyword_only_package_uses_conventions(tmp_path):
    ctx = RepositoryContext(copy_fixture("conventional", tmp_path))
    assert paths(ctx, PiSkillBlock) == {"skills/check/SKILL.md"}
    assert paths(ctx, PiPromptBlock) == {"prompts/nested/review.md"}


def test_dual_package_keeps_portable_skills(tmp_path):
    ctx = RepositoryContext(copy_fixture("dual", tmp_path))
    assert ctx.provenance(ctx.root_path).ecosystems == frozenset({"pi", "claude"})
    assert paths(ctx, SkillBlock) == {"skills/portable/SKILL.md"}
    assert "custom/flat.md" in paths(ctx, PiSkillBlock)


def test_bad_arrays_are_consolidated(tmp_path):
    ctx = RepositoryContext(copy_fixture("invalid", tmp_path))
    violations = PiConfigValidRule().check(ctx)
    assert len(violations) == 2
    assert any("pi.skills" in v.message and "pi.prompts" in v.message for v in violations)
    assert any("packages[0]" in v.message and "packages[1].source" in v.message for v in violations)
    assert not ctx.lint_tree_errors


def test_literal_paths_opt_in_and_globs_are_not_missing(tmp_path):
    ctx = RepositoryContext(copy_fixture("missing", tmp_path))
    violations = PiResourcePathsRule().check(ctx)
    assert len(violations) == 1
    assert "missing" in violations[0].message
    assert "no-match" not in violations[0].message


@pytest.mark.parametrize("fixture", ["package", "project", "conventional", "empty"])
def test_cli_native_pi_metadata_valid(fixture, tmp_path):
    root = copy_fixture(fixture, tmp_path)
    result = run_cli(
        [
            "lint",
            str(root),
            "--rule",
            "pi-config-valid",
            "--rule",
            "pi-skill-valid",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert not data["violations"]


def test_cli_invalid_metadata(tmp_path):
    root = copy_fixture("invalid", tmp_path)
    result = run_cli(["lint", str(root), "--rule", "pi-config-valid", "--format", "json"])
    assert len(json.loads(result.stdout)["violations"]) == 2


def test_unrelated_npm_package_is_not_pi(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"ordinary"}')
    ctx = RepositoryContext(tmp_path)
    assert RepositoryType.PI_PACKAGE not in ctx.repo_types
    assert not paths(ctx, PiPackageBlock)


def test_containment_excludes_and_symlink_loop(tmp_path):
    root = copy_fixture("package", tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("Secret outside the lint root.\n")
    (root / "custom/prompts/escape.md").symlink_to(outside)
    (root / "custom/skills/loop").symlink_to(root / "custom/skills", target_is_directory=True)
    ctx = RepositoryContext(root, exclude_patterns=["custom/skills/keep/**"])
    assert "custom/skills/keep/SKILL.md" not in paths(ctx, PiSkillBlock)
    assert "custom/prompts/escape.md" not in paths(ctx, PiPromptBlock)
    assert not ctx.lint_tree_errors


def test_nested_package_and_unrelated_type_override(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(FIXTURES / "package", root / "packages/review")
    ctx = RepositoryContext(root, repo_types={RepositoryType.AGENTS_MD})
    assert ctx.provenance(root / "packages/review").pi
    assert paths(ctx, PiPackageBlock) == {"packages/review/package.json"}
    assert len(paths(ctx, PiSkillBlock)) == 3


def test_forced_conventional_root_keeps_provenance_declarative(tmp_path):
    root = copy_fixture("conventional", tmp_path)
    (root / "package.json").unlink()
    ctx = RepositoryContext(root, repo_types={RepositoryType.PI_PACKAGE})
    assert not ctx.provenance(root).pi
    assert paths(ctx, PiSkillBlock) == {"skills/check/SKILL.md"}
    assert ctx.skill_count == 1
    assert not paths(ctx, SkillBlock)


def test_forced_malformed_package_reports_parse_error(tmp_path):
    (tmp_path / "package.json").write_text('{"pi":')
    ctx = RepositoryContext(tmp_path, repo_types={RepositoryType.PI_PACKAGE})
    violations = PiConfigValidRule().check(ctx)
    assert len(violations) == 1
    assert "JSON" in violations[0].message


def test_project_overrides_filter_autoload(tmp_path):
    root = copy_fixture("project", tmp_path)
    settings = root / ".pi/settings.json"
    data = json.loads(settings.read_text())
    data["prompts"] = ["!*.md", "+prompts/direct.md", "-prompts/direct.md"]
    settings.write_text(json.dumps(data))
    ctx = RepositoryContext(root)
    assert not paths(ctx, PiPromptBlock)


def test_manifest_globs_do_not_walk_hidden_or_symlinked_trees(tmp_path):
    root = copy_fixture("package", tmp_path)
    (root / "custom/prompts/.hidden").mkdir()
    (root / "custom/prompts/.hidden/secret.md").write_text("Hidden prompt.\n")
    (root / "custom/prompts/link").symlink_to(root / "custom/skills", target_is_directory=True)
    ctx = RepositoryContext(root)
    assert paths(ctx, PiPromptBlock) == {
        "custom/prompts/review.md",
        "custom/prompts/nested/check.md",
    }


def test_explicit_symlink_and_hidden_roots_load_once(tmp_path):
    root = copy_fixture("package", tmp_path)
    (root / ".selected").symlink_to(root / "custom/skills", target_is_directory=True)
    (root / "package.json").write_text(
        json.dumps({"pi": {"skills": [".selected", "custom/skills"]}})
    )
    ctx = RepositoryContext(root)
    assert len(paths(ctx, PiSkillBlock)) == 4
    assert ctx.skill_count == 4
    assert not ctx.lint_tree_errors


def test_ignore_files_and_skill_root_stop_recursion(tmp_path):
    root = copy_fixture("conventional", tmp_path)
    prompts = root / "prompts"
    (prompts / ".fdignore").write_text("nested/\n")
    (root / "skills/.ignore").write_text("check/\n")
    ctx = RepositoryContext(root)
    assert not paths(ctx, PiSkillBlock)
    assert not paths(ctx, PiPromptBlock)
    (root / "skills/.ignore").unlink()
    invalidate_read_caches()
    nested = root / "skills/check/nested"
    nested.mkdir()
    (nested / "SKILL.md").write_text((root / "skills/check/SKILL.md").read_text())
    ctx = RepositoryContext(root)
    assert paths(ctx, PiSkillBlock) == {"skills/check/SKILL.md"}


def test_extension_index_precedence_and_self_reference_never_execute(tmp_path):
    root = copy_fixture("package", tmp_path)
    (root / "extensions/ignored.ts").write_text('throw new Error("Not an entrypoint");')
    ctx = RepositoryContext(root)
    assert paths(ctx, PiExtensionNode) == {"extensions/index.ts"}
    (root / "extensions/package.json").write_text('{"pi":{"extensions":["."]}}')
    invalidate_read_caches()
    ctx = RepositoryContext(root)
    assert paths(ctx, PiExtensionNode) == {"extensions"}
    assert not ctx.lint_tree_errors


def test_settings_symlink_outside_checkout_is_not_read(tmp_path):
    root = copy_fixture("project", tmp_path)
    outside = tmp_path / "settings.json"
    outside.write_text('{"skills":["unexpected"]}')
    settings = root / ".pi/settings.json"
    settings.unlink()
    settings.symlink_to(outside)
    ctx = RepositoryContext(root)
    assert not paths(ctx, PiSettingsBlock)
    assert not ctx.pi_package_roots()
    assert not ctx.lint_tree_errors


def test_severity_override_and_json_no_fabricated_line(tmp_path):
    from skillsaw.rule import Severity

    ctx = RepositoryContext(copy_fixture("invalid", tmp_path))
    rule = PiConfigValidRule({"severity": "error"})
    violations = rule.check(ctx)
    assert all(v.severity is Severity.ERROR and v.line is None for v in violations)


def test_cli_native_skill_error_and_content_checks(tmp_path):
    root = copy_fixture("invalid-skill", tmp_path)
    result = run_cli(["lint", str(root), "--rule", "pi-skill-valid", "--format", "json"])
    violations = json.loads(result.stdout)["violations"]
    assert len(violations) == 1
    assert violations[0]["line"] == 2
    prompt = root / "prompts/check.md"
    prompt.parent.mkdir()
    prompt.write_text("Inspect [the contract](missing-contract.md) before reviewing.\n")
    (root / "package.json").write_text('{"pi":{"prompts":["prompts"]}}')
    result = run_cli(
        ["lint", str(root), "--rule", "content-broken-internal-reference", "--format", "json"]
    )
    assert any(
        v["rule_id"] == "content-broken-internal-reference"
        for v in json.loads(result.stdout)["violations"]
    )


def test_nested_other_consumers_keep_portable_skills(tmp_path):
    root = copy_fixture("package", tmp_path)
    for prefix in (".agents/skills", "plugins/child/skills"):
        skill = root / prefix / "portable"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: portable\ndescription: Use when reviewing an API change.\n---\nReview the request contract.\n"
        )
    marker = root / "plugins/child/.claude-plugin"
    marker.mkdir()
    (marker / "plugin.json").write_text('{"name":"child"}')
    ctx = RepositoryContext(root)
    assert {".agents/skills/portable/SKILL.md", "plugins/child/skills/portable/SKILL.md"} <= paths(
        ctx, SkillBlock
    )


def test_installed_package_stores_are_not_authored_packages(tmp_path):
    pi = tmp_path / ".pi"
    pi.mkdir()
    (pi / "settings.json").write_text('{"packages":["git:github.com/example/package"]}')
    shutil.copytree(FIXTURES / "package", pi / "git/example/package")
    ctx = RepositoryContext(tmp_path)
    assert not ctx.pi_package_roots()
    assert not paths(ctx, PiPackageBlock)


def test_excludes_refresh_package_identity(tmp_path):
    root = copy_fixture("package", tmp_path)
    ctx = RepositoryContext(root)
    assert ctx.provenance(root).pi
    ctx.exclude_patterns.append("package.json")
    ctx.apply_excludes()
    assert not ctx.pi_package_roots()
    assert not ctx.provenance(root).pi
    assert RepositoryType.PI_PACKAGE not in ctx.repo_types
