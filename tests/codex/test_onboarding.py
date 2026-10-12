"""Optional onboarding references follow the selected Codex overlay."""

import json
import shutil

import pytest

from skillsaw.context import RepositoryContext
from skillsaw.rule import Severity
from skillsaw.rules.builtin.codex import CodexPluginJsonValidRule
from skillsaw.utils import invalidate_read_caches

from ._helpers import copy_fixture


def _plugin(tmp_path, layout="portable"):
    repo = copy_fixture("codex/onboarding", tmp_path)
    manifest = repo / "plugin.json"
    if layout == "legacy":
        manifest.unlink()
        manifest = repo / ".codex-plugin/plugin.json"
    elif layout == "fallback":
        data = json.loads(manifest.read_text())
        data.pop("extensions")
        manifest.write_text(json.dumps(data))
        manifest = repo / ".codex-plugin/plugin.json"
    return repo, manifest


def _set_reference(manifest, value):
    data = json.loads(manifest.read_text())
    data.setdefault("extensions", {}).setdefault("com.openai", {})["onboardingSkill"] = value
    manifest.write_text(json.dumps(data))


def _check(repo, config=None):
    invalidate_read_caches()
    return CodexPluginJsonValidRule(config or {}).check(RepositoryContext(repo))


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
@pytest.mark.parametrize("prefix", ["./", ""])
def test_valid_reference_with_non_setup_name(tmp_path, layout, prefix):
    repo, manifest = _plugin(tmp_path, layout)
    _set_reference(manifest, f"{prefix}skills/connect-account/SKILL.md")
    assert _check(repo) == []


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
def test_optional_field_can_be_absent(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    data = json.loads(manifest.read_text())
    data["extensions"]["com.openai"].pop("onboardingSkill")
    manifest.write_text(json.dumps(data))
    assert _check(repo) == []


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
@pytest.mark.parametrize("value", [None, False, 7, [], {}, ["./skills/get-started/SKILL.md"], ""])
def test_malformed_declared_reference(tmp_path, layout, value):
    repo, manifest = _plugin(tmp_path, layout)
    _set_reference(manifest, value)
    findings = _check(repo)
    assert len(findings) == 1
    assert findings[0].file_path == manifest
    assert "non-empty path string" in findings[0].message


@pytest.mark.parametrize("extension", [{}, {"onboardingSkill": "./skills/get-started/SKILL.md"}])
def test_inline_object_shadows_invalid_fallback(tmp_path, extension):
    repo, manifest = _plugin(tmp_path)
    data = json.loads(manifest.read_text())
    data["extensions"]["com.openai"] = extension
    manifest.write_text(json.dumps(data))
    _set_reference(repo / ".codex-plugin/plugin.json", {"invalid": True})
    assert _check(repo) == []


@pytest.mark.parametrize("value", [None, [], False, "ignored"])
def test_non_object_inline_extension_uses_fallback(tmp_path, value):
    repo, manifest = _plugin(tmp_path)
    data = json.loads(manifest.read_text())
    data["extensions"]["com.openai"] = value
    manifest.write_text(json.dumps(data))
    fallback = repo / ".codex-plugin/plugin.json"
    _set_reference(fallback, "./skills/missing/SKILL.md")
    findings = _check(repo)
    assert len(findings) == 1 and findings[0].file_path == fallback


def test_invalid_inline_value_does_not_fall_back(tmp_path):
    repo, manifest = _plugin(tmp_path)
    _set_reference(manifest, False)
    findings = _check(repo)
    assert len(findings) == 1 and findings[0].file_path == manifest


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
@pytest.mark.parametrize(
    "target",
    ["skills/missing/SKILL.md", "skills/get-started", "notes.md", "private/example/SKILL.md"],
)
def test_missing_directory_nonskill_and_unbundled_targets(tmp_path, layout, target):
    repo, manifest = _plugin(tmp_path, layout)
    (repo / "notes.md").write_text("# Meeting notes\n")
    shutil.copytree(repo / "skills/get-started", repo / "private/example")
    _set_reference(manifest, f"./{target}")
    findings = _check(repo)
    assert len(findings) == 1
    assert findings[0].file_path == manifest
    assert "SKILL.md" in findings[0].message


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
def test_custom_component_root_only_applies_to_legacy(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    shutil.copytree(repo / "skills/get-started", repo / "workflows/welcome")
    data = json.loads(manifest.read_text())
    data["skills"] = "./workflows"
    data["extensions"]["com.openai"]["skills"] = "./workflows"
    manifest.write_text(json.dumps(data))
    _set_reference(manifest, "./workflows/welcome/SKILL.md")
    findings = _check(repo)
    assert len(findings) == (0 if layout == "legacy" else 1)


@pytest.mark.parametrize("declared", ["./workflows", "./missing", ["./workflows"]])
def test_legacy_declared_roots_replace_conventional_root(tmp_path, declared):
    repo, manifest = _plugin(tmp_path, "legacy")
    shutil.copytree(repo / "skills/get-started", repo / "workflows/welcome")
    data = json.loads(manifest.read_text())
    data["skills"] = declared
    manifest.write_text(json.dumps(data))
    findings = [v for v in _check(repo) if "onboardingSkill" in v.message]
    assert len(findings) == 1 and "not a bundled skill" in findings[0].message


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
def test_shared_claude_manifest_does_not_change_codex_membership(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    marker = repo / ".claude-plugin"
    marker.mkdir()
    (marker / "plugin.json").write_text('{"name": "workspace-notes"}')
    assert RepositoryContext(repo).provenance(repo).claude
    assert _check(repo) == []
    shutil.copytree(repo / "skills/get-started", repo / "skills/private/nested")
    _set_reference(manifest, "./skills/private/nested/SKILL.md")
    assert len(_check(repo)) == (0 if layout == "legacy" else 1)


@pytest.mark.parametrize(
    "value",
    [
        "../outside/SKILL.md",
        "/outside/SKILL.md",
        "./skills/../skills/get-started/SKILL.md",
        "./bad\x00path",
        "C:\\outside\\SKILL.md",
    ],
)
def test_unsafe_paths(tmp_path, value):
    repo, manifest = _plugin(tmp_path)
    _set_reference(manifest, value)
    findings = _check(repo)
    assert len(findings) == 1 and findings[0].file_path == manifest


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
@pytest.mark.parametrize("kind", ["directory", "file", "dangling", "loop"])
def test_symlink_escapes_and_unresolvable_targets(tmp_path, layout, kind):
    repo, manifest = _plugin(tmp_path, layout)
    skill = repo / "skills/get-started"
    target = skill if kind == "directory" else skill / "SKILL.md"
    outside = tmp_path / "outside"
    target.rename(outside)
    destination = (
        target if kind == "loop" else tmp_path / "missing" if kind == "dangling" else outside
    )
    target.symlink_to(destination, target_is_directory=kind == "directory")
    _set_reference(manifest, "./skills/get-started/SKILL.md")
    findings = _check(repo)
    assert len(findings) == 1 and findings[0].file_path == manifest


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
def test_contained_file_alias_matches_canonical_skill_identity(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    (repo / "welcome.md").symlink_to(repo / "skills/get-started/SKILL.md")
    _set_reference(manifest, "./welcome.md")
    assert _check(repo) == []


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
def test_hidden_skill_is_not_an_onboarding_target(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    shutil.copytree(repo / "skills/get-started", repo / "skills/.private")
    _set_reference(manifest, "./skills/.private/SKILL.md")
    findings = _check(repo)
    assert len(findings) == 1 and "not a bundled skill" in findings[0].message


@pytest.mark.parametrize("layout", ["portable", "fallback", "legacy"])
def test_contained_directory_alias_is_a_bundled_skill(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    (repo / "skills/welcome").symlink_to(repo / "skills/get-started", target_is_directory=True)
    _set_reference(manifest, "./skills/welcome/SKILL.md")
    assert _check(repo) == []


@pytest.mark.parametrize("layout", ["portable", "legacy"])
def test_excluded_skill_does_not_become_an_unbundled_finding(tmp_path, layout):
    repo, manifest = _plugin(tmp_path, layout)
    _set_reference(manifest, "./skills/get-started/SKILL.md")
    context = RepositoryContext(repo, exclude_patterns=["skills/get-started/**"])
    assert CodexPluginJsonValidRule({}).check(context) == []


def test_check_paths_exist_setting_and_severity_override(tmp_path):
    repo, manifest = _plugin(tmp_path)
    _set_reference(manifest, "./skills/generated/SKILL.md")
    assert _check(repo, {"check-paths-exist": False}) == []
    findings = _check(repo, {"severity": "warning"})
    assert len(findings) == 1 and findings[0].severity == Severity.WARNING
    _set_reference(manifest, "../outside/SKILL.md")
    assert len(_check(repo, {"check-paths-exist": False})) == 1


def test_installed_manifest_keeps_existing_stand_down(tmp_path):
    source, manifest = _plugin(tmp_path)
    _set_reference(manifest, False)
    repo = tmp_path / "installed"
    installed = repo / ".codex/plugins/workspace-notes"
    installed.parent.mkdir(parents=True)
    source.rename(installed)
    assert _check(repo) == []
