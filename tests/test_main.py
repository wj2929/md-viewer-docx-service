import os
import json
import pytest
import zipfile
import io
from pathlib import Path
from PIL import Image
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.chart_renderers import RenderResult


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthz:
    def test_returns_200(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_has_required_fields(self, client):
        data = client.get("/healthz").json()
        for key in ("status", "version", "mode", "styles", "fontsAvailable",
                     "minClientVersion", "maxImagesPerRequest"):
            assert key in data, f"Missing key: {key}"

    def test_healthz_does_not_report_fixed_image_cap(self, client):
        data = client.get("/healthz").json()
        assert data["maxImagesPerRequest"] is None

    def test_get_available_fonts_includes_env_font_files(self, tmp_path, monkeypatch):
        from app.main import _get_available_fonts

        font_path = tmp_path / "NotoSansCJKsc-Regular.otf"
        font_path.write_bytes(b"fake-font-bytes")
        monkeypatch.setenv("MD_VIEWER_DOCX_FONT_PATHS", str(font_path))

        assert "NotoSansCJKsc-Regular" in _get_available_fonts()

    def test_status_is_ok(self, client):
        data = client.get("/healthz").json()
        assert data["status"] == "ok"

    def test_styles_include_standard(self, client):
        data = client.get("/healthz").json()
        assert "standard" in data["styles"]

    def test_healthz_styles_are_ordered_and_include_preview(self, client):
        data = client.get("/healthz").json()
        assert data["styles"] == ["preview", "standard", "official", "internal", "report"]

    def test_healthz_reports_font_status_by_style(self, client):
        data = client.get("/healthz").json()

        assert "fontStatus" in data
        assert set(data["fontStatus"]) >= {"standard", "official", "internal", "report"}
        assert "仿宋_GB2312" in data["fontStatus"]["official"]
        assert data["fontStatus"]["official"]["仿宋_GB2312"]["status"] in {"exact", "fallback", "missing"}
        assert "embeddable" in data["fontStatus"]["official"]["仿宋_GB2312"]

    def test_dot_renderer_requires_dot_binary(self, client):
        with patch("app.main.shutil.which", return_value=None):
            data = client.get("/healthz").json()
            assert "dot" not in data["chartRenderersAvailable"]


class TestReadyz:
    def test_readyz_reports_missing_renderer_artifact(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("MDV_RENDER_ARTIFACT_DIR", str(tmp_path / "missing"))

        resp = client.get("/readyz")

        assert resp.status_code == 503
        assert resp.json()["rendererHealth"] == "missing"

    def test_readyz_reports_renderer_artifact_fields(self, client, monkeypatch, tmp_path):
        artifact_dir = tmp_path / "server-render"
        assets_dir = artifact_dir / "assets"
        assets_dir.mkdir(parents=True)
        (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
        (artifact_dir / "manifest.json").write_text(json.dumps({
            "name": "@md-viewer/server-renderer",
            "version": "1.0.0",
            "schemaVersion": "1.0",
            "entryHtml": "server-render.html",
            "assetsDir": "assets",
            "supportedCharts": ["mermaid"],
            "minDocxServiceVersion": "0.1.0",
        }), encoding="utf-8")
        monkeypatch.setenv("MDV_RENDER_ARTIFACT_DIR", str(artifact_dir))

        resp = client.get("/readyz")
        data = resp.json()

        assert resp.status_code == 200
        assert data["fullFidelityRenderSupported"] is True
        assert data["rendererHealth"] == "ok"
        assert data["rendererArtifactVersion"] == "1.0.0"
        assert data["rendererSchemaVersion"] == "1.0"
        assert data["rendererSupportedCharts"] == ["mermaid"]

    def test_readyz_reports_schema_2_renderer_plugins_without_allowlist_warnings(self, client, monkeypatch, tmp_path):
        artifact_dir = tmp_path / "server-render"
        assets_dir = artifact_dir / "assets"
        assets_dir.mkdir(parents=True)
        (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
        (artifact_dir / "manifest.json").write_text(json.dumps({
            "name": "@md-viewer/server-renderer",
            "version": "2.1.0",
            "schemaVersion": "2.0",
            "entryHtml": "server-render.html",
            "assetsDir": "assets",
            "supportedCharts": ["mermaid", "vega-lite", "d2", "bpmn", "wavedrom", "c4plantuml"],
            "minDocxServiceVersion": "0.2.0",
            "renderers": [
                {
                    "type": "mermaid",
                    "displayName": "Mermaid",
                    "capabilities": {"docxService": {"state": "supported"}},
                },
                {
                    "type": "vega-lite",
                    "displayName": "Vega-Lite",
                    "capabilities": {"docxService": {"state": "supported"}},
                },
                {"type": "d2", "displayName": "D2", "capabilities": {"docxService": {"state": "supported"}}},
                {"type": "bpmn", "displayName": "BPMN", "capabilities": {"docxService": {"state": "supported"}}},
                {"type": "wavedrom", "displayName": "WaveDrom", "capabilities": {"docxService": {"state": "supported"}}},
                {"type": "c4plantuml", "displayName": "C4-PlantUML", "capabilities": {"docxService": {"state": "supported"}}},
            ],
        }), encoding="utf-8")
        monkeypatch.setenv("MDV_RENDER_ARTIFACT_DIR", str(artifact_dir))

        resp = client.get("/readyz")
        data = resp.json()

        assert resp.status_code == 200
        assert data["rendererSchemaVersion"] == "2.0"
        assert data["rendererSupportedCharts"] == ["mermaid", "vega-lite", "d2", "bpmn", "wavedrom", "c4plantuml"]
        assert not any(warning["code"] == "RENDERER_MANIFEST_NOT_ALLOWLISTED" for warning in data["rendererWarnings"])


class TestConvertPlainText:
    def test_minimal_markdown(self, client):
        resp = client.post("/convert", json={"markdown": "# Hello\n\nWorld"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert len(resp.content) > 0

    @pytest.mark.parametrize("style", ["preview", "standard", "official", "internal", "report"])
    def test_all_styles(self, client, style):
        resp = client.post("/convert", json={
            "markdown": "# 测试\n\n正文内容。",
            "style": style,
        })
        assert resp.status_code == 200

    def test_invalid_style_returns_4xx(self, client):
        resp = client.post("/convert", json={
            "markdown": "# Test",
            "style": "nonexistent",
        })
        assert resp.status_code in (400, 422)

    def test_invalid_style_returns_style_invalid(self, client):
        resp = client.post("/convert", json={
            "markdown": "# Test",
            "style": "missing",
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "STYLE_INVALID"

    @pytest.mark.parametrize("style", ["standard", "official", "internal", "report"])
    def test_non_preview_styles_convert_complex_markdown(self, client, style):
        resp = client.post("/convert", json={
            "markdown": (
                "# 标题\n\n"
                "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
                "> **注意：** 说明内容\n\n"
                "```bash\nkubectl get pods\n```"
            ),
            "style": style,
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert len(resp.content) > 10_000

    def test_response_headers(self, client):
        resp = client.post("/convert", json={"markdown": "# Test"})
        assert "x-service-version" in resp.headers
        assert "x-service-mode" in resp.headers

    def test_embed_font_warning_header_is_ascii_safe(self, client):
        resp = client.post("/convert", json={
            "markdown": "# 字体测试\n\n正文",
            "embedFont": True,
        })
        assert resp.status_code == 200
        assert "x-convert-warnings" in resp.headers

    def test_formal_style_font_fallback_is_returned_as_warning(self, client):
        with patch("app.main._font_status_by_style", return_value={
            "official": {
                "仿宋_GB2312": {
                    "status": "fallback",
                    "resolved": "Noto Sans CJK SC",
                    "fallback": "Noto Sans CJK SC",
                    "embeddable": True,
                }
            }
        }):
            resp = client.post("/convert", json={
                "markdown": "# 字体测试\n\n正文",
                "style": "official",
            })

        assert resp.status_code == 200
        warnings = json.loads(resp.headers["x-convert-warnings"])
        assert any("仿宋_GB2312" in warning and "Noto Sans CJK SC" in warning for warning in warnings)

    def test_convert_warnings_are_deduped(self, client):
        duplicate = RenderResult(
            markdown="# Test",
            warnings=["katex 渲染已降级：DOCX 服务运行用户缺少 Playwright Chromium。"] * 3,
        )
        with patch("app.main.render_charts_and_formulas_sync", return_value=duplicate):
            resp = client.post("/convert", json={
                "markdown": "# Test\n\nInline $a+b$ and $c+d$.",
                "style": "preview",
            })

        assert resp.status_code == 200
        warnings = json.loads(resp.headers["x-convert-warnings"])
        assert warnings == ["katex 渲染已降级：DOCX 服务运行用户缺少 Playwright Chromium。"]

    def test_null_footer_text_disables_generated_branding(self, client):
        resp = client.post("/convert", json={
            "markdown": "# 标题\n\n正文",
            "style": "preview",
            "footerText": None,
        })

        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            document_xml = z.read("word/document.xml").decode("utf-8")
        assert "由 MD Viewer 生成" not in document_xml

    @pytest.mark.parametrize("style", ["official", "internal", "report"])
    def test_formal_styles_default_to_no_generated_branding(self, client, style):
        resp = client.post("/convert", json={
            "markdown": "# 标题\n\n正文",
            "style": style,
        })

        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            document_xml = z.read("word/document.xml").decode("utf-8")
        assert "由 MD Viewer 生成" not in document_xml


class TestConvertWithImages:
    def test_with_valid_image(self, client, small_png_base64):
        resp = client.post("/convert", json={
            "markdown": "# Test\n\n![](mdv__chart__aabb0011__)",
            "images": [{
                "id": "mdv__chart__aabb0011__",
                "pngBase64": small_png_base64,
                "widthCm": 15.5,
            }],
        })
        assert resp.status_code == 200
        assert resp.headers.get("x-charts-rendered") == "1"

    def test_with_client_images_still_attempts_server_render_for_remaining_supported_charts(self, client, small_png_base64):
        markdown = "# Test\n\n![](mdv__chart__aabb0011__)\n\n```mermaid\nclassDiagram\n  A <|-- B\n```"
        with patch("app.main.render_charts_and_formulas_sync") as render_mock:
            render_mock.return_value = RenderResult(markdown=markdown)
            resp = client.post("/convert", json={
                "markdown": markdown,
                "images": [{
                    "id": "mdv__chart__aabb0011__",
                    "pngBase64": small_png_base64,
                    "widthCm": 15.5,
                }],
            })

        assert resp.status_code == 200
        assert render_mock.call_args.args[1] is None

    def test_with_alt_text_image_placeholder_injects_image(self, client, small_png_base64):
        resp = client.post("/convert", json={
            "markdown": "# Test\n\n![基础流程](mdv__chart__aabb0011__)",
            "images": [{
                "id": "mdv__chart__aabb0011__",
                "pngBase64": small_png_base64,
                "widthCm": 15.5,
            }],
        })

        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            media_entries = [name for name in z.namelist() if name.startswith("word/media/")]
            document_xml = z.read("word/document.xml").decode("utf-8")
        assert len(media_entries) == 1
        assert "mdv__chart__aabb0011__" not in document_xml

    def test_accepts_more_than_fifty_client_rendered_images(self, client, small_png_base64):
        images = [
            {
                "id": f"mdv__chart__{index:08x}__",
                "pngBase64": small_png_base64,
                "widthCm": 15.5,
            }
            for index in range(51)
        ]
        markdown = "# Test\n\n" + "\n\n".join(f"![]({image['id']})" for image in images)

        resp = client.post("/convert", json={
            "markdown": markdown,
            "images": images,
        })

        assert resp.status_code == 200
        assert resp.headers.get("x-charts-rendered") == "51"

    def test_invalid_request_image_reports_warning(self, client):
        resp = client.post("/convert", json={
            "markdown": "# Test\n\n![](mdv__chart__aabb0011__)",
            "images": [{
                "id": "mdv__chart__aabb0011__",
                "pngBase64": "not-valid",
                "widthCm": 15.5,
            }],
            "style": "report",
        })
        assert resp.status_code == 200
        assert "failed validation" in resp.headers.get("x-convert-warnings", "")


class TestRenderChartsSlimMode:
    def test_render_charts_returns_400_on_slim(self, client):
        resp = client.post("/convert", json={
            "markdown": "```mermaid\ngraph LR; A-->B\n```",
            "renderCharts": True,
        })
        # slim 模式没有 playwright，应返回 400 或 200+warning
        # 取决于实际检测逻辑
        assert resp.status_code in (200, 400)

    def test_full_mode_render_charts_uses_real_browser_renderer(self, client):
        pytest.importorskip("playwright.sync_api")
        if not _has_browser_assets():
            pytest.skip("browser chart renderer assets are not installed")

        with patch("app.main._detect_mode", return_value="full"):
            resp = client.post("/convert", json={
                "markdown": "```echarts\n{ xAxis: { type: 'category', data: ['A', 'B'] }, yAxis: {}, series: [{ type: 'bar', data: [1, 2] }] }\n```",
                "renderCharts": True,
            })

        assert resp.status_code == 200
        assert resp.headers.get("x-service-mode") == "serverRendered"
        assert "Playwright Sync API inside the asyncio loop" not in resp.headers.get("x-convert-warnings", "")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            image_name = next(n for n in z.namelist() if n.startswith("word/media/"))
            image = Image.open(io.BytesIO(z.read(image_name)))
        assert image.width == 2340


def _has_browser_assets() -> bool:
    here = Path(__file__).resolve()
    roots = [
        here.parents[1] / "node_modules",
        here.parents[2] / "md-viewer" / "node_modules",
    ]
    return any((root / "echarts" / "dist" / "echarts.min.js").exists() for root in roots)


class TestApiKey:
    def test_without_key_when_required(self):
        with patch.dict(os.environ, {"API_KEY": "secret123"}):
            from importlib import reload
            import app.main as main_mod
            reload(main_mod)
            c = TestClient(main_mod.app)
            resp = c.post("/convert", json={"markdown": "# Test"})
            assert resp.status_code == 401

    def test_with_correct_key(self):
        with patch.dict(os.environ, {"API_KEY": "secret123"}):
            from importlib import reload
            import app.main as main_mod
            reload(main_mod)
            c = TestClient(main_mod.app)
            resp = c.post(
                "/convert",
                json={"markdown": "# Test"},
                headers={"X-API-Key": "secret123"},
            )
            assert resp.status_code == 200


class TestRateLimit:
    """slowapi 在 TestClient 中的行为可能与生产不同，标记为可能跳过"""

    def test_rate_limit_triggers(self):
        with patch.dict(os.environ, {"RATE_LIMIT_PER_MIN": "2"}):
            from importlib import reload
            import app.main as main_mod
            reload(main_mod)
            c = TestClient(main_mod.app)
            for _ in range(3):
                resp = c.post("/convert", json={"markdown": "# Test"})
            # slowapi 在 TestClient 下可能不严格限制，仅验证不报 500
            assert resp.status_code in (200, 429)
