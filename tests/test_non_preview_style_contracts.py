import zipfile

from docx import Document
from lxml import etree

from app.generator import generate_docx_from_content


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _xml_tree(path):
    with zipfile.ZipFile(path) as zf:
        return etree.parse(zf.open("word/document.xml"))


def _fills(path):
    return _xml_tree(path).xpath("//w:shd/@w:fill", namespaces=NS)


def _table_margins(path):
    return _xml_tree(path).xpath("//w:tcMar", namespaces=NS)


def _left_borders(path):
    return _xml_tree(path).xpath("//w:pBdr/w:left", namespaces=NS)


def _paragraph_by_text(path, text):
    matches = _xml_tree(path).xpath(
        "//w:p[.//w:t[text()=$text]]",
        namespaces=NS,
        text=text,
    )
    assert matches, f"paragraph not found: {text}"
    return matches[0]


def test_non_preview_styles_use_a4_page_size(tmp_path):
    for style in ("standard", "official", "internal", "report"):
        out_path = tmp_path / f"{style}-a4.docx"
        generate_docx_from_content(
            content="# 标题\n\n正文",
            output_path=str(out_path),
            style=style,
        )
        section = Document(out_path).sections[0]
        assert round(section.page_width.cm, 1) == 21.0
        assert round(section.page_height.cm, 1) == 29.7


def test_non_preview_headings_disable_word_keep_constraints(tmp_path):
    for style in ("standard", "official", "internal", "report"):
        out_path = tmp_path / f"{style}-heading-flow.docx"
        generate_docx_from_content(
            content="# 标题\n\n> 摘要说明\n\n## 1. 图表\n\n### 1.1 流程图\n\n![](mdv__chart__deadbeef__)",
            output_path=str(out_path),
            style=style,
        )

        for heading_text in ("1. 图表", "1.1 流程图"):
            para = _paragraph_by_text(out_path, heading_text)
            keep_next = para.xpath("./w:pPr/w:keepNext/@w:val", namespaces=NS)
            keep_lines = para.xpath("./w:pPr/w:keepLines/@w:val", namespaces=NS)
            assert keep_next == ["0"]
            assert keep_lines == ["0"]


def test_document_body_first_line_indent_matches_style_contract(tmp_path):
    expected_indent_pt = {
        "preview": None,
        "standard": None,
        "official": 32.0,
        "internal": 30.0,
        "report": 24.0,
    }
    for style, expected_pt in expected_indent_pt.items():
        out_path = tmp_path / f"{style}-body-indent.docx"
        generate_docx_from_content(
            content="# 标题\n\n这是一段普通正文，用于检查不同 DOCX 格式的首行缩进契约。",
            output_path=str(out_path),
            style=style,
        )

        para = next(p for p in Document(out_path).paragraphs if p.text.startswith("这是一段普通正文"))
        if expected_pt is None:
            assert para.paragraph_format.first_line_indent is None
        else:
            assert round(para.paragraph_format.first_line_indent.pt, 2) == expected_pt


def test_non_preview_image_layout_caps_page_height():
    from app.main import _image_layout_for_style

    for style in ("standard", "official", "internal", "report"):
        layout = _image_layout_for_style(style)
        assert layout is not None
        assert layout.max_height_cm <= 15.0


def test_standard_table_has_header_fill_and_cell_margins(tmp_path):
    out_path = tmp_path / "standard-table.docx"
    generate_docx_from_content(
        content="# 标题\n\n| A | B |\n|---|---|\n| 1 | 2 |",
        output_path=str(out_path),
        style="standard",
    )

    assert "F6F8FA" in _fills(out_path)
    assert _table_margins(out_path)

    doc = Document(out_path)
    header_run = next(run for run in doc.tables[0].cell(0, 0).paragraphs[0].runs if run.text)
    body_run = next(run for run in doc.tables[0].cell(1, 0).paragraphs[0].runs if run.text)
    assert header_run.font.size.pt == 9.5
    assert body_run.font.size.pt == 9.5


def test_official_table_does_not_use_web_header_fill(tmp_path):
    out_path = tmp_path / "official-table.docx"
    generate_docx_from_content(
        content="# 标题\n\n| A | B |\n|---|---|\n| 1 | 2 |",
        output_path=str(out_path),
        style="official",
    )

    assert "F6F8FA" not in _fills(out_path)
    assert _table_margins(out_path)


def test_official_note_prefix_only_for_explicit_note(tmp_path):
    out_path = tmp_path / "official-note.docx"
    generate_docx_from_content(
        content="# 标题\n\n> **注意：** 这是正式公文里的说明。",
        output_path=str(out_path),
        style="official",
    )

    doc = Document(out_path)
    assert any(p.text.startswith("注：") for p in doc.paragraphs)
    assert not _left_borders(out_path)


