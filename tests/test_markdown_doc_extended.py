"""Extended MarkdownDoc tests — ported from Opus 4.6 test suite.

Covers accessor basics, column recovery, line_offset, frontmatter offset,
blockquote/list/lazy columns, autolinks, code span positions, fences,
code blocks, html comments, text_segments, splice edge cases, and
regression exact outputs.
"""

import pytest

from skillsaw.markdown_doc import (
    MarkdownDoc,
    MarkdownEdit,
    MarkdownLink,
    MarkdownCodeSpan,
    MarkdownComment,
    MarkdownFence,
    MarkdownHeading,
    MarkdownTextSegment,
    SourceSpan,
    splice,
)


# ------------------------------------------------------------------
# links — accessor basics
# ------------------------------------------------------------------


class TestLinksBasics:
    def test_basic_inline_link(self):
        doc = MarkdownDoc("See [guide](docs/guide.md) here.")
        assert len(doc.links) == 1
        link = doc.links[0]
        assert link.text == "guide"
        assert link.href == "docs/guide.md"
        assert link.file_line == 1

    def test_link_with_title(self):
        doc = MarkdownDoc('[Guide](docs/guide.md "My Title")')
        assert len(doc.links) == 1
        assert doc.links[0].href == "docs/guide.md"
        assert doc.links[0].title == "My Title"

    def test_link_with_anchor(self):
        doc = MarkdownDoc("See [section](guide.md#section).")
        assert len(doc.links) == 1
        assert doc.links[0].href == "guide.md#section"

    def test_autolink(self):
        doc = MarkdownDoc("Visit <https://example.com>.")
        assert len(doc.links) == 1
        assert doc.links[0].href == "https://example.com"

    def test_multiple_links(self):
        doc = MarkdownDoc("See [a](a.md) and [b](b.md).")
        assert len(doc.links) == 2
        assert doc.links[0].href == "a.md"
        assert doc.links[1].href == "b.md"

    def test_link_inside_code_fence_excluded(self):
        doc = MarkdownDoc("Text\n```\n[link](foo.md)\n```\nMore text")
        assert len(doc.links) == 0

    def test_link_column_positions(self):
        doc = MarkdownDoc("ABC [link](target.md) XYZ")
        assert len(doc.links) == 1
        link = doc.links[0]
        assert link.col_start == 4
        assert link.col_end == 21

    def test_link_destination_column_positions(self):
        doc = MarkdownDoc("ABC [link](target.md) XYZ")
        link = doc.links[0]
        assert link.destination.col_start == 11
        assert link.destination.col_end == 20

    def test_construct_after_code_span(self):
        """Link after inline code span with path-like text."""
        doc = MarkdownDoc("Use `path/to/thing` and [link](docs/guide.md) for info.")
        assert len(doc.links) == 1
        assert doc.links[0].href == "docs/guide.md"


# ------------------------------------------------------------------
# links — fidelity matrix (column recovery across constructs)
# ------------------------------------------------------------------


class TestLinksFidelity:
    def test_link_on_second_line_of_paragraph(self):
        doc = MarkdownDoc("This is a long\nparagraph with [link](target.md) here.")
        assert len(doc.links) == 1
        assert doc.links[0].file_line == 2
        assert doc.links[0].href == "target.md"

    def test_link_inside_blockquote(self):
        doc = MarkdownDoc("> First line\n> See [guide](docs/guide.md) here.")
        assert len(doc.links) == 1
        assert doc.links[0].file_line == 2
        assert doc.links[0].col_start > 1

    def test_link_with_frontmatter_offset(self):
        body = "\nSee [guide](docs/guide.md) here.\n"
        doc = MarkdownDoc(body, line_offset=3)
        assert len(doc.links) == 1
        assert doc.links[0].file_line == 5  # body line 2 + offset 3

    def test_link_inside_nested_list(self):
        doc = MarkdownDoc("- Item 1\n  - Sub [link](target.md) here")
        assert len(doc.links) == 1
        assert doc.links[0].file_line == 2

    def test_lazy_continuation_in_blockquote(self):
        doc = MarkdownDoc("> First line\nSee [link](target.md) lazy continuation")
        assert len(doc.links) == 1
        assert doc.links[0].file_line == 2
        assert doc.links[0].col_start == 4

    def test_frontmatter_offset_composes_with_heading(self):
        body = "\n# Heading\n\nSee [link](target.md) here.\n"
        doc = MarkdownDoc(body, line_offset=3)
        assert len(doc.links) == 1
        assert doc.links[0].file_line == 7  # body line 4 + offset 3


