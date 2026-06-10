"""Tests for MarkdownDoc — the AST wrapper for markdown-it-py."""

import pytest

from skillsaw.markdown_doc import (
    MarkdownDoc,
    MdLink,
    MdCodeSpan,
    MdFence,
    MdCodeBlock,
    MdHtmlComment,
    MdHeading,
    MdTextSegment,
)

# ------------------------------------------------------------------
# links()
# ------------------------------------------------------------------


class TestLinks:
    def test_basic_inline_link(self):
        md = MarkdownDoc("See [guide](docs/guide.md) here.")
        links = md.links()
        assert len(links) == 1
        assert links[0].text == "guide"
        assert links[0].href == "docs/guide.md"
        assert links[0].is_autolink is False
        assert links[0].file_line == 1

    def test_link_with_title(self):
        md = MarkdownDoc('[Guide](docs/guide.md "My Title")')
        links = md.links()
        assert len(links) == 1
        assert links[0].href == "docs/guide.md"
        assert links[0].title == "My Title"

    def test_link_with_anchor(self):
        md = MarkdownDoc("See [section](guide.md#section).")
        links = md.links()
        assert len(links) == 1
        assert links[0].href == "guide.md#section"

    def test_autolink(self):
        md = MarkdownDoc("Visit <https://example.com>.")
        links = md.links()
        assert len(links) == 1
        assert links[0].is_autolink is True
        assert links[0].href == "https://example.com"

    def test_multiple_links(self):
        md = MarkdownDoc("See [a](a.md) and [b](b.md).")
        links = md.links()
        assert len(links) == 2
        assert links[0].href == "a.md"
        assert links[1].href == "b.md"

    def test_link_inside_code_fence_excluded(self):
        md = MarkdownDoc("Text\n```\n[link](foo.md)\n```\nMore text")
        links = md.links()
        assert len(links) == 0

    def test_link_column_positions(self):
        md = MarkdownDoc("ABC [link](target.md) XYZ")
        links = md.links()
        assert len(links) == 1
        assert links[0].col_start == 4
        assert links[0].col_end == 21
        assert links[0].href_col_start == 11
        assert links[0].href_col_end == 20

    def test_link_on_second_line_of_paragraph(self):
        """Fidelity matrix: link on 2nd line of wrapped paragraph."""
        md = MarkdownDoc("This is a long\nparagraph with [link](target.md) here.")
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 2
        assert links[0].href == "target.md"

    def test_link_inside_blockquote(self):
        """Fidelity matrix: link inside blockquote continuation line."""
        md = MarkdownDoc("> First line\n> See [guide](docs/guide.md) here.")
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 2
        col = links[0].col_start
        assert "See [guide](docs/guide.md) here."[col - 2 :].startswith("[guide]")

    def test_link_with_frontmatter_offset(self):
        """Fidelity matrix: body offset by YAML frontmatter."""
        body = "\nSee [guide](docs/guide.md) here.\n"
        md = MarkdownDoc(body, line_offset=3)
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 5  # body line 2 + offset 3

    def test_construct_after_code_span(self):
        """Fidelity matrix: link after inline code span with path-like text."""
        md = MarkdownDoc("Use `path/to/thing` and [link](docs/guide.md) for info.")
        links = md.links()
        assert len(links) == 1
        assert links[0].href == "docs/guide.md"


# ------------------------------------------------------------------
# code_spans()
# ------------------------------------------------------------------


class TestCodeSpans:
    def test_basic_code_span(self):
        md = MarkdownDoc("Use `some_func()` here")
        spans = md.code_spans()
        assert len(spans) == 1
        assert spans[0].content == "some_func()"
        assert spans[0].markup == "`"
        assert spans[0].file_line == 1

    def test_double_backtick(self):
        md = MarkdownDoc("Use ``path/to/file.md`` here")
        spans = md.code_spans()
        assert len(spans) == 1
        assert spans[0].content == "path/to/file.md"
        assert spans[0].markup == "``"

    def test_code_span_column_positions(self):
        md = MarkdownDoc("ABC `code` XYZ")
        spans = md.code_spans()
        assert len(spans) == 1
        assert spans[0].col_start == 4
        assert spans[0].col_end == 10