def test_official_normal_quote_does_not_become_note(tmp_path):
    out_path = tmp_path / "official-quote.docx"
    generate_docx_from_content(
        content="# 标题\n\n> 引用一段政策原文。",
        output_path=str(out_path),
        style="official",
    )

    doc = Document(out_path)
    assert not any(p.text.startswith("注：") for p in doc.paragraphs)
    assert any("引用一段政策原文" in p.text for p in doc.paragraphs)


def test_official_quote_uses_first_line_indent_not_left_indent(tmp_path):
    out_path = tmp_path / "official-quote-indent.docx"
    generate_docx_from_content(
        content="# 标题\n\n> 来源：这是一段比较长的说明文字，用来模拟导出后可能换行的家长会来源信息。",
        output_path=str(out_path),
        style="official",
    )

    para = next(p for p in Document(out_path).paragraphs if p.text.startswith("来源："))
    assert para.paragraph_format.left_indent is None
    assert round(para.paragraph_format.first_line_indent.pt, 2) == 32.0


def test_official_quote_lead_in_before_list_uses_first_line_indent(tmp_path):
    out_path = tmp_path / "official-quote-list-lead-in-indent.docx"
    generate_docx_from_content(
        content="# 标题\n\n> **结论**：如需按分部/频道分析连麦使用情况，只能通过以下方式：\n> 1. 第一种方式\n> 2. 第二种方式",
        output_path=str(out_path),
        style="official",
    )

    para = next(p for p in Document(out_path).paragraphs if p.text.startswith("结论："))
    assert para.paragraph_format.left_indent is None
    assert round(para.paragraph_format.first_line_indent.pt, 2) == 32.0


def test_official_quote_list_items_use_hanging_indent(tmp_path):
    out_path = tmp_path / "official-quote-list-indent.docx"
    generate_docx_from_content(
        content="# 标题\n\n> **说明**：\n> - 第一项说明\n> - 第二项说明",
        output_path=str(out_path),
        style="official",
    )

    doc = Document(out_path)
    first_item = next(p for p in doc.paragraphs if "第一项说明" in p.text)
    assert not first_item.text.strip().startswith("-")
    assert first_item.text.strip().startswith("•\t")
    assert round(first_item.paragraph_format.left_indent.cm, 2) == 1.2
    assert round(first_item.paragraph_format.first_line_indent.cm, 2) == -0.5
    assert [round(tab.position.cm, 2) for tab in first_item.paragraph_format.tab_stops] == [1.2]


def test_official_quote_ordered_list_items_use_hanging_indent(tmp_path):
    out_path = tmp_path / "official-quote-ordered-list-indent.docx"
    generate_docx_from_content(
        content="# 标题\n\n> **建议**：\n> 1. 第一项建议\n> 2. 第二项建议",
        output_path=str(out_path),
        style="official",
    )

    doc = Document(out_path)
    first_item = next(p for p in doc.paragraphs if "第一项建议" in p.text)
    second_item = next(p for p in doc.paragraphs if "第二项建议" in p.text)
    assert first_item.text.strip().startswith("1.\t")
    assert second_item.text.strip().startswith("2.\t")
    assert round(first_item.paragraph_format.left_indent.cm, 2) == 1.2
    assert round(first_item.paragraph_format.first_line_indent.cm, 2) == -0.5
    assert [round(tab.position.cm, 2) for tab in first_item.paragraph_format.tab_stops] == [1.2]


def test_official_gfm_note_becomes_note_prefix(tmp_path):
    out_path = tmp_path / "official-gfm-note.docx"
    generate_docx_from_content(
        content="# 标题\n\n> [!NOTE]\n> 这是提示。",
        output_path=str(out_path),
        style="official",
    )

    doc = Document(out_path)
    assert any(p.text.startswith("注：") and "这是提示" in p.text for p in doc.paragraphs)


def test_report_note_preserves_inline_markdown(tmp_path):
    out_path = tmp_path / "report-note-inline.docx"
    generate_docx_from_content(
        content="# 标题\n\n> **注意：** 使用 `kubectl` 检查。",
        output_path=str(out_path),
        style="report",
    )

    doc = Document(out_path)
    assert doc.tables
    assert "kubectl" in doc.tables[0].cell(0, 0).text


def test_official_code_block_uses_9pt_single_spacing(tmp_path):
    out_path = tmp_path / "official-code.docx"
    generate_docx_from_content(
        content="# 标题\n\n```bash\nkubectl get pvc\n```",
        output_path=str(out_path),
        style="official",
    )

    doc = Document(out_path)
    para = next(p for p in doc.paragraphs if "kubectl get pvc" in p.text)
    run = next(r for r in para.runs if r.text)
    assert run.font.size.pt == 9.0
    assert para.paragraph_format.line_spacing == 1.0
