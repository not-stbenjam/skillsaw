"""Attach the inputs for a requested Codex instruction projection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .blocks.codex import CodexConfigBlock
from .blocks.content import AgentsMdBlock, CodexInstructionBlock, ReadmeBlock
from .codex_instructions import CodexInstructionsNode
from .discovery.codex_instructions import project_configs, project_directories, select_instructions
from .formats.codex import CODEX_HOOKS_FILENAME
from .formats.codex_instructions import DEFAULT_MAX_BYTES, candidate_filenames
from .paths import relative_to_str

if TYPE_CHECKING:
    from .lint_tree import _TreeBuildState


def attach_codex_instructions(state: _TreeBuildState) -> None:
    context = state.context
    options = context.codex_instructions
    assert options is not None
    resolve = context.resolve_path
    node = CodexInstructionsNode(
        path=context.root_path, root_path=context.root_path, cwd=context.root_path
    )
    try:
        directories = project_directories(context.root_path, options.cwd, resolve=resolve)
    except (ValueError, OSError) as error:
        node.issues.append(str(error))
        state.root.children.append(node)
        return
    node.cwd = directories[-1]
    if not context.lint_external_content and context.is_externally_sourced(node.cwd):
        node.issues.append("Codex cwd is outside the retained authoring scope")
    configs = {resolve(block.path): block for block in state.root.find(CodexConfigBlock)}
    limit = DEFAULT_MAX_BYTES
    fallbacks = ()
    merged = {}
    origins = {}
    for candidate in project_configs(
        directories, resolve=resolve, is_excluded=context.is_path_excluded
    ):
        if candidate.path.name == CODEX_HOOKS_FILENAME:
            if candidate.issue is None and (
                context.lint_external_content or not context.is_externally_sourced(candidate.path)
            ):
                state.add_codex_hooks(state.root, candidate.path)
            continue
        if candidate.issue:
            node.issues.append(candidate.issue)
            continue
        path = candidate.path
        label = relative_to_str(path, context.root_path) or str(path)
        if not context.lint_external_content and context.is_externally_sourced(path):
            node.issues.append(f"{label}: configuration is outside the retained authoring scope")
            continue
        config = configs.get(resolve(path))
        if config is None:
            config = state.add_codex_config(state.root, path)
            if config is not None:
                configs[resolve(path)] = config
        if config is None:
            node.issues.append(f"{label}: configuration is not in the lint tree")
            continue
        node.config_sources.append(candidate)
        if config.parse_error:
            node.issues.append(f"{label}: {config.parse_error}")
            continue
        for key in ("project_doc_max_bytes", "project_doc_fallback_filenames"):
            if key in (config.raw_data or {}):
                merged[key] = config.raw_data[key]
                origins[key] = label
    if options.project_doc_max_bytes is not None:
        merged["project_doc_max_bytes"] = options.project_doc_max_bytes
        origins["project_doc_max_bytes"] = "explicit codex-instructions analysis input"
    if options.project_doc_fallback_filenames is not None:
        merged["project_doc_fallback_filenames"] = list(options.project_doc_fallback_filenames)
        origins["project_doc_fallback_filenames"] = "explicit codex-instructions analysis input"
    if "project_doc_max_bytes" in merged:
        value = merged["project_doc_max_bytes"]
        node.limit_source = origins["project_doc_max_bytes"]
        if type(value) is not int or value < 0:
            node.issues.append(
                f"{node.limit_source}: project_doc_max_bytes must be a non-negative integer"
            )
        else:
            limit = value
    if "project_doc_fallback_filenames" in merged:
        value = merged["project_doc_fallback_filenames"]
        node.fallback_source = origins["project_doc_fallback_filenames"]
        if not isinstance(value, list) or not all(isinstance(name, str) for name in value):
            node.issues.append(
                f"{node.fallback_source}: project_doc_fallback_filenames must be a list of strings"
            )
        else:
            fallbacks = tuple(value)
    node.max_bytes = limit
    node.filenames, node.ignored_fallbacks = candidate_filenames(fallbacks)
    node.sources = select_instructions(
        directories, node.filenames, resolve=resolve, is_excluded=context.is_path_excluded
    )
    claimed = set()
    readmes = {}
    for parent in state.root.walk():
        for block in parent.children:
            resolved = resolve(block.path)
            if isinstance(block, ReadmeBlock):
                readmes[resolved] = (parent, block)
            else:
                claimed.add(resolved)
    for source in node.sources:
        if source.issue is not None or source.resolved_path in claimed:
            continue
        # Keep existing skill/command/config roles. A selected README also
        # needs prose checks: its display role does not expose any content.
        block_type = AgentsMdBlock if source.path.name == "AGENTS.md" else CodexInstructionBlock
        if source.resolved_path in readmes:
            parent, readme = readmes[source.resolved_path]
            block = state.add_parser_block(
                parent,
                source.path,
                block_type,
                owner=readme.plugin_owner,
                content_suppressed=readme.content_suppressed,
            )
            if block is not None:
                block.externally_sourced = readme.externally_sourced
        else:
            state.add_block(state.root, source.path, block_type)
        claimed.add(source.resolved_path)
    state.root.children.append(node)
    state.root.invalidate_find_cache()