# ------------------------------------------------------------------
# fences() and code_blocks()
# ------------------------------------------------------------------


class TestFences:
    def test_basic_fence(self):
        md = MarkdownDoc("Text\n```python\nx = 1\n```\nMore")
        fences = md.fences()
        assert len(fences) == 1
        assert fences[0].info == "python"
        assert "x = 1" in fences[0].content

    def test_tilde_fence(self):
        md = MarkdownDoc("Text\n~~~\ncode\n~~~\nMore")
        fences = md.fences()
        assert len(fences) == 1


class TestCodeBlocks:
    def test_indented_code_block(self):
        md = MarkdownDoc("Text\n\n    indented code\n    more code\n\nAfter")
        blocks = md.code_blocks()
        assert len(blocks) == 1
        assert "indented code" in blocks[0].content


# ------------------------------------------------------------------
# headings()
# ------------------------------------------------------------------


class TestHeadings:
    def test_atx_heading(self):
        md = MarkdownDoc("# Title\n\nContent\n\n## Section")
        headings = md.headings()
        assert len(headings) == 2
        assert headings[0].text == "Title"
        assert headings[0].level == 1
        assert headings[1].text == "Section"
        assert headings[1].level == 2

    def test_setext_heading(self):
        md = MarkdownDoc("Title\n=====\n\nContent")
        headings = md.headings()
        assert len(headings) == 1
        assert headings[0].text == "Title"
        assert headings[0].level == 1
        assert headings[0].is_setext is True


# ------------------------------------------------------------------
# html_comments()
# ------------------------------------------------------------------


class TestHtmlComments:
    def test_block_comment(self):
        md = MarkdownDoc("Text\n\n<!-- some comment -->\n\nMore")
        comments = md.html_comments()
        assert len(comments) == 1
        assert "some comment" in comments[0].text

    def test_inline_comment(self):
        md = MarkdownDoc("Text <!-- inline --> here")
        comments = md.html_comments()
        assert len(comments) == 1
        assert "inline" in comments[0].text

    def test_multiline_comment(self):
        md = MarkdownDoc("Text\n\n<!--\nmulti\nline\n-->\n\nMore")
        comments = md.html_comments()
        assert len(comments) == 1
        assert "multi" in comments[0].text

    def test_comment_inside_fence_excluded(self):
        md = MarkdownDoc("Text\n```\n<!-- not a comment -->\n```\nMore")
        comments = md.html_comments()
        assert len(comments) == 0


# ------------------------------------------------------------------
# text_segments()
# ------------------------------------------------------------------


class TestTextSegments:
    def test_plain_text(self):
        md = MarkdownDoc("Hello world")
        segs = md.text_segments()
        assert len(segs) == 1
        assert segs[0].text == "Hello world"
        assert segs[0].file_line == 1

    def test_text_outside_links(self):
        md = MarkdownDoc("Before [link](url) after")
        segs = md.text_segments()
        texts = [s.text for s in segs]
        assert "Before " in texts
        assert " after" in texts
        # Text inside the link is excluded
        assert "link" not in texts

    def test_text_outside_code_spans(self):
        md = MarkdownDoc("Before `code` after")
        segs = md.text_segments()
        texts = [s.text for s in segs]
        assert "Before " in texts
        assert " after" in texts


# ------------------------------------------------------------------
# stripped_body()
# ------------------------------------------------------------------


