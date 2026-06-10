"""Markdown parsing helpers with source spans.

The linter reads Markdown through ``markdown-it-py`` for CommonMark block and
inline semantics, then recovers source columns for targeted fixes.  We never
render Markdown back from the token tree; fixes splice the original text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from markdown_it import MarkdownIt
from markdown_it.token import Token


@dataclass(frozen=True)
class SourceSpan:
    """A single-line source span using file-absolute, 1-based lines."""

    file_line: int
    col_start: int
    col_end: int


@dataclass(frozen=True)
class MarkdownLink:
    text: str
    href: str
    title: str
    file_line: int
    col_start: int
    col_end: int
    destination: SourceSpan
    reference_label: Optional[str] = None


@dataclass(frozen=True)
class MarkdownCodeSpan:
    content: str
    file_line: int
    col_start: int
    col_end: int
    content_col_start: int
    content_col_end: int

    @property
    def source_span(self) -> SourceSpan:
        return SourceSpan(self.file_line, self.col_start, self.col_end)

    @property
    def content_span(self) -> SourceSpan:
        return SourceSpan(self.file_line, self.content_col_start, self.content_col_end)


@dataclass(frozen=True)
class MarkdownFence:
    info: str
    file_line_start: int
    file_line_end: int


@dataclass(frozen=True)
class MarkdownComment:
    content: str
    file_line: int
    col_start: int
    col_end: int
    file_line_end: int


@dataclass(frozen=True)
class MarkdownHeading:
    text: str
    level: int
    file_line: int
    file_line_end: int
    col_start: int
    col_end: int
    style: str


@dataclass(frozen=True)
class MarkdownTextSegment:
    text: str
    file_line: int
    col_start: int
    col_end: int


@dataclass(frozen=True)
class MarkdownEdit:
    file_line: int
    col_start: int
    col_end: int
    replacement: str


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_REFERENCE_DEF_RE = re.compile(
    r"^(?P<indent>[ \t]{0,3})\[(?P<label>[^\]]+)\]:[ \t]*(?P<dest><[^>\n]*>|[^ \t\n]+)"
)


class MarkdownDoc:
    """Parsed Markdown body with file-absolute span helpers."""

    def __init__(
        self,
        body: str,
        *,
        line_offset: int = 0,
        line_map: Optional[Callable[[int], int]] = None,
    ) -> None:
        self.body = body
        self.line_offset = line_offset
        self._line_map = line_map
        self._source_lines = body.splitlines()
        self._line_endings = _split_line_endings(body)
        self._parser = MarkdownIt("commonmark")
        self._env: Dict[str, object] = {}
        self._tokens = self._parser.parse(body, self._env)

    def file_line(self, body_line: int) -> int:
        if self._line_map is not None:
            return self._line_map(body_line)
        return body_line + self.line_offset

    @property
    def tokens(self) -> Sequence[Token]:
        return self._tokens

    def prose_lines(self) -> List[Tuple[int, str]]:
        """Return body lines with non-prose Markdown structures blanked."""
        return [
            (self.file_line(idx + 1), line) for idx, line in enumerate(self._blanked_source_lines())
        ]

    def prose_text(self) -> str:
        """Return the original body with code/comment constructs blanked."""
        blanked = self._blanked_source_lines()
        parts: List[str] = []
        for i, line in enumerate(blanked):
            ending = self._line_endings[i] if i < len(self._line_endings) else ""
            parts.append(line + ending)
        return "".join(parts)

    @cached_property
    def links(self) -> Tuple[MarkdownLink, ...]:
        found: List[MarkdownLink] = []
        for inline in self._inline_tokens():
            children = inline.children or []
            mapping = self._inline_mapping(inline)
            cursor = 0
            idx = 0
            while idx < len(children):
                child = children[idx]
                if child.type != "link_open":
                    idx += 1
                    continue
                href = child.attrGet("href") or ""
                title = child.attrGet("title") or ""
                link_text, close_idx = self._link_text(children, idx)
                match = self._find_link_source(inline.content, cursor, href, title)
                if match is None:
                    idx = close_idx + 1
                    continue
                start, end, dest_start, dest_end, label = match
                source_start = mapping.position(start)
                source_end = mapping.position(end)
                if source_start is None or source_end is None:
                    idx = close_idx + 1
                    continue
                if label is None:
                    dest_pos_start = mapping.position(dest_start)
                    dest_pos_end = mapping.position(dest_end)
                    if dest_pos_start is None or dest_pos_end is None:
                        idx = close_idx + 1
                        continue
                    destination = SourceSpan(dest_pos_start[0], dest_pos_start[1], dest_pos_end[1])
                else:
                    reference = self._reference_destination_spans.get(label.upper())
                    if reference is None:
                        idx = close_idx + 1
                        continue
                    destination = reference
                found.append(
                    MarkdownLink(
                        text=link_text,
                        href=href,
                        title=title,
                        file_line=source_start[0],
                        col_start=source_start[1],
                        col_end=source_end[1],
                        destination=destination,
                        reference_label=label,
                    )
                )
                cursor = end
                idx = close_idx + 1
        return tuple(found)

    @cached_property
    def code_spans(self) -> Tuple[MarkdownCodeSpan, ...]:
        spans: List[MarkdownCodeSpan] = []
        for inline in self._inline_tokens():
            mapping = self._inline_mapping(inline)
            cursor = 0
            for child in inline.children or []:
                if child.type != "code_inline":
                    continue
                match = _find_code_span_source(inline.content, cursor, child.content, child.markup)
                if match is None:
                    continue
                start, end, content_start, content_end = match
                source_start = mapping.position(start)
                source_end = mapping.position(end)
                content_pos_start = mapping.position(content_start)
                content_pos_end = mapping.position(content_end)
                if (
                    source_start is None
                    or source_end is None
                    or content_pos_start is None
                    or content_pos_end is None
                    or source_start[0] != source_end[0]
                    or content_pos_start[0] != content_pos_end[0]
                ):
                    cursor = end
                    continue
                spans.append(
                    MarkdownCodeSpan(
                        content=child.content,
                        file_line=source_start[0],
                        col_start=source_start[1],
                        col_end=source_end[1],
                        content_col_start=content_pos_start[1],
                        content_col_end=content_pos_end[1],
                    )
                )
                cursor = end
        return tuple(spans)

    @cached_property
    def fences(self) -> Tuple[MarkdownFence, ...]:
        fences: List[MarkdownFence] = []
        for token in self._tokens:
            if token.type not in {"fence", "code_block"} or not token.map:
                continue
            start, end = token.map
            fences.append(
                MarkdownFence(
                    info=token.info or "",
                    file_line_start=self.file_line(start + 1),
                    file_line_end=self.file_line(end),
                )
            )
        return tuple(fences)

    @cached_property
    def html_comments(self) -> Tuple[MarkdownComment, ...]:
        comments: List[MarkdownComment] = []
        for token in self._tokens:
            if token.type == "html_block" and token.map and "<!--" in token.content:
                start_line = token.map[0]
                for match in _HTML_COMMENT_RE.finditer(token.content):
                    comments.append(
                        self._comment_from_block_match(start_line, token.content, match)
                    )
            elif token.type == "inline":
                mapping = self._inline_mapping(token)
                cursor = 0
                for child in token.children or []:
                    if child.type != "html_inline" or not child.content.startswith("<!--"):
                        continue
                    loc = token.content.find(child.content, cursor)
                    if loc < 0:
                        continue
                    end = loc + len(child.content)
                    start_pos = mapping.position(loc)
                    end_pos = mapping.position(end)
                    if start_pos and end_pos:
                        comments.append(
                            MarkdownComment(
                                content=child.content[4:-3],
                                file_line=start_pos[0],
                                col_start=start_pos[1],
                                col_end=end_pos[1],
                                file_line_end=end_pos[0],
                            )
                        )
                    cursor = end
        return tuple(comments)

    @cached_property
    def headings(self) -> Tuple[MarkdownHeading, ...]:
        headings: List[MarkdownHeading] = []
        for i, token in enumerate(self._tokens):
            if token.type != "heading_open" or not token.map:
                continue
            inline = self._tokens[i + 1] if i + 1 < len(self._tokens) else None
            text = inline.content if inline is not None and inline.type == "inline" else ""
            level = int(token.tag[1:]) if token.tag.startswith("h") else 0
            start = token.map[0]
            source = self._source_line(start)
            style = "setext" if token.markup in {"=", "-"} else "atx"
            if style == "atx":
                marker = source.find("#")
                col_start = marker if marker >= 0 else 0
                col_end = len(source)
            else:
                col_start = 0
                col_end = len(source)
            headings.append(
                MarkdownHeading(
                    text=text,
                    level=level,
                    file_line=self.file_line(start + 1),
                    file_line_end=self.file_line(token.map[1]),
                    col_start=col_start,
                    col_end=col_end,
                    style=style,
                )
            )
        return tuple(headings)

    @cached_property
    def text_segments(self) -> Tuple[MarkdownTextSegment, ...]:
        segments: List[MarkdownTextSegment] = []
        for inline in self._inline_tokens():
            mapping = self._inline_mapping(inline)
            cursor = 0
            in_link = 0
            for child in inline.children or []:
                if child.type == "link_open":
                    in_link += 1
                    continue
                if child.type == "link_close":
                    in_link = max(0, in_link - 1)
                    continue
                if child.type == "softbreak":
                    cursor = _advance_to_next_line(inline.content, cursor)
                    continue
                if in_link or child.type in {"code_inline", "html_inline"}:
                    source = _child_source_text(child)
                    if source:
                        loc = inline.content.find(source, cursor)
                        if loc >= 0:
                            cursor = loc + len(source)
                    continue
                if child.type != "text" or not child.content:
                    continue
                loc = inline.content.find(child.content, cursor)
                if loc < 0:
                    loc = inline.content.find(child.content)
                if loc < 0:
                    continue
                end = loc + len(child.content)
                self._append_text_segment(segments, mapping, child.content, loc, end)
                cursor = end
        return tuple(segments)

    def span_is_exact_code_content(
        self, file_line: int, col_start: int, col_end: int
    ) -> Optional[SourceSpan]:
        """Return enclosing backtick span when the queried span is exact code content."""
        for span in self.code_spans:
            if (
                span.file_line == file_line
                and span.content_col_start == col_start
                and span.content_col_end == col_end
            ):
                return span.source_span
        return None

    def _inline_tokens(self) -> Iterable[Token]:
        for token in self._tokens:
            if token.type == "inline" and token.map:
                yield token

    def _source_line(self, zero_based_line: int) -> str:
        if zero_based_line < 0 or zero_based_line >= len(self._source_lines):
            return ""
        return self._source_lines[zero_based_line]

    def _inline_mapping(self, token: Token) -> "_InlineMapping":
        assert token.map is not None
        return _InlineMapping(
            inline_content=token.content,
            source_lines=self._source_lines,
            body_start_line=token.map[0],
            file_line=self.file_line,
        )

    def _link_text(self, children: Sequence[Token], open_idx: int) -> Tuple[str, int]:
        pieces: List[str] = []
        depth = 0
        for idx in range(open_idx + 1, len(children)):
            child = children[idx]
            if child.type == "link_open":
                depth += 1
            elif child.type == "link_close":
                if depth == 0:
                    return "".join(pieces), idx
                depth -= 1
            elif child.type == "text":
                pieces.append(child.content)
            elif child.type == "code_inline":
                pieces.append(child.content)
            elif child.type == "softbreak":
                pieces.append("\n")
        return "".join(pieces), open_idx

    def _find_link_source(
        self, source: str, cursor: int, href: str, title: str
    ) -> Optional[Tuple[int, int, int, int, Optional[str]]]:
        for candidate in _iter_link_candidates(source, cursor):
            cand_href = candidate.href
            if candidate.reference_label is not None:
                reference = self._references.get(candidate.reference_label.upper())
                if reference is None:
                    continue
                cand_href = reference[0]
                cand_title = reference[1]
            else:
                cand_title = candidate.title
            if cand_href == href and (cand_title or "") == (title or ""):
                return (
                    candidate.start,
                    candidate.end,
                    candidate.dest_start,
                    candidate.dest_end,
                    candidate.reference_label,
                )
        return None

    @cached_property
    def _references(self) -> Dict[str, Tuple[str, str]]:
        raw = self._env.get("references")
        if not isinstance(raw, dict):
            return {}
        result: Dict[str, Tuple[str, str]] = {}
        for label, value in raw.items():
            if isinstance(value, dict):
                result[str(label).upper()] = (
                    str(value.get("href", "")),
                    str(value.get("title", "")),
                )
        return result

    @cached_property
    def _reference_destination_spans(self) -> Dict[str, SourceSpan]:
        raw = self._env.get("references")
        if not isinstance(raw, dict):
            return {}
        spans: Dict[str, SourceSpan] = {}
        for label, value in raw.items():
            if not isinstance(value, dict):
                continue
            token_map = value.get("map")
            if not isinstance(token_map, list) or not token_map:
                continue
            line_idx = int(token_map[0])
            source = self._source_line(line_idx)
            match = _REFERENCE_DEF_RE.match(source)
            if not match:
                continue
            dest_start = match.start("dest")
            dest_end = match.end("dest")
            if (
                source[dest_start:dest_end].startswith("<")
                and source[dest_end - 1 : dest_end] == ">"
            ):
                dest_start += 1
                dest_end -= 1
            spans[str(label).upper()] = SourceSpan(
                self.file_line(line_idx + 1), dest_start, dest_end
            )
        return spans

    def _comment_from_block_match(
        self, start_line: int, content: str, match: re.Match[str]
    ) -> MarkdownComment:
        before = content[: match.start()]
        line_delta = before.count("\n")
        line_start_idx = before.rfind("\n") + 1
        body_line = start_line + line_delta + 1
        col_start = match.start() - line_start_idx

        matched = match.group(0)
        end_line_delta = matched.count("\n")
        if end_line_delta:
            col_end = len(matched.rsplit("\n", 1)[-1])
        else:
            col_end = col_start + len(matched)
        return MarkdownComment(
            content=matched[4:-3],
            file_line=self.file_line(body_line),
            col_start=col_start,
            col_end=col_end,
            file_line_end=self.file_line(body_line + end_line_delta),
        )

    def _append_text_segment(
        self,
        segments: List[MarkdownTextSegment],
        mapping: "_InlineMapping",
        text: str,
        start: int,
        end: int,
    ) -> None:
        line_start = start
        for piece in text.split("\n"):
            piece_end = line_start + len(piece)
            if piece:
                start_pos = mapping.position(line_start)
                end_pos = mapping.position(piece_end)
                if start_pos and end_pos and start_pos[0] == end_pos[0]:
                    segments.append(
                        MarkdownTextSegment(
                            text=piece,
                            file_line=start_pos[0],
                            col_start=start_pos[1],
                            col_end=end_pos[1],
                        )
                    )
            line_start = piece_end + 1

    def _blanked_source_lines(self) -> List[str]:
        lines = list(self._source_lines)

        def blank_span(span: SourceSpan) -> None:
            body_line = self._body_line_from_file_line(span.file_line)
            if body_line is None or body_line < 1 or body_line > len(lines):
                return
            idx = body_line - 1
            line = lines[idx]
            start = max(0, min(span.col_start, len(line)))
            end = max(start, min(span.col_end, len(line)))
            lines[idx] = line[:start] + (" " * (end - start)) + line[end:]

        for token in self._tokens:
            if token.type in {"fence", "code_block"} and token.map:
                for line_idx in range(token.map[0], token.map[1]):
                    if 0 <= line_idx < len(lines):
                        lines[line_idx] = " " * len(lines[line_idx])

        for span in self.code_spans:
            blank_span(span.source_span)

        for comment in self.html_comments:
            for file_line in range(comment.file_line, comment.file_line_end + 1):
                body_line = self._body_line_from_file_line(file_line)
                if body_line is None or body_line < 1 or body_line > len(lines):
                    continue
                idx = body_line - 1
                line = lines[idx]
                if file_line == comment.file_line:
                    start = comment.col_start
                else:
                    start = 0
                if file_line == comment.file_line_end:
                    end = comment.col_end
                else:
                    end = len(line)
                start = max(0, min(start, len(line)))
                end = max(start, min(end, len(line)))
                lines[idx] = line[:start] + (" " * (end - start)) + line[end:]

        return lines

    def _body_line_from_file_line(self, file_line: int) -> Optional[int]:
        if self._line_map is None:
            return file_line - self.line_offset
        for body_line in range(1, len(self._source_lines) + 1):
            if self._line_map(body_line) == file_line:
                return body_line
        return None


class _InlineMapping:
    def __init__(
        self,
        *,
        inline_content: str,
        source_lines: Sequence[str],
        body_start_line: int,
        file_line: Callable[[int], int],
    ) -> None:
        self._ranges: List[Tuple[int, int, int, int]] = []
        self._inline_content = inline_content
        offset = 0
        inline_lines = inline_content.split("\n")
        for idx, inline_line in enumerate(inline_lines):
            source_idx = body_start_line + idx
            raw = source_lines[source_idx] if 0 <= source_idx < len(source_lines) else ""
            raw_col = raw.find(inline_line) if inline_line else 0
            if raw_col < 0:
                raw_col = _best_effort_column(raw, inline_line)
            line_start = offset
            line_end = offset + len(inline_line)
            self._ranges.append((line_start, line_end, file_line(source_idx + 1), raw_col))
            offset = line_end + 1

    def position(self, index: int) -> Optional[Tuple[int, int]]:
        if index < 0:
            return None
        for line_start, line_end, file_line, raw_col in self._ranges:
            if line_start <= index <= line_end:
                return file_line, raw_col + (index - line_start)
        if index == len(self._inline_content) and self._ranges:
            line_start, line_end, file_line, raw_col = self._ranges[-1]
            return file_line, raw_col + (line_end - line_start)
        return None


@dataclass(frozen=True)
class _LinkCandidate:
    start: int
    end: int
    dest_start: int
    dest_end: int
    href: str
    title: str
    reference_label: Optional[str] = None


def _iter_link_candidates(source: str, cursor: int) -> Iterable[_LinkCandidate]:
    pos = cursor
    while pos < len(source):
        start = source.find("[", pos)
        if start < 0:
            return
        if start > 0 and source[start - 1] == "!":
            pos = start + 1
            continue
        label_end = _find_closing_bracket(source, start)
        if label_end is None:
            pos = start + 1
            continue
        after = label_end + 1
        if after < len(source) and source[after] == "(":
            parsed = _parse_inline_link_destination(source, start, after)
            if parsed is not None:
                yield parsed
                pos = parsed.end
                continue
        elif after < len(source) and source[after] == "[":
            ref_end = source.find("]", after + 1)
            if ref_end >= 0:
                raw_label = source[after + 1 : ref_end]
                if raw_label == "":
                    raw_label = source[start + 1 : label_end]
                yield _LinkCandidate(
                    start=start,
                    end=ref_end + 1,
                    dest_start=after + 1,
                    dest_end=ref_end,
                    href="",
                    title="",
                    reference_label=_normalize_reference_label(raw_label),
                )
                pos = ref_end + 1
                continue
        raw_label = source[start + 1 : label_end]
        yield _LinkCandidate(
            start=start,
            end=label_end + 1,
            dest_start=start + 1,
            dest_end=label_end,
            href="",
            title="",
            reference_label=_normalize_reference_label(raw_label),
        )
        pos = start + 1


def _find_closing_bracket(source: str, start: int) -> Optional[int]:
    escaped = False
    for idx in range(start + 1, len(source)):
        ch = source[idx]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "]":
            return idx
    return None


def _parse_inline_link_destination(
    source: str, link_start: int, paren_start: int
) -> Optional[_LinkCandidate]:
    pos = paren_start + 1
    while pos < len(source) and source[pos] in " \t\n":
        pos += 1
    if pos >= len(source):
        return None

    if source[pos] == "<":
        dest_start = pos + 1
        close = source.find(">", dest_start)
        if close < 0:
            return None
        dest_end = close
        pos = close + 1
    else:
        dest_start = pos
        depth = 0
        escaped = False
        while pos < len(source):
            ch = source[pos]
            if escaped:
                escaped = False
                pos += 1
                continue
            if ch == "\\":
                escaped = True
                pos += 1
                continue
            if ch in " \t\n" and depth == 0:
                break
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            pos += 1
        dest_end = pos

    title = ""
    while pos < len(source) and source[pos] in " \t\n":
        pos += 1
    if pos < len(source) and source[pos] in {'"', "'"}:
        quote = source[pos]
        title_start = pos + 1
        pos = title_start
        escaped = False
        while pos < len(source):
            ch = source[pos]
            if escaped:
                escaped = False
                pos += 1
                continue
            if ch == "\\":
                escaped = True
                pos += 1
                continue
            if ch == quote:
                title = source[title_start:pos]
                pos += 1
                break
            pos += 1
    elif pos < len(source) and source[pos] == "(":
        title_start = pos + 1
        close = source.find(")", title_start)
        if close < 0:
            return None
        title = source[title_start:close]
        pos = close + 1

    while pos < len(source) and source[pos] in " \t\n":
        pos += 1
    if pos >= len(source) or source[pos] != ")":
        return None
    return _LinkCandidate(
        start=link_start,
        end=pos + 1,
        dest_start=dest_start,
        dest_end=dest_end,
        href=source[dest_start:dest_end],
        title=title,
    )


def _find_code_span_source(
    source: str, cursor: int, content: str, markup: str
) -> Optional[Tuple[int, int, int, int]]:
    tick_count = len(markup) if markup else 1
    opener = "`" * tick_count
    pos = cursor
    while pos < len(source):
        start = source.find(opener, pos)
        if start < 0:
            return None
        content_start = start + tick_count
        end_content = source.find(opener, content_start)
        if end_content < 0:
            return None
        raw_content = source[content_start:end_content]
        normalized = raw_content.replace("\n", " ")
        if normalized.startswith(" ") and normalized.endswith(" ") and normalized.strip():
            normalized = normalized[1:-1]
        if normalized == content:
            return start, end_content + tick_count, content_start, end_content
        pos = content_start
    return None


def _child_source_text(child: Token) -> str:
    if child.type == "code_inline":
        markup = child.markup or "`"
        return f"{markup}{child.content}{markup}"
    if child.type == "html_inline":
        return child.content
    if child.type == "text":
        return child.content
    return ""


def _advance_to_next_line(source: str, cursor: int) -> int:
    loc = source.find("\n", cursor)
    return len(source) if loc < 0 else loc + 1


def _normalize_reference_label(label: str) -> str:
    return " ".join(label.split()).upper()


def _best_effort_column(raw: str, inline_line: str) -> int:
    stripped = inline_line.lstrip()
    if stripped:
        loc = raw.find(stripped)
        if loc >= 0:
            return loc - (len(inline_line) - len(stripped))
    return 0


def _split_line_endings(text: str) -> List[str]:
    endings: List[str] = []
    pos = 0
    while pos < len(text):
        nl = text.find("\n", pos)
        if nl < 0:
            endings.append("")
            break
        if nl > 0 and text[nl - 1] == "\r":
            endings.append("\r\n")
        else:
            endings.append("\n")
        pos = nl + 1
    return endings


def splice(content: str, edits: Iterable[Union[MarkdownEdit, Tuple[int, int, int, str]]]) -> str:
    """Apply single-line file-absolute edits right-to-left."""
    normalized: List[MarkdownEdit] = []
    for edit in edits:
        if isinstance(edit, MarkdownEdit):
            normalized.append(edit)
        else:
            line, start, end, replacement = edit
            normalized.append(MarkdownEdit(line, start, end, replacement))

    lines = content.splitlines(True)
    for edit in sorted(normalized, key=lambda e: (e.file_line, e.col_start), reverse=True):
        idx = edit.file_line - 1
        if idx < 0 or idx >= len(lines):
            continue
        line = lines[idx]
        line_body, ending = _split_line_body_ending(line)
        start = max(0, min(edit.col_start, len(line_body)))
        end = max(start, min(edit.col_end, len(line_body)))
        lines[idx] = line_body[:start] + edit.replacement + line_body[end:] + ending
    return "".join(lines)


def _split_line_body_ending(line: str) -> Tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""
