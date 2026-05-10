import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _node_playwright_available() -> bool:
    return subprocess.run(
        ["node", "-e", "require.resolve('playwright')"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).returncode == 0


@pytest.mark.skipif(not _node_playwright_available(), reason="node playwright is not installed")
def test_renderer_cli_loads_artifact_and_captures_block(tmp_path):
    artifact_dir = tmp_path / "artifact"
    assets_dir = artifact_dir / "assets"
    output_dir = tmp_path / "out"
    assets_dir.mkdir(parents=True)
    output_dir.mkdir()

    (artifact_dir / "server-render.html").write_text(
        """
        <!doctype html>
        <html>
          <body>
            <script>
              const wrapper = document.createElement('div')
              wrapper.className = 'mermaid-wrapper'
              wrapper.style.width = '320px'
              wrapper.style.height = '160px'
              wrapper.style.background = '#ffffff'
              wrapper.innerHTML = '<svg width="320" height="160"><rect width="320" height="160" fill="white"/><text x="20" y="80">Mermaid</text></svg>'
              document.body.appendChild(wrapper)
              window.__MDV_RENDER_RESULT__ = {
                schemaVersion: '1.0',
                ok: true,
                status: 'success',
                html: document.body.innerHTML,
                images: [{
                  id: 'mdv__chart__00000000__',
                  type: 'mermaid',
                  selector: '.mermaid-wrapper',
                  widthPx: 320,
                  heightPx: 160,
                  widthCm: 15.5,
                  durationMs: 1
                }],
                stats: { totalBlocks: 1, renderedBlocks: 1, failedBlocks: 0, durationMs: 1 },
                warnings: []
              }
              window.__MDV_RENDER_DONE__ = true
            </script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    payload = {
        "schemaVersion": "1.0",
        "markdown": "```mermaid\\ngraph TD\\nA-->B\\n```",
        "theme": "light",
        "enabledRenderers": ["mermaid"],
        "networkPolicy": "blocked",
        "outputDir": str(output_dir),
    }

    completed = subprocess.run(
        ["node", str(REPO_ROOT / "renderers" / "mdv-renderer-cli.mjs")],
        input=json.dumps(payload),
        env={**os.environ, "MDV_RENDER_ARTIFACT_DIR": str(artifact_dir)},
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "success"
    assert Path(result["htmlPath"]).exists()
    assert len(result["images"]) == 1
    assert Path(result["images"][0]["pngPath"]).exists()
    assert result["images"][0]["widthPx"] >= 300


@pytest.mark.skipif(not _node_playwright_available(), reason="node playwright is not installed")
def test_renderer_cli_defaults_to_pdf_like_viewport_width(tmp_path):
    artifact_dir = tmp_path / "artifact"
    output_dir = tmp_path / "out"
    artifact_dir.mkdir()
    output_dir.mkdir()

    (artifact_dir / "server-render.html").write_text(
        """
        <!doctype html>
        <html>
          <head>
            <style>
              html, body { margin: 0; padding: 0; }
              .responsive-chart {
                width: 100vw;
                height: 400px;
                background: #ffffff;
              }
            </style>
          </head>
          <body>
            <div class="responsive-chart"></div>
            <script>
              window.__MDV_RENDER_RESULT__ = {
                schemaVersion: '1.0',
                ok: true,
                status: 'success',
                html: document.body.innerHTML,
                images: [{
                  id: 'mdv__chart__00000000__',
                  type: 'echarts',
                  selector: '.responsive-chart',
                  widthPx: 1,
                  heightPx: 1,
                  widthCm: 15.5,
                  durationMs: 1
                }],
                stats: { totalBlocks: 1, renderedBlocks: 1, failedBlocks: 0, durationMs: 1 },
                warnings: []
              }
              window.__MDV_RENDER_DONE__ = true
            </script>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    payload = {
        "schemaVersion": "1.0",
        "markdown": "```echarts\\n{}\\n```",
        "theme": "light",
        "enabledRenderers": ["echarts"],
        "networkPolicy": "blocked",
        "outputDir": str(output_dir),
    }

    completed = subprocess.run(
        ["node", str(REPO_ROOT / "renderers" / "mdv-renderer-cli.mjs")],
        input=json.dumps(payload),
        env={**os.environ, "MDV_RENDER_ARTIFACT_DIR": str(artifact_dir)},
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["images"][0]["widthPx"] == 656