class TestStrippedBody:
    def test_fences_blanked(self):
        md = MarkdownDoc("Text\n```\ncode\n```\nMore")
        result = md.stripped_body()
        assert "code" not in result
        assert "Text" in result
        assert "More" in result
        assert result.count("\n") == 4

    def test_html_comments_blanked(self):
        md = MarkdownDoc("Text\n\n<!-- comment -->\n\nMore")
        result = md.stripped_body()
        assert "comment" not in result

    def test_inline_code_blanked(self):
        md = MarkdownDoc("Use `func()` here")
        result = md.stripped_body()
        assert "func" not in result
        assert "Use" in result
        assert "here" in result

    def test_line_count_preserved(self):
        md = MarkdownDoc("A\n```\nx\ny\nz\n```\nB")
        result = md.stripped_body()
        assert result.count("\n") == 6

    def test_multiline_inline_code_span(self):
        md = MarkdownDoc("Some `code that\nspans lines` here")
        result = md.stripped_body()
        assert "code that" not in result
        assert "spans lines" not in result


# ------------------------------------------------------------------
# is_inside_code_span / code_span_bounds
# ------------------------------------------------------------------


class TestCodeSpanDetection:
    def test_inside_code_span(self):
        md = MarkdownDoc("Use `${VAR}/path/file.md` here")
        # path/file.md is inside the code span but is NOT the exact content
        spans = md.code_spans()
        assert len(spans) == 1
        markup_len = len(spans[0].markup)
        inner_start = spans[0].col_start + markup_len
        inner_end = spans[0].col_end - markup_len
        assert md.is_inside_code_span(1, inner_start + 6, inner_end) is True

    def test_exact_code_span_content_not_inside(self):
        md = MarkdownDoc("Use `path/file.md` here")
        spans = md.code_spans()
        assert len(spans) == 1
        markup_len = len(spans[0].markup)
        inner_start = spans[0].col_start + markup_len
        inner_end = spans[0].col_end - markup_len
        # Exact content → returns False (should still be linkable)
        assert md.is_inside_code_span(1, inner_start, inner_end) is False

    def test_code_span_bounds_exact(self):
        md = MarkdownDoc("Use `path/file.md` here")
        spans = md.code_spans()
        markup_len = len(spans[0].markup)
        inner_start = spans[0].col_start + markup_len
        inner_end = spans[0].col_end - markup_len
        bounds = md.code_span_bounds(1, inner_start, inner_end)
        assert bounds == (spans[0].col_start, spans[0].col_end)


# ------------------------------------------------------------------
# splice()
# ------------------------------------------------------------------


class TestSplice:
    def test_single_edit(self):
        content = "See [link](old.md) here"
        result = MarkdownDoc.splice(content, [(1, 11, 17, "new.md")])
        assert result == "See [link](new.md) here"

    def test_multiple_edits_same_line(self):
        content = "A old1 B old2 C"
        result = MarkdownDoc.splice(
            content,
            [
                (1, 2, 6, "new1"),
                (1, 9, 13, "new2"),
            ],
        )
        assert result == "A new1 B new2 C"

    def test_edits_on_different_lines(self):
        content = "line1 old\nline2 old"
        result = MarkdownDoc.splice(
            content,
            [
                (1, 6, 9, "new"),
                (2, 6, 9, "new"),
            ],
        )
        assert result == "line1 new\nline2 new"


# ------------------------------------------------------------------
# body_line()
# ------------------------------------------------------------------


class TestBodyLine:
    def test_no_offset(self):
        md = MarkdownDoc("Line 1\nLine 2")
        assert md.body_line(1) == 1
        assert md.body_line(2) == 2

    def test_with_offset(self):
        md = MarkdownDoc("Body line 1\nBody line 2", line_offset=5)
        # file_line 6 = body_line 1 (6 - 5)
        assert md.body_line(6) == 1
        assert md.body_line(7) == 2


# ------------------------------------------------------------------
# Fidelity matrix (from issue #284)
# ------------------------------------------------------------------


