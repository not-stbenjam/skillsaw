"""Pi's native skill metadata contract, separate from portable Agent Skills."""

from typing import List

from skillsaw.blocks.pi import PiSkillBlock
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.rule import Rule, RuleViolation, Severity


class PiSkillValidRule(Rule):
    """Report metadata that prevents Pi from loading a declared skill."""

    since = "0.21.0"
    repo_types = frozenset({RepositoryType.PI, RepositoryType.PI_PACKAGE})

    @property
    def rule_id(self) -> str:
        return "pi-skill-valid"

    @property
    def description(self) -> str:
        return "Pi skills need parseable frontmatter and a nonempty description"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for block in context.lint_tree.find(PiSkillBlock):
            if block.frontmatter_error:
                violations.append(
                    self.violation(
                        f"Invalid Pi skill frontmatter: {block.frontmatter_error}",
                        block=block,
                        line=block.frontmatter_error_line,
                    )
                )
                continue
            description = block.field_value("description")
            if not isinstance(description, str) or not description.strip():
                violations.append(
                    self.violation(
                        "Pi skips this skill: add a nonempty description in frontmatter",
                        block=block,
                        line=block.key_line("description"),
                    )
                )
        return violations
