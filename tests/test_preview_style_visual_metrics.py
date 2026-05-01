import os
import shutil
import subprocess
import zipfile

import pytest
from docx import Document

from app.generator import generate_docx_from_content
from app.image_injector import ImageData, inject_images


def test_preview_docx_has_visual_contract_metrics(tmp_path, small_png_base64):
    placeholder_id = "mdv__chart__aabbccdd__"
    out_path = tmp_path / "preview-metrics.docx"
    content = (
        "# 标题\n\n"
        "| A | B |\n"
        "|---|---|\n"
        "| 1 | 2 |\n\n"
        f"![]({placeholder_id})\n\n"
        "```bash\nkubectl get pods --all-namespaces\n```"
    )

    generate_docx_from_content(content=content, output_path=str(out_path), style="preview")
    injected = inject_images(
        str(out_path),
        {placeholder_id: ImageData(placeholder_id, small_png_base64, width_cm=15.5)},
        style="preview",
    )

    assert injected == 1

    doc = Document(str(out_path))
    section = doc.sections[0]
    assert round(section.page_width.cm, 1) == 21.0
    assert round(section.page_height.cm, 1) == 29.7
    assert section.left_margin.cm <= 1.3
    assert section.right_margin.cm <= 1.3

    with zipfile.ZipFile(out_path) as zf:
        names = zf.namelist()
        xml = zf.read("word/document.xml").decode("utf-8")

    assert sum(1 for name in names if name.startswith("word/media/") and name.endswith(".png")) == 1
    assert 'w:fill="F6F8FA"' in xml
    assert "w:tcMar" in xml
    assert 'w:w="11906"' in xml
    assert 'w:h="16838"' in xml


def test_preview_docx_converts_to_a4_pdf_when_tools_available(tmp_path):
    soffice = shutil.which("soffice") or (
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if os.path.exists("/Applications/LibreOffice.app/Contents/MacOS/soffice")
        else None
    )
    pdfinfo = shutil.which("pdfinfo")
    if not soffice or not pdfinfo:
        pytest.skip("soffice/pdfinfo not available")

    out_path = tmp_path / "preview-pdf.docx"
    generate_docx_from_content(
        content="# 标题\n\n## 小节\n\n正文\n\n| A | B |\n|---|---|\n| 1 | 2 |",
        output_path=str(out_path),
        style="preview",
    )

    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(out_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    pdf_path = tmp_path / "preview-pdf.pdf"
    result = subprocess.run(
        [pdfinfo, str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert "Pages:" in result.stdout
    assert "A4" in result.stdout or "595." in result.stdout