class TestFidelityMatrix:
    def test_link_on_wrapped_paragraph_line(self):
        """Link on 2nd/3rd line of wrapped paragraph must report correct line."""
        md = MarkdownDoc(
            "This is a long paragraph that\n"
            "wraps and has a [link](target.md)\n"
            "on the second line."
        )
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 2

    def test_link_inside_blockquote_continuation(self):
        """Link inside blockquote; columns re-add marker width."""
        md = MarkdownDoc("> Line one\n> See [guide](docs/guide.md) here.")
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 2
        # col_start should account for "> " prefix
        assert links[0].col_start > 1

    def test_link_inside_nested_list(self):
        """Link inside nested list with hanging indent."""
        md = MarkdownDoc("- Item 1\n  - Sub [link](target.md) here")
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 2

    def test_lazy_continuation_in_blockquote(self):
        """Lazy continuation: text continues without > marker."""
        md = MarkdownDoc("> First line\nSee [link](target.md) lazy continuation")
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 2
        assert links[0].col_start == 4

    def test_construct_after_same_paragraph_code_span(self):
        """Code span containing path-like text followed by a real link."""
        md = MarkdownDoc("Use `src/main.py` then see [docs](guide.md).")
        links = md.links()
        assert len(links) == 1
        assert links[0].href == "guide.md"
        assert links[0].file_line == 1

    def test_frontmatter_offset(self):
        """line_offset composes correctly with token maps."""
        body = "\n# Heading\n\nSee [link](target.md) here.\n"
        md = MarkdownDoc(body, line_offset=3)
        links = md.links()
        assert len(links) == 1
        assert links[0].file_line == 7  # body line 4 + offset 3


# ------------------------------------------------------------------
# Regression suite (from issue #284)
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

    def test_suppression_inside_fence_ignored(self, tmp_path):
        """A directive inside a fenced code block must NOT suppress violations."""
        from skillsaw.suppression import build_suppression_map
        from skillsaw.markdown_doc import MarkdownDoc

        content = (
            "# Guide\n"
            "\n"
            "```markdown\n"
            "<!-- skillsaw-disable content-weak-language -->\n"
            "```\n"
            "\n"
            "Try to handle errors.\n"
        )
        md = MarkdownDoc(content)
        smap = build_suppression_map(content, md=md)
        assert not smap.is_suppressed("content-weak-language", 7)

    def test_indented_code_block_not_scanned_as_prose(self, tmp_path):
        """4-space-indented code must not be scanned as prose."""
        md = MarkdownDoc("Text\n\n    Try to handle errors gracefully.\n\nMore text")
        result = md.stripped_body()
        lines = result.splitlines()
        # The indented code block line should be blanked
        assert "Try to handle" not in lines[2]

    def test_autofix_idempotent_substring(self, tmp_path):
        """Substring corruption fix — splice-based fix must be idempotent."""
        from skillsaw.context import RepositoryContext
        from skillsaw.rules.builtin.content.unlinked_internal_reference import (
            ContentUnlinkedInternalReferenceRule,
        )

        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "setup.md").write_text("# Setup\n")
        (tmp_path / "CLAUDE.md").write_text("Backup docs/setup.md.bak and docs/setup.md too.\n")

        context = RepositoryContext(tmp_path)
        rule = ContentUnlinkedInternalReferenceRule()
        violations = rule.check(context)
        # Should flag docs/setup.md (the real one), not the .bak fragment
        fixable = [v for v in violations if "autofixable" in v.message]
        if fixable:
            fixes = rule.fix(context, violations)
            if fixes:
                fixed = fixes[0].fixed_content
                (tmp_path / "CLAUDE.md").write_text(fixed)
                # Second run must produce identical content
                context2 = RepositoryContext(tmp_path)
                violations2 = rule.check(context2)
                fixable2 = [v for v in violations2 if "autofixable" in v.message]
                if fixable2:
                    fixes2 = rule.fix(context2, violations2)
                    if fixes2:
                        assert fixes2[0].fixed_content == fixed
