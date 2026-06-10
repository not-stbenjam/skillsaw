"""Markdown AST wrapper using markdown-it-py.

Parses markdown once and exposes structural accessors (links, code spans,
fences, headings, HTML comments) and a splice function for surgical edits.
AST for reading; splice for writing — never round-trips the AST back to text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from markdown_it import MarkdownIt


@dataclass(frozen=True)
class MdLink:
    text: str
    href: str
    title: Optional[str]
    file_line: int
    col_start: int
    col_end: int
    href_col_start: int
    href_col_end: int
    is_autolink: bool = False


@dataclass(frozen=True)
class MdCodeSpan:
    content: str
    markup: str
    file_line: int
    col_start: int
    col_end: int


@dataclass(frozen=True)
class MdFence:
    info: str
    content: str
    file_line_start: int
    file_line_end: int


@dataclass(frozen=True)
class MdCodeBlock:
    content: str
    file_line_start: int
    file_line_end: int


@dataclass(frozen=True)
class MdHtmlComment:
    text: str
    file_line_start: int
    file_line_end: int
    col_start: Optional[int] = None
    col_end: Optional[int] = None


@dataclass(frozen=True)
class MdHeading:
    text: str
    level: int
    file_line: int
    is_setext: bool = False


@dataclass(frozen=True)
class MdTextSegment:
    text: str
    file_line: int
    col_start: int
    col_end: int


_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)


class MarkdownDoc:
    __slots__ = (
        "_body",
        "_line_offset",
        "_line_map",
        "_source_lines",
        "_tokens",
        "_cache",
    )

    def __init__(
        self,
        body: str,
        line_offset: int = 0,
        line_map: Optional[Callable[[int], int]] = None,
    ):
        self._body = body
        self._line_offset = line_offset
        self._line_map = line_map
        self._source_lines = body.split("\n")
        self._tokens = MarkdownIt().parse(body)
        self._cache: Dict[str, object] = {}

    def _file_line(self, body_line: int) -> int:
        if self._line_map is not None:
            return self._line_map(body_line)
        return body_line + self._line_offset

    def body_line(self, file_line: int) -> int:
        """Inverse of _file_line: convert file-absolute to 1-based body line."""
        return file_line - self._line_offset

    # ------------------------------------------------------------------
    # Block-level accessors
    # ------------------------------------------------------------------

    def fences(self) -> List[MdFence]:
        if "fences" not in self._cache:
            result: List[MdFence] = []
            for t in self._tokens:
                if t.type == "fence" and t.map:
                    result.append(
                        MdFence(
                            info=t.info.strip(),
                            content=t.content,
                            file_line_start=self._file_line(t.map[0] + 1),
                            file_line_end=self._file_line(t.map[1]),
                        )
                    )
            self._cache["fences"] = result
        return self._cache["fences"]  # type: ignore[return-value]

    def code_blocks(self) -> List[MdCodeBlock]:
        if "code_blocks" not in self._cache:
            result: List[MdCodeBlock] = []
            for t in self._tokens:
                if t.type == "code_block" and t.map:
                    result.append(
                        MdCodeBlock(
                            content=t.content,
                            file_line_start=self._file_line(t.map[0] + 1),
                            file_line_end=self._file_line(t.map[1]),
                        )
                    )
            self._cache["code_blocks"] = result
        return self._cache["code_blocks"]  # type: ignore[return-value]

    def headings(self) -> List[MdHeading]:
        if "headings" not in self._cache:
            result: List[MdHeading] = []
            for i, t in enumerate(self._tokens):
                if t.type == "heading_open" and t.map:
                    text = ""
                    if i + 1 < len(self._tokens) and self._tokens[i + 1].type == "inline":
                        text = self._tokens[i + 1].content
                    result.append(
                        MdHeading(
                            text=text,
                            level=int(t.tag[1]),
                            file_line=self._file_line(t.map[0] + 1),
                            is_setext=t.markup in ("=", "-"),
                        )
                    )
            self._cache["headings"] = result
        return self._cache["headings"]  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Inline accessors (require column glue)
    # ------------------------------------------------------------------

    def links(self) -> List[MdLink]:
        if "links" not in self._cache:
            self._cache["links"] = self._extract_links()
        return self._cache["links"]  # type: ignore[return-value]

    def code_spans(self) -> List[MdCodeSpan]:
        if "code_spans" not in self._cache:
            self._cache["code_spans"] = self._extract_code_spans()
        return self._cache["code_spans"]  # type: ignore[return-value]

    def text_segments(self) -> List[MdTextSegment]:
        if "text_segments" not in self._cache:
            self._cache["text_segments"] = self._extract_text_segments()
        return self._cache["text_segments"]  # type: ignore[return-value]

    def html_comments(self) -> List[MdHtmlComment]:
        if "html_comments" not in self._cache:
            self._cache["html_comments"] = self._extract_html_comments()
        return self._cache["html_comments"]  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # stripped_body / prose_lines
    # ------------------------------------------------------------------

    def stripped_body(self) -> str:
        if "stripped" not in self._cache:
            self._cache["stripped"] = self._build_stripped_body()
        return self._cache["stripped"]  # type: ignore[return-value]

    def prose_lines(self) -> List[Tuple[int, str]]:
        body = self.stripped_body()
        result: List[Tuple[int, str]] = []
        for i, line in enumerate(body.split("\n")):
            result.append((self._file_line(i + 1), line))
        return result

    # ------------------------------------------------------------------
    # span_is_exact_code_content — port of is_inside_inline_code
    # ------------------------------------------------------------------

    def is_inside_code_span(self, file_line: int, col_start: int, col_end: int) -> bool:
        for cs in self.code_spans():
            if cs.file_line != file_line:
                continue
            markup_len = len(cs.markup)
            inner_start = cs.col_start + markup_len
            inner_end = cs.col_end - markup_len
            if inner_start <= col_start and col_end <= inner_end:
                if inner_start == col_start and inner_end == col_end:
                    return False
                return True
        return False

    def code_span_bounds(
        self, file_line: int, col_start: int, col_end: int
    ) -> Optional[Tuple[int, int]]:
        for cs in self.code_spans():
            if cs.file_line != file_line:
                continue
            markup_len = len(cs.markup)
            inner_start = cs.col_start + markup_len
            inner_end = cs.col_end - markup_len
            if inner_start == col_start and inner_end == col_end:
                return (cs.col_start, cs.col_end)
        return None

    # ------------------------------------------------------------------
    # splice
    # ------------------------------------------------------------------

    @staticmethod
    def splice(content: str, edits: Sequence[Tuple[int, int, int, str]]) -> str:
        lines = content.split("\n")
        sorted_edits = sorted(edits, key=lambda e: (e[0], e[1]), reverse=True)
        for file_line, col_start, col_end, replacement in sorted_edits:
            idx = file_line - 1
            if 0 <= idx < len(lines):
                line = lines[idx]
                lines[idx] = line[:col_start] + replacement + line[col_end:]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Column glue internals
    # ------------------------------------------------------------------

    def _compute_prefix_widths(self, inline_token) -> List[int]:
        content = inline_token.content
        content_lines = content.split("\n")
        map_start = inline_token.map[0]

        widths: List[int] = []
        for i, cline in enumerate(content_lines):
            line_idx = map_start + i
            if line_idx >= len(self._source_lines):
                widths.append(0)
                continue
            raw = self._source_lines[line_idx]
            if not cline:
                widths.append(0)
            elif raw.endswith(cline):
                widths.append(len(raw) - len(cline))
            else:
                widths.append(0)
        return widths

    def _content_to_pos(
        self, inline_token, content_offset: int, prefix_widths: List[int]
    ) -> Tuple[int, int]:
        content = inline_token.content
        before = content[:content_offset]
        line_idx = before.count("\n")
        line_start = before.rfind("\n") + 1
        col_in_content = content_offset - line_start

        map_start = inline_token.map[0]
        fl = self._file_line(map_start + line_idx + 1)
        pw = prefix_widths[line_idx] if line_idx < len(prefix_widths) else 0
        return fl, pw + col_in_content

    def _content_to_body_pos(
        self, inline_token, content_offset: int, prefix_widths: List[int]
    ) -> Tuple[int, int]:
        content = inline_token.content
        before = content[:content_offset]
        line_idx = before.count("\n")
        line_start = before.rfind("\n") + 1
        col_in_content = content_offset - line_start

        map_start = inline_token.map[0]
        pw = prefix_widths[line_idx] if line_idx < len(prefix_widths) else 0
        return map_start + line_idx, pw + col_in_content

    @staticmethod
    def _find_backtick_run(content: str, markup: str, start: int) -> int:
        mlen = len(markup)
        idx = start
        while idx <= len(content) - mlen:
            if content[idx : idx + mlen] == markup:
                before_ok = idx == 0 or content[idx - 1] != "`"
                after_ok = idx + mlen >= len(content) or content[idx + mlen] != "`"
                if before_ok and after_ok:
                    return idx
            idx += 1
        return -1

    @staticmethod
    def _find_matching_bracket(content: str, open_pos: int) -> int:
        depth = 1
        i = open_pos + 1
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            elif ch == "\\":
                i += 1
            i += 1
        return i - 1 if depth == 0 else -1

    @staticmethod
    def _find_matching_paren(content: str, open_pos: int) -> int:
        depth = 1
        i = open_pos + 1
        in_angle = False
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == "<":
                in_angle = True
            elif ch == ">":
                in_angle = False
            elif not in_angle:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif ch == "\\":
                    i += 1
            i += 1
        return i - 1 if depth == 0 else -1

    # ------------------------------------------------------------------
    # Inline walk — core column glue
    # ------------------------------------------------------------------

    def _walk_inline(self, inline_token):
        """Walk inline children yielding (kind, obj, content_start, content_end, link_depth).

        kind is 'text', 'code', 'link', 'html', 'image'.
        """
        content = inline_token.content
        children = inline_token.children or []
        pos = 0
        link_depth = 0

        i = 0
        while i < len(children):
            child = children[i]

            if child.type == "softbreak":
                nl = content.find("\n", pos)
                if nl >= 0:
                    pos = nl + 1
                i += 1
                continue

            if child.type == "hardbreak":
                nl = content.find("\n", pos)
                if nl >= 0:
                    pos = nl + 1
                i += 1
                continue

            if child.type == "text":
                idx = content.find(child.content, pos)
                if idx >= 0:
                    yield ("text", child, idx, idx + len(child.content), link_depth)
                    pos = idx + len(child.content)
                i += 1
                continue

            if child.type == "code_inline":
                markup = child.markup
                idx = self._find_backtick_run(content, markup, pos)
                if idx >= 0:
                    close = self._find_backtick_run(content, markup, idx + len(markup))
                    end = close + len(markup) if close >= 0 else len(content)
                    yield ("code", child, idx, end, link_depth)
                    pos = end
                i += 1
                continue

            if child.type == "link_open":
                link_depth += 1
                is_autolink = child.markup == "autolink"

                if is_autolink:
                    idx = content.find("<", pos)
                    close_i = i + 1
                    while close_i < len(children) and children[close_i].type != "link_close":
                        close_i += 1
                    gt = content.find(">", idx + 1) if idx >= 0 else -1
                    end = gt + 1 if gt >= 0 else (idx + 1 if idx >= 0 else pos)
                    yield ("link", child, idx if idx >= 0 else pos, end, link_depth)
                    link_depth -= 1
                    pos = end
                    i = close_i + 1
                    continue

                idx = content.find("[", pos)
                close_i = i + 1
                while close_i < len(children) and children[close_i].type != "link_close":
                    close_i += 1

                if idx < 0:
                    link_depth -= 1
                    i = close_i + 1
                    continue

                text_close = self._find_matching_bracket(content, idx)
                if text_close < 0:
                    link_depth -= 1
                    i = close_i + 1
                    continue

                next_ch = content[text_close + 1] if text_close + 1 < len(content) else ""
                if next_ch == "(":
                    paren_close = self._find_matching_paren(content, text_close + 1)
                    end = paren_close + 1 if paren_close >= 0 else text_close + 2
                elif next_ch == "[":
                    ref_close = content.find("]", text_close + 2)
                    end = ref_close + 1 if ref_close >= 0 else text_close + 2
                else:
                    end = text_close + 1

                yield ("link", child, idx, end, link_depth)
                link_depth -= 1
                pos = end
                i = close_i + 1
                continue

            if child.type == "link_close":
                i += 1
                continue

            if child.type == "html_inline":
                idx = content.find(child.content, pos)
                if idx >= 0:
                    yield ("html", child, idx, idx + len(child.content), link_depth)
                    pos = idx + len(child.content)
                i += 1
                continue

            if child.type == "image":
                idx = content.find("![", pos)
                if idx >= 0:
                    paren_close = (
                        self._find_matching_paren(content, content.find("(", idx))
                        if "(" in content[idx:]
                        else -1
                    )
                    end = paren_close + 1 if paren_close >= 0 else idx + 2
                    yield ("image", child, idx, end, link_depth)
                    pos = end
                i += 1
                continue

            i += 1

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_links(self) -> List[MdLink]:
        result: List[MdLink] = []
        for t in self._tokens:
            if t.type != "inline" or not t.children or not t.map:
                continue
            pw = self._compute_prefix_widths(t)
            content = t.content
            children = t.children
            for kind, child, cstart, cend, _ld in self._walk_inline(t):
                if kind != "link":
                    continue
                href = child.attrs.get("href", "") if child.attrs else ""
                title = child.attrs.get("title") if child.attrs else None
                is_autolink = child.markup == "autolink"

                fl, col_s = self._content_to_pos(t, cstart, pw)
                fl_e, col_e = self._content_to_pos(t, cend, pw)

                link_text = self._collect_link_text(children, child)

                href_cs, href_ce = col_s, col_e
                if not is_autolink:
                    href_cs, href_ce = self._locate_href_in_content(
                        content, cstart, cend, href, title, t, pw
                    )
                else:
                    _, href_cs = self._content_to_pos(t, cstart + 1, pw)
                    _, href_ce = self._content_to_pos(t, cend - 1, pw)

                result.append(
                    MdLink(
                        text=link_text,
                        href=href,
                        title=title,
                        file_line=fl,
                        col_start=col_s,
                        col_end=col_e,
                        href_col_start=href_cs,
                        href_col_end=href_ce,
                        is_autolink=is_autolink,
                    )
                )
        return result

    @staticmethod
    def _collect_link_text(children, link_open_child) -> str:
        parts: List[str] = []
        found = False
        for c in children:
            if c is link_open_child:
                found = True
                continue
            if found:
                if c.type == "link_close":
                    break
                if c.type == "text":
                    parts.append(c.content)
                elif c.type == "softbreak":
                    parts.append("\n")
                elif c.type == "code_inline":
                    parts.append(c.markup + c.content + c.markup)
        return "".join(parts)

    def _locate_href_in_content(
        self,
        content: str,
        link_start: int,
        link_end: int,
        href: str,
        title: Optional[str],
        inline_token,
        prefix_widths: List[int],
    ) -> Tuple[int, int]:
        span = content[link_start:link_end]
        paren_idx = span.find("](")
        if paren_idx < 0:
            fl, cs = self._content_to_pos(inline_token, link_start, prefix_widths)
            return cs, cs + len(span)

        href_start_in_span = paren_idx + 2
        abs_href_start = link_start + href_start_in_span
        while abs_href_start < link_end and content[abs_href_start] in " \t\n":
            abs_href_start += 1

        abs_href_end = abs_href_start + len(href)

        _, hcs = self._content_to_pos(inline_token, abs_href_start, prefix_widths)
        _, hce = self._content_to_pos(inline_token, abs_href_end, prefix_widths)
        return hcs, hce

    def _extract_code_spans(self) -> List[MdCodeSpan]:
        result: List[MdCodeSpan] = []
        for t in self._tokens:
            if t.type != "inline" or not t.children or not t.map:
                continue
            pw = self._compute_prefix_widths(t)
            for kind, child, cstart, cend, _ld in self._walk_inline(t):
                if kind != "code":
                    continue
                fl, col_s = self._content_to_pos(t, cstart, pw)
                _, col_e = self._content_to_pos(t, cend, pw)
                result.append(
                    MdCodeSpan(
                        content=child.content,
                        markup=child.markup,
                        file_line=fl,
                        col_start=col_s,
                        col_end=col_e,
                    )
                )
        return result

    def _extract_text_segments(self) -> List[MdTextSegment]:
        result: List[MdTextSegment] = []
        for t in self._tokens:
            if t.type != "inline" or not t.children or not t.map:
                continue
            pw = self._compute_prefix_widths(t)
            for kind, child, cstart, cend, link_depth in self._walk_inline(t):
                if kind != "text" or link_depth > 0:
                    continue
                fl, col_s = self._content_to_pos(t, cstart, pw)
                _, col_e = self._content_to_pos(t, cend, pw)
                result.append(
                    MdTextSegment(
                        text=child.content,
                        file_line=fl,
                        col_start=col_s,
                        col_end=col_e,
                    )
                )
        return result

    def _extract_html_comments(self) -> List[MdHtmlComment]:
        result: List[MdHtmlComment] = []

        for t in self._tokens:
            if t.type == "html_block" and t.map:
                for m in _COMMENT_RE.finditer(t.content):
                    result.append(
                        MdHtmlComment(
                            text=m.group(1),
                            file_line_start=self._file_line(t.map[0] + 1),
                            file_line_end=self._file_line(t.map[1]),
                        )
                    )

        for t in self._tokens:
            if t.type != "inline" or not t.children or not t.map:
                continue
            pw = self._compute_prefix_widths(t)
            for kind, child, cstart, cend, _ld in self._walk_inline(t):
                if kind != "html":
                    continue
                m = _COMMENT_RE.match(child.content)
                if not m:
                    continue
                fl, col_s = self._content_to_pos(t, cstart, pw)
                _, col_e = self._content_to_pos(t, cend, pw)
                result.append(
                    MdHtmlComment(
                        text=m.group(1),
                        file_line_start=fl,
                        file_line_end=fl,
                        col_start=col_s,
                        col_end=col_e,
                    )
                )

        return result

    # ------------------------------------------------------------------
    # stripped_body builder
    # ------------------------------------------------------------------

    def _build_stripped_body(self) -> str:
        lines = list(self._source_lines)

        for t in self._tokens:
            if t.type in ("fence", "code_block") and t.map:
                for j in range(t.map[0], min(t.map[1], len(lines))):
                    lines[j] = ""

        for t in self._tokens:
            if t.type == "html_block" and t.map:
                for j in range(t.map[0], min(t.map[1], len(lines))):
                    lines[j] = re.sub(r"[^\n]", " ", lines[j])

        for t in self._tokens:
            if t.type != "inline" or not t.children or not t.map:
                continue
            pw = self._compute_prefix_widths(t)
            for kind, child, cstart, cend, _ld in self._walk_inline(t):
                if kind not in ("code", "html"):
                    continue
                start_line, col_s = self._content_to_body_pos(t, cstart, pw)
                end_line, col_e = self._content_to_body_pos(t, cend, pw)
                if start_line == end_line:
                    if 0 <= start_line < len(lines):
                        line = lines[start_line]
                        if col_s < len(line) and col_e <= len(line):
                            span_len = col_e - col_s
                            lines[start_line] = line[:col_s] + " " * span_len + line[col_e:]
                else:
                    for bl in range(start_line, min(end_line + 1, len(lines))):
                        if bl < 0:
                            continue
                        line = lines[bl]
                        if bl == start_line:
                            lines[bl] = line[:col_s] + " " * (len(line) - col_s)
                        elif bl == end_line:
                            lines[bl] = " " * min(col_e, len(line)) + line[col_e:]
                        else:
                            lines[bl] = " " * len(line)

        return "\n".join(lines)