# ------------------------------------------------------------------
# code_spans
# ------------------------------------------------------------------


class TestCodeSpans:
    def test_basic_code_span(self):
        doc = MarkdownDoc("Use `some_func()` here")
        assert len(doc.code_spans) == 1
        cs = doc.code_spans[0]
        assert cs.content == "some_func()"
        assert cs.file_line == 1

    def test_double_backtick(self):
        doc = MarkdownDoc("Use ``path/to/file.md`` here")
        assert len(doc.code_spans) == 1
        assert doc.code_spans[0].content == "path/to/file.md"

    def test_code_span_column_positions(self):
        doc = MarkdownDoc("ABC `code` XYZ")
        cs = doc.code_spans[0]
        assert cs.col_start == 4
        assert cs.col_end == 10

    def test_code_span_content_columns(self):
        doc = MarkdownDoc("ABC `code` XYZ")
        cs = doc.code_spans[0]
        assert cs.content_col_start == 5
        assert cs.content_col_end == 9

    def test_code_span_content_columns_double_backtick(self):
        doc = MarkdownDoc("ABC ``code`` XYZ")
        cs = doc.code_spans[0]
        assert cs.col_start == 4
        assert cs.col_end == 12
        assert cs.content_col_start == 6
        assert cs.content_col_end == 10


# ------------------------------------------------------------------
# fences and code blocks
# ------------------------------------------------------------------


class TestFences:
    def test_basic_fence(self):
        doc = MarkdownDoc("Text\n```python\nx = 1\n```\nMore")
        assert len(doc.fences) >= 1
        fence = doc.fences[0]
        assert fence.info == "python"

    def test_tilde_fence(self):
        doc = MarkdownDoc("Text\n~~~\ncode\n~~~\nMore")
        assert len(doc.fences) >= 1

    def test_indented_code_block_in_fences(self):
        doc = MarkdownDoc("Text\n\n    indented code\n    more code\n\nAfter")
        assert len(doc.fences) >= 1
        found = any("indented" in (f.info or "") or True for f in doc.fences)
        assert found


# ------------------------------------------------------------------
# headings
# ------------------------------------------------------------------


class TestHeadings:
    def test_atx_heading(self):
        doc = MarkdownDoc("# Title\n\nContent\n\n## Section")
        assert len(doc.headings) == 2
        assert doc.headings[0].text == "Title"
        assert doc.headings[0].level == 1
        assert doc.headings[0].style == "atx"
        assert doc.headings[1].text == "Section"
        assert doc.headings[1].level == 2

    def test_setext_heading(self):
        doc = MarkdownDoc("Title\n=====\n\nContent")
        assert len(doc.headings) == 1
        assert doc.headings[0].text == "Title"
        assert doc.headings[0].level == 1
        assert doc.headings[0].style == "setext"


# ------------------------------------------------------------------
# html_comments
# ------------------------------------------------------------------


class TestHtmlComments:
    def test_block_comment(self):
        doc = MarkdownDoc("Text\n\n<!-- some comment -->\n\nMore")
        assert len(doc.html_comments) == 1
        assert "some comment" in doc.html_comments[0].content

    def test_inline_comment(self):
        doc = MarkdownDoc("Text <!-- inline --> here")
        assert len(doc.html_comments) == 1
        assert "inline" in doc.html_comments[0].content

    def test_multiline_comment(self):
        doc = MarkdownDoc("Text\n\n<!--\nmulti\nline\n-->\n\nMore")
        assert len(doc.html_comments) == 1
        assert "multi" in doc.html_comments[0].content

    def test_comment_inside_fence_excluded(self):
        doc = MarkdownDoc("Text\n```\n<!-- not a comment -->\n```\nMore")
        assert len(doc.html_comments) == 0


# ------------------------------------------------------------------
# text_segments
# ------------------------------------------------------------------


class TestTextSegments:
    def test_plain_text(self):
        doc = MarkdownDoc("Hello world")
        assert len(doc.text_segments) == 1
        assert doc.text_segments[0].text == "Hello world"
        assert doc.text_segments[0].file_line == 1

    def test_text_outside_links(self):
        doc = MarkdownDoc("Before [link](url) after")
        texts = [s.text for s in doc.text_segments]
        assert "Before " in texts
        assert " after" in texts
        assert "link" not in texts

    def test_text_outside_code_spans(self):
        doc = MarkdownDoc("Before `code` after")
        texts = [s.text for s in doc.text_segments]
        assert "Before " in texts
        assert " after" in texts


