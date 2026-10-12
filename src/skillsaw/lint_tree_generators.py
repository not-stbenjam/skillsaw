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
        if project.config is not None:
            state.add_block(
                state.root,
                project.config,
                RulerConfigBlock if ruler else RulesyncConfigBlock,
            )
        for path in project.rules:
            state.add_block(state.root, path, RulerRuleBlock if ruler else RulesyncRuleBlock)
