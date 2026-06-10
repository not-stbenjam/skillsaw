"""Content unlinked internal reference rule"""

import re
from collections import defaultdict
from pathlib import Path, PurePath
from typing import Dict, List, Optional

from skillsaw.rule import AutofixConfidence, AutofixResult, Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.markdown_doc import MarkdownEdit, SourceSpan, splice
from skillsaw.rules.builtin.content_analysis import (
    FileContentBlock,
    gather_all_content_blocks,
)


class ContentUnlinkedInternalReferenceRule(Rule):
    """Detect bare path-like strings that are not wrapped in markdown link syntax"""

    autofix_confidence = AutofixConfidence.SAFE

    formats = None
    since = "0.9.0"
    repo_types = None

    config_schema = {
        "patterns": {
            "type": "list",
            "default": ["./**/*.*", "references/**/*.md"],
            "description": "Glob patterns for path-like strings to flag when unlinked",
        },
    }

    # Match path-like strings: contain / and a file extension, or start with ./
    _PATH_LIKE_RE = re.compile(
        r"(?<!\()"  # not preceded by ( (would be inside link syntax)
        r"(?:"
        r"\./[\w./_-]+"  # starts with ./
        r"|"
        r"[\w._-]+(?:/[\w._-]+)+\.[\w]{1,10}"  # contains / and has extension
        r")"
        r"(?!\))"  # not followed by ) (would be inside link syntax)
    )

    # Detect URLs so we can skip path-like fragments inside them
    _URL_RE = re.compile(r"https?://[^\s)]+")

    @property
    def rule_id(self) -> str:
        return "content-unlinked-internal-reference"

    @property
    def description(self) -> str:
        return "Detect bare path-like strings not wrapped in markdown link syntax"

    def default_severity(self) -> Severity:
        return Severity.INFO

    def _is_inside_url(self, line: str, match_start: int, match_end: int) -> bool:
        """Check if a match position falls inside a URL."""
        for url_match in self._URL_RE.finditer(line):
            if url_match.start() <= match_start and match_end <= url_match.end():
                return True
        return False

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        root = context.root_path.resolve()
        patterns = self.config.get("patterns", self.config_schema["patterns"]["default"])
        violations = []
        for cf in gather_all_content_blocks(context):
            for candidate in self._path_candidates(cf, patterns):
                path_str = candidate.path
                if re.match(r"^\s*@\S", candidate.line_text):
                    continue
                resolved = (cf.path.parent / path_str).resolve()
                file_exists = False
                try:
                    resolved.relative_to(root)
                    file_exists = resolved.exists()
                except ValueError:
                    pass
                msg = f"Unlinked path reference: '{path_str}' — consider wrapping in link syntax [{path_str}]({path_str})"
                if file_exists:
                    msg += " (file exists, autofixable)"
                violations.append(
                    self.violation(
                        msg,
                        block=cf,
                        line=cf.markdown.body_line(candidate.span.file_line),
                    )
                )
        return violations

    def _path_candidates(self, cf, patterns: List[str]) -> List["_PathCandidate"]:
        candidates: List[_PathCandidate] = []
        for segment in cf.markdown.text_segments:
            if not segment.text.strip():
                continue
            for match in self._PATH_LIKE_RE.finditer(segment.text):
                path_str = match.group(0)
                if self._is_inside_url(segment.text, match.start(), match.end()):
                    continue
                if not any(PurePath(path_str).match(p) for p in patterns):
                    continue
                candidates.append(
                    _PathCandidate(
                        path=path_str,
                        span=SourceSpan(
                            segment.file_line,
                            segment.col_start + match.start(),
                            segment.col_start + match.end(),
                        ),
                        line_text=segment.text,
                        code_source_span=None,
                    )
                )

        for code_span in cf.markdown.code_spans:
            if _span_inside_link(code_span.source_span, cf.markdown.links):
                continue
            text = code_span.content
            for match in self._PATH_LIKE_RE.finditer(text):
                if match.start() != 0 or match.end() != len(text):
                    continue
                path_str = match.group(0)
                if not any(PurePath(path_str).match(p) for p in patterns):
                    continue
                candidates.append(
                    _PathCandidate(
                        path=path_str,
                        span=SourceSpan(
                            code_span.file_line,
                            code_span.content_col_start,
                            code_span.content_col_end,
                        ),
                        line_text=text,
                        code_source_span=code_span.source_span,
                    )
                )
        return candidates

    def fix(
        self, context: RepositoryContext, violations: List[RuleViolation], **kwargs: object
    ) -> List[AutofixResult]:
        fixes_by_file: Dict[Path, List[tuple]] = defaultdict(list)
        for v in violations:
            if not v.file_path or "autofixable" not in v.message:
                continue
            path_str = v.message.split("'")[1]
            fixes_by_file[v.file_path].append((path_str, v))

        results: List[AutofixResult] = []
        for fpath, replacements in fixes_by_file.items():
            try:
                content = fpath.read_text(encoding="utf-8")
            except OSError:
                continue
            violations_fixed = []
            edits: List[MarkdownEdit] = []
            block = FileContentBlock(path=fpath, category="file", body=content)
            candidates_by_line_path: Dict[tuple[int, str], List[_PathCandidate]] = defaultdict(list)
            patterns = self.config.get("patterns", self.config_schema["patterns"]["default"])
            for candidate in self._path_candidates(block, patterns):
                candidates_by_line_path[(candidate.span.file_line, candidate.path)].append(
                    candidate
                )

            for path_str, v in replacements:
                fl = v.file_line
                if fl is None:
                    continue
                candidates = candidates_by_line_path.get((fl, path_str), [])
                if not candidates:
                    continue
                candidate = candidates.pop(0)
                if candidate.code_source_span is not None:
                    line = content.splitlines()[candidate.code_source_span.file_line - 1]
                    source_text = line[
                        candidate.code_source_span.col_start : candidate.code_source_span.col_end
                    ]
                    edits.append(
                        MarkdownEdit(
                            candidate.code_source_span.file_line,
                            candidate.code_source_span.col_start,
                            candidate.code_source_span.col_end,
                            f"[{source_text}]({path_str})",
                        )
                    )
                else:
                    edits.append(
                        MarkdownEdit(
                            candidate.span.file_line,
                            candidate.span.col_start,
                            candidate.span.col_end,
                            f"[{path_str}]({path_str})",
                        )
                    )
                violations_fixed.append(v)
            fixed = splice(content, edits)
            if fixed != content:
                results.append(
                    AutofixResult(
                        rule_id=self.rule_id,
                        file_path=fpath,
                        confidence=AutofixConfidence.SAFE,
                        original_content=content,
                        fixed_content=fixed,
                        description=f"Wrap {len(violations_fixed)} bare path(s) in markdown link syntax",
                        violations_fixed=violations_fixed,
                    )
                )
        return results


class _PathCandidate:
    def __init__(
        self,
        *,
        path: str,
        span: SourceSpan,
        line_text: str,
        code_source_span: Optional[SourceSpan],
    ) -> None:
        self.path = path
        self.span = span
        self.line_text = line_text
        self.code_source_span = code_source_span


def _span_inside_link(span: SourceSpan, links) -> bool:
    for link in links:
        if (
            span.file_line == link.file_line
            and link.col_start <= span.col_start
            and span.col_end <= link.col_end
        ):
            return True
    return False
