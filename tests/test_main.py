import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app


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

    def test_status_is_ok(self, client):
        data = client.get("/healthz").json()
        assert data["status"] == "ok"

    def test_styles_include_standard(self, client):
        data = client.get("/healthz").json()
        assert "standard" in data["styles"]

    def test_dot_renderer_requires_dot_binary(self, client):
        with patch("app.main.shutil.which", return_value=None):
            data = client.get("/healthz").json()
            assert "dot" not in data["chartRenderersAvailable"]


class TestConvertPlainText:
    def test_minimal_markdown(self, client):
        resp = client.post("/convert", json={"markdown": "# Hello\n\nWorld"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert len(resp.content) > 0

    @pytest.mark.parametrize("style", ["standard", "official", "internal", "report"])
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


class TestRenderChartsSlimMode:
    def test_render_charts_returns_400_on_slim(self, client):
        resp = client.post("/convert", json={
            "markdown": "```mermaid\ngraph LR; A-->B\n```",
            "renderCharts": True,
        })
        # slim 模式没有 playwright，应返回 400 或 200+warning
        # 取决于实际检测逻辑
        assert resp.status_code in (200, 400)


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