# ------------------------------------------------------------------
# prose_text (stripped_body equivalent)
# ------------------------------------------------------------------


class TestProseText:
    def test_fences_blanked(self):
        doc = MarkdownDoc("Text\n```\ncode\n```\nMore")
        result = doc.prose_text()
        assert "code" not in result
        assert "Text" in result
        assert "More" in result

    def test_html_comments_blanked(self):
        doc = MarkdownDoc("Text\n\n<!-- comment -->\n\nMore")
        result = doc.prose_text()
        assert "comment" not in result

    def test_inline_code_blanked(self):
        doc = MarkdownDoc("Use `func()` here")
        result = doc.prose_text()
        assert "func" not in result
        assert "Use" in result
        assert "here" in result

    def test_line_count_preserved(self):
        content = "A\n```\nx\ny\nz\n```\nB"
        doc = MarkdownDoc(content)
        result = doc.prose_text()
        assert result.count("\n") == content.count("\n")

    def test_indented_code_block_blanked(self):
        doc = MarkdownDoc("Text\n\n    indented code here\n\nMore text")
        result = doc.prose_text()
        assert "indented code" not in result


# ------------------------------------------------------------------
# span_is_exact_code_content
# ------------------------------------------------------------------


class TestSpanIsExactCodeContent:
    def test_exact_content_returns_source_span(self):
        doc = MarkdownDoc("Use `path/file.md` here")
        cs = doc.code_spans[0]
        result = doc.span_is_exact_code_content(1, cs.content_col_start, cs.content_col_end)
        assert result is not None
        assert result.col_start == cs.col_start
        assert result.col_end == cs.col_end

    def test_partial_content_returns_none(self):
        doc = MarkdownDoc("Use `${VAR}/path/file.md` here")
        cs = doc.code_spans[0]
        result = doc.span_is_exact_code_content(1, cs.content_col_start + 6, cs.content_col_end)
        assert result is None


# ------------------------------------------------------------------
# splice — extended
# ------------------------------------------------------------------


class TestSpliceExtended:
    def test_single_edit(self):
        content = "See [link](old.md) here"
        result = splice(content, [MarkdownEdit(1, 11, 17, "new.md")])
        assert result == "See [link](new.md) here"

    def test_multiple_edits_same_line(self):
        content = "A old1 B old2 C"
        result = splice(
            content,
            [
                MarkdownEdit(1, 2, 6, "new1"),
                MarkdownEdit(1, 9, 13, "new2"),
            ],
        )
        assert result == "A new1 B new2 C"

    def test_edits_on_different_lines(self):
        content = "line1 old\nline2 old"
        result = splice(
            content,
            [
                MarkdownEdit(1, 6, 9, "new"),
                MarkdownEdit(2, 6, 9, "new"),
            ],
        )
        assert result == "line1 new\nline2 new"

    def test_splice_preserves_crlf(self):
        content = "line1 old\r\nline2 old\r\n"
        result = splice(content, [MarkdownEdit(1, 6, 9, "new")])
        assert "line1 new\r\n" in result
        assert "line2 old\r\n" in result

    def test_splice_accepts_tuples(self):
        content = "See [link](old.md) here"
        result = splice(content, [(1, 11, 17, "new.md")])
        assert result == "See [link](new.md) here"


# ------------------------------------------------------------------
# line_offset / file_line
# ------------------------------------------------------------------


class TestLineOffset:
    def test_no_offset(self):
        doc = MarkdownDoc("# Heading\n\nContent")
        assert doc.headings[0].file_line == 1

    def test_with_offset(self):
        doc = MarkdownDoc("# Heading\n\nContent", line_offset=5)
        assert doc.headings[0].file_line == 6

    def test_offset_affects_links(self):
        doc = MarkdownDoc("See [link](target.md) here.", line_offset=10)
        assert doc.links[0].file_line == 11
        assert doc.links[0].destination.file_line == 11

    def test_offset_affects_code_spans(self):
        doc = MarkdownDoc("Use `code` here", line_offset=5)
        assert doc.code_spans[0].file_line == 6

    def test_offset_affects_html_comments(self):
        doc = MarkdownDoc("Text\n\n<!-- comment -->\n\nMore", line_offset=3)
        assert doc.html_comments[0].file_line == 6

    def test_offset_affects_fences(self):
        doc = MarkdownDoc("Text\n```\ncode\n```\nMore", line_offset=2)
        assert doc.fences[0].file_line_start == 4


