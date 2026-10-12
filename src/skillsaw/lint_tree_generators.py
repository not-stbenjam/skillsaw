"""Attach independent generator source and configuration parser roles."""

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
            # A source may also be a native instruction or an alias of a
            # consumer config. Preserve both interpretations: their decoded
            # fields, frontmatter and whole-file views need different checks.
            state.add_parser_block(
                state.root,
                path,
                RulerRuleBlock if ruler else RulesyncRuleBlock,
                preserve_content_aliases=True,
            )


def attach_generator_configs(state):
    """Add independent config parsers after native consumers, before extra prose."""
    for project in state.context.generator_projects():
        ruler = project.generator == "ruler"
        if project.config is not None:
            state.add_parser_block(
                state.root,
                project.config,
                RulerConfigBlock if ruler else RulesyncConfigBlock,
                preserve_content_aliases=True,
            )
