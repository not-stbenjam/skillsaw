"""Attach Pi resources through the shared tree builder's containment/dedup seam."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, TYPE_CHECKING

from .lint_target import LintTarget
from .blocks import ContextFileBlock

if TYPE_CHECKING:
    from .lint_tree import _TreeBuildState
from .blocks.pi import PiSettingsBlock, PiSkillBlock, PiPromptBlock, PiThemeBlock, PiExtensionNode
from .discovery.pi import local_path, package_resources, project_resources
from .formats.pi import RESOURCE_FIELDS
from .utils import read_frontmatter_commented
from .paths import safe_is_file

_CLASSES = {
    "skills": PiSkillBlock,
    "prompts": PiPromptBlock,
    "themes": PiThemeBlock,
    "extensions": PiExtensionNode,
}


def _attach(
    state: _TreeBuildState,
    parent: LintTarget,
    paths: Iterable[Path],
    kind: str,
    owner: Optional[Path] = None,
) -> None:
    for path in paths:
        if kind == "skills" and path.name == "SKILL.md" and path.parent in state.context.skills:
            # Other consumers retain their portable skill role in dual packages.
            continue
        if kind == "skills" and path.name != "SKILL.md":
            frontmatter, error, _error_line = read_frontmatter_commented(path)
            description = frontmatter.get("description") if isinstance(frontmatter, dict) else None
            if error or not isinstance(description, str) or not description.strip():
                # Pi ignores ordinary Markdown documentation among flat skills.
                continue
        state.add_block(parent, path, _CLASSES[kind], owner=owner)


def attach_pi_resources(state: _TreeBuildState, parent: LintTarget, package: Path) -> None:
    context = state.context
    for kind in RESOURCE_FIELDS:
        _attach(
            state,
            parent,
            package_resources(package, kind, context.root_path, context.is_path_excluded),
            kind,
            owner=package,
        )


def attach_pi_projects(state: _TreeBuildState, root: LintTarget) -> None:
    context = state.context
    for directory in context.agent_tool_dirs(".pi"):
        block = state.add_parser_block(root, directory / "settings.json", PiSettingsBlock)
        data = block.raw_data if block is not None else None
        for name in ("SYSTEM.md", "APPEND_SYSTEM.md"):
            state.add_block(root, directory / name, ContextFileBlock)
        for kind in RESOURCE_FIELDS:
            paths = project_resources(directory, kind, context.root_path, context.is_path_excluded)
            _attach(state, root, sorted(set(paths)), kind)
        if isinstance(data, dict) and isinstance(data.get("packages"), list):
            for entry in data["packages"]:
                source = entry.get("source") if isinstance(entry, dict) else entry
                if isinstance(source, str):
                    path = local_path(directory, source, context.root_path)
                    if path is not None and safe_is_file(path):
                        _attach(state, root, [path], "extensions")
