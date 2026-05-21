import io
import threading
import zipfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


def test_convert_source_markdown_returns_docx(client, monkeypatch, tmp_path):
    from app import main

    class FakeSummary:
        totalBlocks = 1
        renderedBlocks = 1
        failedBlocks = 0
        warningCount = 0
        statusText = "所有支持的图表已渲染"

        def model_dump(self):
            return {
                "totalBlocks": self.totalBlocks,
                "renderedBlocks": self.renderedBlocks,
                "failedBlocks": self.failedBlocks,
                "warningCount": self.warningCount,
                "statusText": self.statusText,
            }

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = []
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n正文",
        "style": "preview",
    })

    assert resp.status_code == 200
    assert resp.headers["x-service-mode"] == "fullFidelity"
    assert resp.headers["x-render-status"] == "success"
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_convert_source_null_footer_text_disables_generated_branding(client, monkeypatch):
    from app import main

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = []
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n正文",
        "style": "preview",
        "footerText": None,
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    assert "由 MD Viewer 生成" not in document_xml


def test_convert_source_injects_full_fidelity_renderer_images(client, monkeypatch, tmp_path, small_png_base64):
    from app import main

    png_path = tmp_path / "chart.png"
    png_path.write_bytes(__import__("base64").b64decode(small_png_base64))

    class FakeSummary:
        totalBlocks = 1
        renderedBlocks = 1
        failedBlocks = 0
        warningCount = 0
        statusText = "success"

        def model_dump(self):
            return {
                "totalBlocks": self.totalBlocks,
                "renderedBlocks": self.renderedBlocks,
                "failedBlocks": self.failedBlocks,
                "warningCount": self.warningCount,
                "statusText": self.statusText,
            }

    class FakeImage:
        id = "mdv__chart__aabbccdd__"
        type = "mermaid"
        pngPath = str(png_path)
        widthPx = 100
        heightPx = 100
        widthCm = 12.0
        durationMs = 1

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = [FakeImage()]
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n```mermaid\ngraph TD\nA --> B\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert len(media_entries) == 1
    assert "mdv__chart__aabbccdd__" not in document_xml
    assert "graph TD" not in document_xml


def test_convert_source_injects_full_fidelity_katex_images(client, monkeypatch, tmp_path, small_png_base64):
    from app import main

    png_path = tmp_path / "formula.png"
    png_path.write_bytes(__import__("base64").b64decode(small_png_base64))

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeImage:
        id = "mdv__chart__00000000__"
        type = "katex"
        pngPath = str(png_path)
        widthCm = 12.0

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = [FakeImage()]
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 公式\n\n$$\nx = y + 1\n$$",
        "style": "preview",
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert len(media_entries) == 1
    assert "x = y + 1" not in document_xml
    assert "mdv__chart__00000000__" not in document_xml


def test_full_fidelity_katex_width_follows_rendered_pixel_width(tmp_path, small_png_base64):
    import base64
    from app.main import _full_fidelity_images_to_base64

    png_path = tmp_path / "formula.png"
    png_path.write_bytes(base64.b64decode(small_png_base64))

    class FakeImage:
        id = "mdv__chart__00000000__"
        type = "katex"
        pngPath = str(png_path)
        widthPx = 240
        heightPx = 80
        widthCm = 12.0

    result = _full_fidelity_images_to_base64([FakeImage()])

    assert len(result) == 1
    assert 4.0 <= result[0]["widthCm"] <= 5.5


def test_full_fidelity_chart_width_follows_rendered_pixel_width(tmp_path, small_png_base64):
    import base64
    from app.main import _full_fidelity_images_to_base64

    png_path = tmp_path / "chart.png"
    png_path.write_bytes(base64.b64decode(small_png_base64))

    class NarrowMermaid:
        id = "mdv__chart__00000000__"
        type = "mermaid"
        pngPath = str(png_path)
        widthPx = 340
        heightPx = 480
        widthCm = 15.5

    class WideEcharts:
        id = "mdv__chart__00000001__"
        type = "echarts"
        pngPath = str(png_path)
        widthPx = 1408
        heightPx = 377
        widthCm = 15.5

    result = _full_fidelity_images_to_base64([NarrowMermaid(), WideEcharts()])

    assert 5.5 <= result[0]["widthCm"] <= 7.0
    assert result[1]["widthCm"] == 15.5


def test_full_fidelity_chart_width_prefers_renderer_physical_width(tmp_path, small_png_base64):
    import base64
    from app.main import _full_fidelity_images_to_base64

    png_path = tmp_path / "chart.png"
    png_path.write_bytes(base64.b64decode(small_png_base64))

    class RendererSizedChart:
        id = "mdv__chart__00000000__"
        type = "graphviz"
        pngPath = str(png_path)
        widthPx = 556
        heightPx = 419
        widthCm = 13.1

    result = _full_fidelity_images_to_base64([RendererSizedChart()])

    assert result[0]["widthCm"] == 13.1


def test_full_fidelity_images_to_base64_preserves_block_id(tmp_path, small_png_base64):
    import base64
    from app.main import _full_fidelity_images_to_base64

    png_path = tmp_path / "chart.png"
    png_path.write_bytes(base64.b64decode(small_png_base64))

    class RendererImage:
        id = "mdv__chart__00000000__"
        type = "mermaid"
        pngPath = str(png_path)
        widthPx = 556
        heightPx = 419
        widthCm = 13.1
        blockId = "mdv-mermaid-abcdef12"

    result = _full_fidelity_images_to_base64([RendererImage()])

    assert result[0]["blockId"] == "mdv-mermaid-abcdef12"


def test_convert_source_injects_full_fidelity_excalidraw_file_images(client, monkeypatch, tmp_path, small_png_base64):
    from app import main

    png_path = tmp_path / "excalidraw.png"
    png_path.write_bytes(__import__("base64").b64decode(small_png_base64))

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeImage:
        id = "mdv__chart__00000000__"
        type = "excalidraw"
        pngPath = str(png_path)
        widthCm = 15.5

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = [FakeImage()]
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "bundle",
        "entryPath": "docs/readme.md",
        "resources": [
            {
                "path": "docs/readme.md",
                "kind": "text",
                "content": "# 图\n\n![架构](../diagrams/a.excalidraw)",
                "mediaType": "text/markdown",
                "size": 38,
            },
            {
                "path": "diagrams/a.excalidraw",
                "kind": "text",
                "content": "{\"type\":\"excalidraw\",\"version\":2,\"source\":\"\",\"elements\":[]}",
                "mediaType": "application/json",
                "size": 60,
            },
        ],
        "style": "preview",
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert len(media_entries) == 1
    assert ".excalidraw" not in document_xml
    assert "mdv__chart__00000000__" not in document_xml


def test_convert_source_injects_full_fidelity_drawio_images(client, monkeypatch, tmp_path, small_png_base64):
    from app import main

    png_path = tmp_path / "drawio.png"
    png_path.write_bytes(__import__("base64").b64decode(small_png_base64))

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeImage:
        id = "mdv__chart__00000000__"
        type = "drawio"
        pngPath = str(png_path)
        widthCm = 15.5

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = [FakeImage()]
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# DrawIO\n\n```drawio\n<mxGraphModel><root><mxCell id=\"0\"/></root></mxGraphModel>\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert len(media_entries) == 1
    assert "mxGraphModel" not in document_xml
    assert "mdv__chart__00000000__" not in document_xml


