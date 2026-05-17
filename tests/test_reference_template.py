import base64
import io
import json

from docx import Document


def _template_base64() -> str:
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("模板前置段落")
    doc.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def test_convert_accepts_reference_docx_template(client):
    resp = client.post("/convert", json={
        "markdown": "# 正文标题\n\n正文内容",
        "style": "standard",
        "referenceDocxBase64": _template_base64(),
    })

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_convert_warns_and_falls_back_for_invalid_reference_docx(client):
    resp = client.post("/convert", json={
        "markdown": "# 正文标题\n\n正文内容",
        "style": "standard",
        "referenceDocxBase64": base64.b64encode(b"not-a-docx").decode(),
    })

    assert resp.status_code == 200
    warnings = json.loads(resp.headers["x-convert-warnings"])
    assert any("reference.docx" in warning and "已回退内置样式" in warning for warning in warnings)
