"""Content actionability score rule"""

import re
from typing import List

from skillsaw.rule import AutofixConfidence, Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.content_analysis import (
    gather_all_content_blocks,
)


class ContentActionabilityScoreRule(Rule):
    """Compute an actionability score for instruction files"""

    autofix_confidence = AutofixConfidence.LLM

    formats = None
    since = "0.7.0"
    baseline_mode = "floor"

    @property
    def llm_fix_prompt(self):
        return (
            "You are improving AI coding assistant instruction files that have "
            "low actionability scores. Make instructions more actionable by "
            "adding specific commands, file paths, and concrete actions.\n\n"
            "Rules:\n"
            "- Replace vague prose with imperative instructions\n"
            "- Add specific commands (e.g., `npm test`, `make lint`)\n"
            "- Add file paths where relevant (e.g., `src/config.ts`)\n"
            "- Convert descriptions into action items\n"
            "- Do NOT add instructions that don't match the project\n"
            "- Preserve markdown formatting"
        )

    _VERB_RE = re.compile(
        r"\b(?:use|run|create|add|remove|check|set|write|read|call|return|throw|"
        r"avoid|prefer|include|exclude|follow|implement|test|validate|verify|"
        r"handle|log|format|configure|install|update|delete|move|copy|import|"
        r"export|define|declare|initialize|override|extend|wrap|deploy|build|"
        r"commit|push|pull|merge|rebase|review|ensure|make|keep|always|never)\b",
        re.IGNORECASE,
    )
    _COMMAND_RE = re.compile(r"`[^`]+`")
    _PATH_RE = re.compile(r"(?:`[^`]*[/\\][^`]*`|[\w./\\]+\.\w{1,5})")
    WARN_THRESHOLD = 40

    @property
    def rule_id(self) -> str:
        return "content-actionability-score"

    @property
    def description(self) -> str:
        return "Score instruction files on actionability (verb density, commands, file references)"

    def default_severity(self) -> Severity:
        return Severity.INFO

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for cf in gather_all_content_blocks(context):
            body = cf.read_body()
            if not body:
                continue
            line_pairs = [(i, line) for i, line in enumerate(body.splitlines(), 1) if line.strip()]
            if len(line_pairs) < 5:
                continue
            code_lines = {
                cf.markdown.body_line(span.file_line)
                for span in cf.markdown.code_spans
                if span.content.strip()
            }
            code_path_lines = {
                cf.markdown.body_line(span.file_line)
                for span in cf.markdown.code_spans
                if self._PATH_RE.search(span.content)
            }
            total = len(line_pairs)
            verb_lines = sum(1 for _line_num, line in line_pairs if self._VERB_RE.search(line))
            cmd_lines = sum(
                1
                for line_num, line in line_pairs
                if self._COMMAND_RE.search(line) or line_num in code_lines
            )
            path_lines = sum(
                1
                for line_num, line in line_pairs
                if self._PATH_RE.search(line) or line_num in code_path_lines
            )

            verb_ratio = verb_lines / total
            cmd_ratio = cmd_lines / total
            path_ratio = path_lines / total
            score = int((verb_ratio * 50) + (cmd_ratio * 30) + (path_ratio * 20))
            score = min(100, score)

            if score < self.WARN_THRESHOLD:
                violations.append(
                    self.violation(
                        f"Low actionability score: {score}/100 (verbs: {verb_ratio:.0%}, commands: {cmd_ratio:.0%}, paths: {path_ratio:.0%})",
                        block=cf,
                        value=score,
                    )
                )
        return violations