def test_convert_source_injects_full_fidelity_echarts_images(client, monkeypatch, tmp_path, small_png_base64):
    from app import main

    png_path = tmp_path / "echarts.png"
    png_path.write_bytes(__import__("base64").b64decode(small_png_base64))

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeImage:
        id = "mdv__chart__00000000__"
        type = "echarts"
        pngPath = str(png_path)
        widthCm = 15.5

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = [FakeImage()]
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# ECharts\n\n```echarts\n{\"series\":[{\"type\":\"bar\",\"data\":[1,2]}]}\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert len(media_entries) == 1
    assert "series" not in document_xml
    assert "mdv__chart__00000000__" not in document_xml


def test_convert_source_injects_full_fidelity_markmap_images(client, monkeypatch, tmp_path, small_png_base64):
    from app import main

    png_path = tmp_path / "markmap.png"
    png_path.write_bytes(__import__("base64").b64decode(small_png_base64))

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeImage:
        id = "mdv__chart__00000000__"
        type = "markmap"
        pngPath = str(png_path)
        widthCm = 15.5

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = [FakeImage()]
        stats = {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# Markmap\n\n```markmap\n# Root\n## Branch\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert len(media_entries) == 1
    assert "Branch" not in document_xml
    assert "mdv__chart__00000000__" not in document_xml


def test_full_fidelity_replacement_uses_source_index_for_partial_echarts_results():
    from app.main import _replace_full_fidelity_chart_blocks

    markdown = """# 图表

```echarts
invalid json
```

```echarts
{"series":[{"type":"bar","data":[1,2]}]}
```
"""

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "echarts",
        "sourceIndex": 1,
    }])

    assert "invalid json" in result
    assert "mdv__chart__00000001__" in result
    assert '"series"' not in result


