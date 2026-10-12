"""Attach authored generator sources before generic instruction-file sweeps."""

from skillsaw.blocks.generators import (
    RulerConfigBlock,
    RulerRuleBlock,
    RulesyncConfigBlock,
    RulesyncRuleBlock,
)


def attach_generator_sources(state):
    for project in state.context.generator_projects():
        ruler = project.generator == "ruler"
        for path in project.rules:
            state.add_block(state.root, path, RulerRuleBlock if ruler else RulesyncRuleBlock)
            resolved = state.resolve_repo_path(path)
            if resolved is not None:
                state.generator_source_paths.add(resolved)


def attach_generator_configs(state):
    """Add independent config parsers after native consumers, before extra prose."""
    for project in state.context.generator_projects():
        ruler = project.generator == "ruler"
        if project.config is not None:
            block = state.add_parser_block(
                state.root,
                project.config,
                RulerConfigBlock if ruler else RulesyncConfigBlock,
            )
            if block is not None:
                state.seen.add(block.resolved_path)
