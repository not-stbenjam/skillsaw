from skillsaw.markdown_doc import MarkdownDoc, MarkdownEdit, splice


def test_inline_link_on_wrapped_paragraph_reports_actual_line():
    doc = MarkdownDoc("First paragraph line\ncontinues with [guide](docs/guide.md).\n")

    link = doc.links[0]

    assert link.file_line == 2
    assert link.destination.file_line == 2
    assert link.destination.col_start == 23
    assert link.destination.col_end == 36


def test_inline_link_in_blockquote_and_lazy_continuation_keeps_source_lines():
    doc = MarkdownDoc("> intro\n> [quoted](docs/quoted.md)\nlazy [plain](docs/plain.md)\n")

    quoted, lazy = doc.links

    assert quoted.file_line == 2
    assert quoted.destination.col_start == 11
    assert lazy.file_line == 3
    assert lazy.destination.col_start == 13


def test_inline_link_in_list_continuation_readds_indent_columns():
    doc = MarkdownDoc("- item\n  continuation [guide](docs/guide.md)\n")

    link = doc.links[0]

    assert link.file_line == 2
    assert link.destination.col_start == 23


def test_reference_style_link_uses_definition_destination_span():
    doc = MarkdownDoc('[guide][g]\n\n[g]: docs/guide.md "Guide"\n')

    link = doc.links[0]

    assert link.href == "docs/guide.md"
    assert link.title == "Guide"
    assert link.file_line == 1
    assert link.destination.file_line == 3
    assert link.destination.col_start == 5
    assert link.destination.col_end == 18


def test_shortcut_reference_style_link_is_resolved():
    doc = MarkdownDoc('[guide]\n\n[guide]: docs/guide.md "Guide"\n')

    link = doc.links[0]

    assert link.href == "docs/guide.md"
    assert link.title == "Guide"
    assert link.file_line == 1
    assert link.destination.file_line == 3
    assert link.destination.col_start == 9
    assert link.destination.col_end == 22


def test_headings_include_setext():
    doc = MarkdownDoc("ATX\n===\n\n## Hash\n")

    headings = doc.headings

    assert [(h.text, h.level, h.file_line, h.style) for h in headings] == [
        ("ATX", 1, 1, "setext"),
        ("Hash", 2, 4, "atx"),
    ]


def test_prose_text_blanks_code_comments_and_indented_blocks_preserving_lines():
    content = (
        "Before docs/ok.md\n"
        "\n"
        "    docs/code.md\n"
        "\n"
        "Inline `docs/code.md` and text.\n"
        "<!-- docs/comment.md -->\n"
        "```\n"
        "docs/fenced.md\n"
        "```\n"
        "After docs/ok.md\n"
    )

    prose = MarkdownDoc(content).prose_text()

    assert prose.count("\n") == content.count("\n")
    assert "docs/ok.md" in prose
    assert "docs/code.md" not in prose
    assert "docs/comment.md" not in prose
    assert "docs/fenced.md" not in prose


def test_text_segments_skip_links_and_code_but_keep_plain_text_spans():
    doc = MarkdownDoc("See [linked](docs/linked.md), `docs/code.md`, and docs/plain.md.\n")

    segment_text = [segment.text for segment in doc.text_segments]

    assert "docs/plain.md" in " ".join(segment_text)
    assert "docs/linked.md" not in " ".join(segment_text)
    assert "docs/code.md" not in " ".join(segment_text)


def test_splice_applies_edits_right_to_left():
    content = "See docs/a.md and docs/b.md.\n"
    fixed = splice(
        content,
        [
            MarkdownEdit(1, 4, 13, "[docs/a.md](docs/a.md)"),
            MarkdownEdit(1, 18, 27, "[docs/b.md](docs/b.md)"),
        ],
    )

    assert fixed == "See [docs/a.md](docs/a.md) and [docs/b.md](docs/b.md).\n"