def test_full_fidelity_replacement_prefers_block_id_over_source_index():
    from app.main import _collect_full_fidelity_source_locators, _replace_full_fidelity_chart_blocks

    markdown = """# 图表

```echarts
{"series":[{"type":"bar","data":[1]}]}
```

```echarts
{"series":[{"type":"line","data":[2]}]}
```
"""
    locators = _collect_full_fidelity_source_locators(markdown)
    second = [locator for locator in locators if locator["type"] == "echarts"][1]

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "echarts",
        "blockId": second["blockId"],
        "sourceIndex": 0,
    }])

    assert "mdv__chart__00000001__" in result
    assert '"line"' not in result
    assert '"bar"' in result


def test_full_fidelity_hash_matches_renderer_utf16_algorithm():
    from app.main import _stable_hash

    assert _stable_hash("😀") == "cb31c4b8"
    assert _stable_hash("中文😀") == "914dfa10"


def test_full_fidelity_replacement_uses_source_index_for_graphviz_results():
    from app.main import _replace_full_fidelity_chart_blocks

    markdown = """# 图表

```graphviz
invalid
```

```graphviz
digraph G { A -> B }
```
"""

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "graphviz",
        "sourceIndex": 1,
    }])

    assert "invalid" in result
    assert "mdv__chart__00000001__" in result
    assert "digraph G" not in result


def test_full_fidelity_replacement_uses_source_index_for_infographic_results():
    from app.main import _replace_full_fidelity_chart_blocks

    markdown = """# 图表

```infographic
infographic list-column-done-list
data
  title A
```

```infographic
infographic sequence-timeline-simple
data
  title B
```
"""

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "infographic",
        "sourceIndex": 1,
    }])

    assert "mdv__chart__00000001__" in result
    assert "sequence-timeline-simple" not in result
    assert "list-column-done-list" in result


def test_full_fidelity_replacement_uses_source_index_for_plantuml_results():
    from app.main import _replace_full_fidelity_chart_blocks

    markdown = """# 图表

```plantuml
@startuml
Alice -> Bob: first
@enduml
```

```puml
@startuml
Alice -> Bob: second
@enduml
```
"""

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "plantuml",
        "sourceIndex": 1,
    }])

    assert "mdv__chart__00000001__" in result
    assert "second" not in result
    assert "first" in result


@pytest.mark.parametrize(
    ("image_type", "markdown", "removed", "kept"),
    [
        (
            "vega-lite",
            """# 图表

```vegalite
{"data":{"values":[{"x":1}]},"mark":"bar"}
```

```vega-lite
{"data":{"values":[{"x":2}]},"mark":"line"}
```
""",
            '"line"',
            '"bar"',
        ),
        (
            "d2",
            """# 图表

```d2
a -> b
```

```d2
c -> d
```
""",
            "c -> d",
            "a -> b",
        ),
        (
            "bpmn",
            """# 图表

```bpmn
<definitions id="first" />
```

```bpmn
<definitions id="second" />
```
""",
            "second",
            "first",
        ),
        (
            "wavedrom",
            """# 图表

```wavedrom
{ signal: [{ name: 'a', wave: '01' }] }
```

```wavedrom
{ signal: [{ name: 'b', wave: '10' }] }
```
""",
            "name: 'b'",
            "name: 'a'",
        ),
        (
            "c4plantuml",
            """# 图表

```c4
@startuml
Person(a, "A")
@enduml
```

```c4plantuml
@startuml
Person(b, "B")
@enduml
```
""",
            'Person(b, "B")',
            'Person(a, "A")',
        ),
    ],
)
def test_full_fidelity_replacement_uses_source_index_for_renderer_plugins(image_type, markdown, removed, kept):
    from app.main import _replace_full_fidelity_chart_blocks

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": image_type,
        "sourceIndex": 1,
    }])

    assert "mdv__chart__00000001__" in result
    assert removed not in result
    assert kept in result


def test_full_fidelity_replacement_uses_source_index_for_bpmn_file_refs():
    from app.main import _replace_full_fidelity_chart_blocks

    markdown = "# 图表\n\n![第一个](first.bpmn)\n\n![第二个](second.bpmn)\n"

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "bpmn",
        "sourceIndex": 1,
    }])

    assert "mdv__chart__00000001__" in result
    assert "second.bpmn" not in result
    assert "first.bpmn" in result


