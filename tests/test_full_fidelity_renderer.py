import json
import sys

import pytest

from app.full_fidelity_renderer import render_markdown_full_fidelity


def test_renderer_parses_cli_json(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    html = tmp_path / "rendered.html"
    image = tmp_path / "chart.png"
    html.write_text("<h1>ok</h1>", encoding="utf-8")
    image.write_bytes(b"png")
    payload = {
        "schemaVersion": "1.0",
        "ok": True,
        "status": "success",
        "htmlPath": str(html),
        "images": [
            {
                "id": "mdv__chart__aabbccdd__",
                "type": "vega-lite",
                "pngPath": str(image),
                "widthPx": 800,
                "heightPx": 400,
                "widthCm": 15.5,
                "durationMs": 20,
            }
        ],
        "warnings": [],
        "stats": {"totalBlocks": 1, "renderedBlocks": 1, "failedBlocks": 0, "durationMs": 20},
        "renderSummary": {
            "totalBlocks": 1,
            "renderedBlocks": 1,
            "failedBlocks": 0,
            "warningCount": 0,
            "statusText": "所有支持的图表已渲染",
        },
    }
    cli.write_text("print(" + repr(json.dumps(payload)) + ")\n", encoding="utf-8")

    result = render_markdown_full_fidelity(
        markdown="# ok",
        renderer_cli=[sys.executable, str(cli)],
        output_dir=tmp_path,
        timeout_ms=5000,
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.images[0].id == "mdv__chart__aabbccdd__"
    assert result.renderSummary.statusText == "所有支持的图表已渲染"


def test_renderer_passes_page_timeout_before_subprocess_deadline(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    html = tmp_path / "rendered.html"
    payload_path = tmp_path / "payload.json"
    html.write_text("<h1>ok</h1>", encoding="utf-8")
    cli.write_text(
        "\n".join([
            "import json, pathlib, sys",
            "payload = json.load(sys.stdin)",
            f"pathlib.Path({str(payload_path)!r}).write_text(json.dumps(payload), encoding='utf-8')",
            "print(json.dumps({",
            "  'schemaVersion': '1.0',",
            "  'ok': True,",
            "  'status': 'success',",
            f"  'htmlPath': {str(html)!r},",
            "  'images': [],",
            "  'warnings': [],",
            "  'stats': {'totalBlocks': 0, 'renderedBlocks': 0, 'failedBlocks': 0, 'durationMs': 0},",
            "  'renderSummary': {'totalBlocks': 0, 'renderedBlocks': 0, 'failedBlocks': 0, 'warningCount': 0, 'statusText': 'ok'},",
            "}))",
        ]),
        encoding="utf-8",
    )

    render_markdown_full_fidelity(
        markdown="# ok",
        renderer_cli=[sys.executable, str(cli)],
        output_dir=tmp_path,
        timeout_ms=60000,
    )

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["timeoutMs"] == 55000
    assert payload["enabledRenderers"] == [
        "mermaid",
        "katex",
        "excalidraw",
        "drawio",
        "echarts",
        "markmap",
        "graphviz",
        "infographic",
        "plantuml",
        "vega-lite",
        "d2",
        "bpmn",
        "wavedrom",
        "c4plantuml",
    ]
    assert payload["networkPolicy"] == "local-friendly"


def test_renderer_allows_cli_margin_after_page_timeout(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    html = tmp_path / "rendered.html"
    html.write_text("<h1>timeout</h1>", encoding="utf-8")
    cli.write_text(
        "\n".join([
            "import json, pathlib, sys, time",
            "payload = json.load(sys.stdin)",
            "time.sleep((payload['timeoutMs'] / 1000) + 7)",
            "print(json.dumps({",
            "  'schemaVersion': '1.0',",
            "  'ok': False,",
            "  'status': 'timeout',",
            f"  'htmlPath': {str(html)!r},",
            "  'images': [],",
            "  'warnings': [],",
            "  'stats': {'totalBlocks': 1, 'renderedBlocks': 0, 'failedBlocks': 1, 'durationMs': payload['timeoutMs']},",
            "  'renderSummary': {'totalBlocks': 1, 'renderedBlocks': 0, 'failedBlocks': 1, 'warningCount': 0, 'statusText': 'timeout'},",
            "}))",
        ]),
        encoding="utf-8",
    )

    result = render_markdown_full_fidelity(
        markdown="```mermaid\ngraph TD\nA-->B\n```",
        renderer_cli=[sys.executable, str(cli)],
        output_dir=tmp_path,
        timeout_ms=7000,
    )

    assert result.status == "timeout"
    assert result.stats.failedBlocks == 1


def test_renderer_returns_timeout_result_when_cli_exceeds_deadline(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    cli.write_text(
        "\n".join([
            "import time",
            "time.sleep(30)",
        ]),
        encoding="utf-8",
    )

    result = render_markdown_full_fidelity(
        markdown="```infographic\ninfographic list-row-simple-horizontal-arrow\n```",
        renderer_cli=[sys.executable, str(cli)],
        output_dir=tmp_path,
        timeout_ms=1000,
    )

    assert result.status == "timeout"
    assert result.ok is False
    assert result.stats.failedBlocks == 1
    assert result.renderSummary.statusText == "renderer cli timed out"


def test_renderer_timeout_count_excludes_plantuml_postprocess_blocks(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    cli.write_text(
        "\n".join([
            "import time",
            "time.sleep(30)",
        ]),
        encoding="utf-8",
    )

    result = render_markdown_full_fidelity(
        markdown="```plantuml\n@startuml\nAlice -> Bob: hello\n@enduml\n```\n",
        renderer_cli=[sys.executable, str(cli)],
        output_dir=tmp_path,
        timeout_ms=1000,
    )

    assert result.status == "timeout"
    assert result.stats.totalBlocks == 0
    assert result.stats.failedBlocks == 0


def test_renderer_timeout_counts_renderer_plugin_blocks(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    cli.write_text(
        "\n".join([
            "import time",
            "time.sleep(30)",
        ]),
        encoding="utf-8",
    )

    result = render_markdown_full_fidelity(
        markdown="\n\n".join([
            "```vegalite\n{\"data\":{\"values\":[]},\"mark\":\"bar\"}\n```",
            "```d2\na -> b\n```",
            "```bpmn\n<definitions />\n```",
            "```wavedrom\n{ signal: [] }\n```",
            "```c4\n@startuml\n@enduml\n```",
            "![流程](process.bpmn)",
        ]),
        renderer_cli=[sys.executable, str(cli)],
        output_dir=tmp_path,
        timeout_ms=1000,
    )

    assert result.status == "timeout"
    assert result.stats.totalBlocks == 6
    assert result.stats.failedBlocks == 6


def test_renderer_rejects_output_paths_outside_output_dir(tmp_path):
    cli = tmp_path / "fake_renderer.py"
    outside = tmp_path.parent / "outside.html"
    payload = {
        "schemaVersion": "1.0",
        "ok": True,
        "status": "success",
        "htmlPath": str(outside),
        "images": [],
        "warnings": [],
        "stats": {"totalBlocks": 0, "renderedBlocks": 0, "failedBlocks": 0, "durationMs": 0},
        "renderSummary": {
            "totalBlocks": 0,
            "renderedBlocks": 0,
            "failedBlocks": 0,
            "warningCount": 0,
            "statusText": "ok",
        },
    }
    cli.write_text("print(" + repr(json.dumps(payload)) + ")\n", encoding="utf-8")

    with pytest.raises(ValueError):
        render_markdown_full_fidelity(
            markdown="# ok",
            renderer_cli=[sys.executable, str(cli)],
            output_dir=tmp_path,
            timeout_ms=5000,
        )
