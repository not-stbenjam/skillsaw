"""
Rule: instruction-file-valid
"""

from typing import List

from skillsaw.blocks import CodexInstructionBlock, ContentBlock, FrontmatteredBlock
from skillsaw.codex_instructions import CodexInstructionsNode
from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext, INSTRUCTION_REPO_TYPES
from skillsaw.repository_types import RepositoryType
from skillsaw.rules.builtin.content_analysis import DevinGlobalRuleBlock, InstructionBlock
from skillsaw.rules.builtin.utils import read_text

from ._helpers import is_instruction_filename


class InstructionFileValidRule(Rule):
    """Check that instruction files are valid UTF-8 and non-empty"""

    repo_types = INSTRUCTION_REPO_TYPES | {RepositoryType.CODEX_PROJECT}

    @property
    def rule_id(self) -> str:
        return "instruction-file-valid"

    @property
    def description(self) -> str:
        return (
            "Instruction files (AGENTS.md and tool-compatible alternatives) "
            "must be valid and non-empty"
        )

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        tree = context.lint_tree
        selected = {
            source.resolved_path
            for node in tree.find(CodexInstructionsNode)
            for source in node.sources
            if source.issue is None and source.resolved_path is not None
        }
        blocks = tree.find(InstructionBlock)
        if selected:
            # A selected command or skill keeps its parser role. Empty and
            # unreadable frontmattered files have no BodyContent child.
            for block_type in (ContentBlock, FrontmatteredBlock):
                blocks.extend(b for b in tree.find(block_type) if b.resolved_path in selected)
        seen = set()
        for block in blocks:
            recognized = isinstance(block, InstructionBlock) and (
                isinstance(block, (CodexInstructionBlock, DevinGlobalRuleBlock))
                or is_instruction_filename(block.path.name)
            )
            if not recognized and block.resolved_path not in selected:
                continue
            if block.resolved_path in seen:
                continue
            seen.add(block.resolved_path)

            content = read_text(block.path)
            if content is None:
                violations.append(
                    self.violation(
                        f"Failed to read {block.path.name} (invalid encoding or I/O error)",
                        file_path=block.path,
                    )
                )
                continue

            if not content.strip():
                violations.append(
                    self.violation(f"{block.path.name} is empty", file_path=block.path)
                )

        return violations