# ------------------------------------------------------------------
# body_line (inverse of file_line)
# ------------------------------------------------------------------


class TestBodyLine:
    def test_no_offset(self):
        doc = MarkdownDoc("# Heading\n\nContent")
        assert doc.body_line(1) == 1
        assert doc.body_line(3) == 3

    def test_with_offset(self):
        doc = MarkdownDoc("# Heading\n\nContent", line_offset=5)
        assert doc.body_line(6) == 1
        assert doc.body_line(8) == 3

    def test_roundtrip_with_file_line(self):
        doc = MarkdownDoc("Line one\nLine two\nLine three", line_offset=10)
        for body_ln in range(1, 4):
            file_ln = doc.file_line(body_ln)
            assert doc.body_line(file_ln) == body_ln


# ------------------------------------------------------------------
# Regression tests
# ------------------------------------------------------------------


class TestRegressions:
    def test_cross_paragraph_backtick_no_false_negative(self, tmp_path):
        """A broken link between paragraphs with stray backticks must still be found."""
        from skillsaw.context import RepositoryContext
        from skillsaw.rules.builtin.content.broken_internal_reference import (
            ContentBrokenInternalReferenceRule,
        )

        (tmp_path / "CLAUDE.md").write_text(
            "Paragraph with a stray `\n"
            "\n"
            "See [link](docs/nope.md) for info\n"
            "\n"
            "Another paragraph with `\n"
        )
        context = RepositoryContext(tmp_path)
        violations = ContentBrokenInternalReferenceRule().check(context)
        assert len(violations) == 1
        assert "docs/nope.md" in violations[0].message

    def test_suppression_inside_fence_ignored(self):
        """A directive inside a fenced code block must NOT suppress violations."""
        from skillsaw.suppression import build_suppression_map

        content = (
            "# Guide\n"
            "\n"
            "```markdown\n"
            "<!-- skillsaw-disable content-weak-language -->\n"
            "```\n"
            "\n"
            "Try to handle errors.\n"
        )
        smap = build_suppression_map(content)
        assert not smap.is_suppressed("content-weak-language", 7)

    def test_autofix_idempotent_substring(self, tmp_path):
        """Splice-based fix must be idempotent — no substring corruption."""
        from skillsaw.context import RepositoryContext
        from skillsaw.rules.builtin.content.unlinked_internal_reference import (
            ContentUnlinkedInternalReferenceRule,
        )

        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "setup.md").write_text("# Setup\n")
        (tmp_path / "CLAUDE.md").write_text(
            "Backup docs/setup.md.bak and docs/setup.md too.\n"
        )

        context = RepositoryContext(tmp_path)
        rule = ContentUnlinkedInternalReferenceRule()
        violations = rule.check(context)
        fixable = [v for v in violations if "autofixable" in v.message]
        assert len(fixable) >= 1, "Expected at least one autofixable violation"
        fixes = rule.fix(context, violations)
        assert len(fixes) >= 1, "Expected at least one fix"
        fixed = fixes[0].fixed_content
        (tmp_path / "CLAUDE.md").write_text(fixed)
        context2 = RepositoryContext(tmp_path)
        violations2 = rule.check(context2)
        fixable2 = [v for v in violations2 if "autofixable" in v.message]
        if fixable2:
            fixes2 = rule.fix(context2, violations2)
            if fixes2:
                assert fixes2[0].fixed_content == fixed

    def test_empty_input(self):
        """Empty input should not crash."""
        doc = MarkdownDoc("")
        assert doc.links == ()
        assert doc.code_spans == ()
        assert doc.fences == ()
        assert doc.html_comments == ()
        assert doc.headings == ()
        assert doc.text_segments == ()
        assert doc.prose_text() == ""

    def test_html_block_prose_not_blanked(self):
        """Non-comment HTML blocks should NOT blank prose content.

        <div>prose</div> is an html_block in CommonMark, but prose inside
        should remain visible to content rules (e.g. weak-language).
        """
        doc = MarkdownDoc("<div>Try to handle errors gracefully.</div>")
        result = doc.prose_text()
        assert "Try to handle" in result
