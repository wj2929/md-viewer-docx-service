from docx import Document

from app.font_embedder import embed_fonts_if_requested


def test_embed_fonts_without_available_font_keeps_docx_readable(tmp_path):
    doc_path = tmp_path / "sample.docx"
    doc = Document()
    doc.add_paragraph("字体嵌入降级测试")
    doc.save(doc_path)

    warnings = embed_fonts_if_requested(str(doc_path), True, font_paths=["/not/found/font.ttf"])

    reopened = Document(doc_path)
    assert reopened.paragraphs[0].text == "字体嵌入降级测试"
    assert warnings
    assert "未找到可嵌入字体" in warnings[0]


def test_embed_fonts_disabled_returns_no_warnings(tmp_path):
    doc_path = tmp_path / "sample.docx"
    doc = Document()
    doc.add_paragraph("no-op")
    doc.save(doc_path)

    assert embed_fonts_if_requested(str(doc_path), False) == []
