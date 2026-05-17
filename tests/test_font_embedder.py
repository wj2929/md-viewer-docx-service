import zipfile

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


def test_embed_fonts_uses_env_font_paths_by_default(tmp_path, monkeypatch):
    font_path = tmp_path / "CustomCjk.ttf"
    font_path.write_bytes(b"fake-font-bytes")
    monkeypatch.setenv("MD_VIEWER_DOCX_FONT_PATHS", str(font_path))

    doc_path = tmp_path / "sample.docx"
    doc = Document()
    doc.add_paragraph("env font")
    doc.save(doc_path)

    warnings = embed_fonts_if_requested(str(doc_path), True)

    assert warnings == []
    import zipfile
    with zipfile.ZipFile(doc_path) as zf:
        assert "word/fonts/CustomCjk.ttf" in zf.namelist()


def test_embed_fonts_writes_all_available_font_files(tmp_path):
    first_font = tmp_path / "FirstCjk.ttf"
    second_font = tmp_path / "SecondCjk.otf"
    first_font.write_bytes(b"first-font-bytes")
    second_font.write_bytes(b"second-font-bytes")

    doc_path = tmp_path / "multi-font.docx"
    doc = Document()
    doc.add_paragraph("multiple fonts")
    doc.save(doc_path)

    warnings = embed_fonts_if_requested(
        str(doc_path),
        True,
        font_paths=[str(first_font), str(second_font)],
    )

    assert warnings == []
    with zipfile.ZipFile(doc_path) as zf:
        names = zf.namelist()
    assert "word/fonts/FirstCjk.ttf" in names
    assert "word/fonts/SecondCjk.otf" in names