def test_full_fidelity_locators_include_file_refs_in_document_order():
    from app.main import _collect_full_fidelity_source_locators

    markdown = "\n\n".join([
        "![流程](./process.bpmn?raw=1#v)",
        "```bpmn\n<definitions id=\"inline\" />\n```",
        "![画布](./diagram.excalidraw)",
    ])

    locators = _collect_full_fidelity_source_locators(markdown)

    assert [(item["type"], item["sourceKind"], item["sourceIndex"]) for item in locators] == [
        ("bpmn", "imageRef", 0),
        ("bpmn", "fence", 1),
        ("excalidraw", "imageRef", 0),
    ]
    assert locators[0]["resolvedPath"] == "./process.bpmn"
    assert locators[2]["resolvedPath"] == "./diagram.excalidraw"


def test_full_fidelity_replacement_prefers_block_id_for_bpmn_file_refs():
    from app.main import _collect_full_fidelity_source_locators, _replace_full_fidelity_chart_blocks

    markdown = "# 图表\n\n![第一个](first.bpmn)\n\n![第二个](second.bpmn)\n"
    locators = _collect_full_fidelity_source_locators(markdown)
    second = [locator for locator in locators if locator["type"] == "bpmn"][1]

    result = _replace_full_fidelity_chart_blocks(markdown, [{
        "id": "mdv__chart__00000001__",
        "type": "bpmn",
        "blockId": second["blockId"],
        "sourceIndex": 0,
    }])

    assert "mdv__chart__00000001__" in result
    assert "second.bpmn" not in result
    assert "first.bpmn" in result


def test_convert_source_accepts_markdown_url(client, monkeypatch):
    from app import main

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.end_headers()
            self.wfile.write("# URL 标题\n\n正文".encode("utf-8"))

        def log_message(self, format, *args):
            return

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = []
        stats = {"totalBlocks": 0, "renderedBlocks": 0, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    captured = {}

    def fake_render(**kwargs):
        captured["markdown"] = kwargs["markdown"]
        return FakeResult()

    monkeypatch.setenv("MDV_SOURCE_URL_POLICY", "local-friendly")
    monkeypatch.setattr(main, "render_markdown_full_fidelity", fake_render)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        resp = client.post("/convert-source", json={
            "sourceType": "url",
            "url": f"http://127.0.0.1:{server.server_port}/doc.md",
            "style": "preview",
        })
    finally:
        server.shutdown()

    assert resp.status_code == 200
    assert captured["markdown"] == "# URL 标题\n\n正文"


def test_convert_source_passes_bundle_resources_to_renderer(client, monkeypatch):
    from app import main

    class FakeSummary:
        failedBlocks = 0

        def model_dump(self):
            return {"failedBlocks": 0}

    class FakeResult:
        ok = True
        status = "success"
        warnings = []
        images = []
        stats = {"totalBlocks": 0, "renderedBlocks": 0, "failedBlocks": 0, "durationMs": 10}
        renderSummary = FakeSummary()

    captured = {}

    def fake_render(**kwargs):
        captured.update(kwargs)
        return FakeResult()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", fake_render)

    resp = client.post("/convert-source", json={
        "sourceType": "bundle",
        "entryPath": "docs/readme.md",
        "resources": [
            {
                "path": "docs/readme.md",
                "kind": "text",
                "content": "# Bundle\n\n![图](../diagrams/a.excalidraw)",
                "mediaType": "text/markdown",
                "size": 44,
            },
            {
                "path": "diagrams/a.excalidraw",
                "kind": "text",
                "content": "{\"type\":\"excalidraw\",\"version\":2,\"source\":\"\",\"elements\":[]}",
                "mediaType": "application/json",
                "size": 60,
            },
        ],
        "style": "preview",
    })

    assert resp.status_code == 200
    assert captured["markdown"] == "# Bundle\n\n![图](../diagrams/a.excalidraw)"
    assert captured["markdown_file_path"] == "docs/readme.md"
    assert captured["resources"][1]["path"] == "diagrams/a.excalidraw"


def test_convert_source_fail_mode_returns_502(client, monkeypatch):
    from app import main

    class FakeSummary:
        failedBlocks = 1

        def model_dump(self):
            return {"failedBlocks": 1}

    class FakeResult:
        ok = False
        status = "partial"
        warnings = []
        images = []
        stats = {"totalBlocks": 1, "renderedBlocks": 0, "failedBlocks": 1, "durationMs": 10}
        renderSummary = FakeSummary()

    monkeypatch.setattr(main, "render_markdown_full_fidelity", lambda **kwargs: FakeResult())

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n```mermaid\ngraph TD\nA --> B\n```",
        "fallbackMode": "fail",
    })

    assert resp.status_code == 502
    assert resp.json()["detail"]["code"] == "RENDER_FAILED"
