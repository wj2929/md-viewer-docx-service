import base64
import io

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
