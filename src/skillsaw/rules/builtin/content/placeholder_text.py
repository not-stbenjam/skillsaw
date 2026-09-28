"""Content placeholder text rule"""

import re
from typing import List

from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.rules.builtin.content_analysis import (
    gather_all_content_blocks,
    patterns_matching_anywhere,
)

# Marker words that, joined by "," or "/", form a list naming markers
# ("TODO, FIXME", "TBD / TODO") rather than leaving one.
_MARKER_WORDS = frozenset({"TODO", "FIXME", "XXX", "TBD", "HACK"})
_LIST_SEPARATORS = ",/"
_LEADING_WORD = re.compile(r"[A-Z]+\b")
_TRAILING_WORD = re.compile(r"\b[A-Z]+$")
# "add to TODO", "the TODO", "your TODO" name the marker as a noun.
_NOUN_DETERMINERS = ("to ", "the ", "a ", "your ")


def _marker_group_end(line: str, end: int) -> int:
    """End of the marker list starting at ``end`` (``TODO/FIXME`` -> after FIXME)."""
    while True:
        rest = line[end:].lstrip()
        if not rest[:1] or rest[0] not in _LIST_SEPARATORS:
            return end
        after = rest[1:].lstrip()
        nxt = _LEADING_WORD.match(after)
        if not nxt or nxt.group() not in _MARKER_WORDS:
            return end
        end = len(line) - len(after) + nxt.end()


def _names_a_marker(line: str, start: int, end: int) -> bool:
    """Whether the marker at ``line[start:end]`` is mentioned, not left.

    Checked in code rather than with lookarounds: a filename
    (``TODO.md``), a list of marker words (``TODO, FIXME``), or a noun
    after a determiner (``add to TODO``). A marker, or list of markers,
    followed by ``:`` or ``(`` is left (``TODO/FIXME: fill in``,
    ``the TODO(alice): ...``) whatever precedes it.
    """
    tail = line[_marker_group_end(line, end) :]
    if tail.lstrip()[:1] == ":" or tail[:1] == "(":
        return False
    after = line[end : end + 2]
    if len(after) == 2 and after[0] == "." and (after[1].islower() or after[1].isdigit()):
        return True
    word = line[start:end]
    if any(sep in line for sep in _LIST_SEPARATORS):
        rest = line[end:].lstrip()
        if rest[:1] and rest[0] in _LIST_SEPARATORS:
            nxt = _LEADING_WORD.match(rest[1:].lstrip())
            if nxt and nxt.group() in _MARKER_WORDS and nxt.group() != word:
                return True
        head = line[:start].rstrip()
        if head[-1:] and head[-1] in _LIST_SEPARATORS:
            prev = _TRAILING_WORD.search(head[:-1].rstrip())
            if prev and prev.group() in _MARKER_WORDS and prev.group() != word:
                return True
    if word == "XXX":
        # "your XXX API key" is a fill-in slot, not a named marker.
        return False
    head = line[:start].lower()
    for det in _NOUN_DETERMINERS:
        if head.endswith(det):
            cut = len(head) - len(det)
            if cut == 0 or not head[cut - 1].isalnum():
                return True
    return False


class ContentPlaceholderTextRule(Rule):
    """Detect TODO markers, bracket placeholders, and unfilled template text"""

    since = "0.9.0"
    repo_types = None

    _MARKER_PATTERNS = [
        (re.compile(r"\bTODO\b"), "TODO marker"),
        (re.compile(r"\bFIXME\b"), "FIXME marker"),
        (re.compile(r"\bXXX\b"), "XXX marker"),
    ]
    _PLACEHOLDER_PATTERNS = _MARKER_PATTERNS + [
        (re.compile(r"\[link\s+here\]", re.IGNORECASE), "Placeholder link"),
        (re.compile(r"\[Insert\s+[^\]]+\]", re.IGNORECASE), "Insert placeholder"),
        (re.compile(r"\[If\s+[^\]]+\]", re.IGNORECASE), "Conditional placeholder"),
        (
            re.compile(
                r"\*(?:TBD|to be added|details to be added|content to be added)\*",
                re.IGNORECASE,
            ),
            "Unfilled template text",
        ),
    ]

    _MARKER_REGEXES = frozenset(p for p, _ in _MARKER_PATTERNS)

    @property
    def rule_id(self) -> str:
        return "content-placeholder-text"

    @property
    def description(self) -> str:
        return "Detect TODO markers, bracket placeholders, and unfilled template text"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for cf in gather_all_content_blocks(context):
            body = cf.read_body(strip_code_blocks=True)
            if not body:
                continue
            active = patterns_matching_anywhere(body, self._PLACEHOLDER_PATTERNS)
            if not active:
                continue
            for line_num, line in enumerate(body.splitlines(), 1):
                if not line.strip():
                    continue
                for pattern, desc in active:
                    if pattern in self._MARKER_REGEXES:
                        match = next(
                            (
                                m
                                for m in pattern.finditer(line)
                                if not _names_a_marker(line, m.start(), m.end())
                            ),
                            None,
                        )
                    else:
                        match = pattern.search(line)
                    if match:
                        violations.append(
                            self.violation(
                                f"Placeholder text ({desc}): '{match.group()}'",
                                block=cf,
                                line=line_num,
                            )
                        )
        return violations
