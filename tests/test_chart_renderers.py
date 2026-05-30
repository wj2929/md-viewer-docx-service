import pytest
import base64
from PIL import Image
from io import BytesIO
from pathlib import Path

from app.chart_renderers import (
    RenderedImage,
    _render_fallback_warning,
    _normalize_plantuml_code,
    render_charts_and_formulas_sync,
    rendered_images_to_base64,
)


def _has_browser_assets() -> bool:
    here = Path(__file__).resolve()
    roots = [
        here.parents[1] / "node_modules",
        here.parents[2] / "md-viewer" / "node_modules",
    ]
    return any((root / "mermaid" / "dist" / "mermaid.min.js").exists() for root in roots)


def _has_katex_assets() -> bool:
    here = Path(__file__).resolve()
    roots = [
        here.parents[1] / "node_modules",
        here.parents[2] / "md-viewer" / "node_modules",
    ]
    return any((root / "katex" / "dist" / "katex.min.js").exists() for root in roots)


def test_render_charts_replaces_supported_fences_with_images():
    markdown = "# Demo\n\n```mermaid\ngraph LR; A-->B\n```\n\nDone."

    result = render_charts_and_formulas_sync(markdown, ["mermaid"])

    assert "![](mdv__chart__" in result.markdown
    assert "```mermaid" not in result.markdown
    assert len(result.images) == 1
    image = next(iter(result.images.values()))
    assert image.id.startswith("mdv__chart__")
    assert image.width_cm == 15.5
    assert len(image.png_bytes) > 100


def test_render_formulas_replaces_katex_blocks_with_images():
    markdown = "# Math\n\n$$\nE = mc^2\n$$\n\nInline $a+b$ text."

    result = render_charts_and_formulas_sync(markdown, [])

    assert "![](mdv__chart__" in result.markdown
    assert "$$" not in result.markdown
    assert "$a+b$" not in result.markdown
    assert len(result.images) == 2


def test_playwright_browser_missing_warning_is_user_actionable():
    error = RuntimeError(
        "BrowserType.launch: Executable doesn't exist at "
        "/var/root/Library/Caches/ms-playwright/chromium_headless_shell-1187/chrome-mac/headless_shell\n"
        "╔════════════════════════════════════════════════════════════╗\n"
        "║ Looks like Playwright was just installed or updated.       ║\n"
        "║     playwright install                                     ║\n"
        "╚════════════════════════════════════════════════════════════╝"
    )

    warning = _render_fallback_warning("katex", error)

    assert warning.startswith("katex 渲染已降级")
    assert "同一用户" in warning
    assert "python -m playwright install chromium" in warning
    assert "/var/root" not in warning
    assert "╔" not in warning


def test_full_mode_katex_renderer_produces_formula_png():
    pytest.importorskip("playwright.sync_api")
    if not _has_katex_assets():
        pytest.skip("katex renderer assets are not installed")

    result = render_charts_and_formulas_sync("$$\nx = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\n$$", [])

    assert len(result.images) == 1
    image = next(iter(result.images.values()))
    assert len(image.png_bytes) > 2_000
    png = Image.open(BytesIO(image.png_bytes))
    assert png.width < 1400
    assert png.height < 320


def test_rendered_images_to_base64_downscales_oversized_images_for_injection():
    buf = BytesIO()
    Image.new("RGB", (2340, 9100), color="white").save(buf, format="PNG")

    encoded = rendered_images_to_base64({
        "mdv__chart__abcdef12__": RenderedImage(
            id="mdv__chart__abcdef12__",
            png_bytes=buf.getvalue(),
            width_cm=15.5,
        )
    })[0]

    png = Image.open(BytesIO(base64.b64decode(encoded["pngBase64"])))
    assert png.width * png.height <= 20_000_000
    assert encoded["widthCm"] < 7.0
    assert encoded["widthCm"] * (png.height / png.width) <= 24.1


def test_plantuml_renderer_uses_png_server(monkeypatch):
    import requests

    class Response:
        status_code = 200
        content = b"\x89PNG\r\n\x1a\nplantuml"

    captured = {}

    def fake_get(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setenv("MDV_PLANTUML_SERVER_URL", "http://127.0.0.1:8080/plantuml")

    result = render_charts_and_formulas_sync(
        "```plantuml\n@startuml\nAlice -> Bob: hello\n@enduml\n```",
        ["plantuml"],
    )

    assert "```plantuml" not in result.markdown
    assert "![](mdv__chart__" in result.markdown
    assert captured["url"].startswith("http://127.0.0.1:8080/plantuml/png/")
    assert len(result.images) == 1


def test_puml_alias_uses_plantuml_renderer(monkeypatch):
    import requests

    class Response:
        status_code = 200
        content = b"\x89PNG\r\n\x1a\nplantuml"

    def fake_get(url, timeout):
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setenv("MDV_PLANTUML_SERVER_URL", "http://127.0.0.1:8080/plantuml")

    result = render_charts_and_formulas_sync(
        "```puml\n@startuml\nAlice -> Bob: hello\n@enduml\n```",
        ["plantuml"],
    )

    assert "```puml" not in result.markdown
    assert "![](mdv__chart__" in result.markdown
    assert len(result.images) == 1


def test_plantuml_renderer_ignores_backticks_inside_code(monkeypatch):
    import requests

    class Response:
        status_code = 200
        content = b"\x89PNG\r\n\x1a\nplantuml"

    monkeypatch.setattr(requests, "get", lambda url, timeout: Response())
    monkeypatch.setenv("MDV_PLANTUML_SERVER_URL", "http://127.0.0.1:8080/plantuml")

    markdown = """# Demo

```plantuml
@startuml
title Markdown 代码块正则匹配
state "匹配 ```" as MatchFence
MatchFence --> Done
@enduml
```

## Next Heading

正文
"""

    result = render_charts_and_formulas_sync(markdown, ["plantuml"])

    assert "state \"匹配 ```\"" not in result.markdown
    assert "MatchFence --> Done" not in result.markdown
    assert "@enduml" not in result.markdown
    assert "## Next Heading" in result.markdown
    assert "正文" in result.markdown
    assert len(result.images) == 1


def test_plantuml_normalizer_expands_single_line_classes():
    code = """@startuml
class A01 { +method(): void }
class A02 { +method(): void }
A01 --> A02
@enduml"""

    normalized = _normalize_plantuml_code(code)

    assert "class A01 {\n  +method(): void\n}" in normalized
    assert "class A02 {\n  +method(): void\n}" in normalized
    assert "A01 --> A02" in normalized


def test_plantuml_normalizer_uses_nwdiag_markers():
    code = """@startuml
nwdiag {
  network LAN {
    A
  }
}
@enduml"""

    normalized = _normalize_plantuml_code(code)

    assert normalized.startswith("@startnwdiag")
    assert normalized.rstrip().endswith("@endnwdiag")


def test_plantuml_renderer_keeps_server_error_png_instead_of_source_fallback(monkeypatch):
    import requests

    class Response:
        status_code = 400
        content = b"\x89PNG\r\n\x1a\nplantuml-error"
        headers = {"content-type": "image/png"}

    monkeypatch.setattr(requests, "get", lambda url, timeout: Response())
    monkeypatch.setenv("MDV_PLANTUML_SERVER_URL", "http://127.0.0.1:8080/plantuml")

    result = render_charts_and_formulas_sync(
        "```plantuml\n@startuml\ninvalid\n@enduml\n```",
        ["plantuml"],
    )

    assert "```plantuml" not in result.markdown
    assert "invalid" not in result.markdown
    assert len(result.images) == 1
    assert next(iter(result.images.values())).png_bytes == b"\x89PNG\r\n\x1a\nplantuml-error"


def test_plantuml_renderer_retries_transient_request_failures(monkeypatch):
    import requests

    class Response:
        status_code = 200
        content = b"\x89PNG\r\n\x1a\nplantuml-ok"
        headers = {"content-type": "image/png"}

    calls = {"count": 0}

    def flaky_get(url, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.Timeout("temporary timeout")
        return Response()

    monkeypatch.setattr(requests, "get", flaky_get)
    monkeypatch.setenv("MDV_PLANTUML_SERVER_URL", "http://127.0.0.1:8080/plantuml")
    monkeypatch.setenv("MDV_PLANTUML_RETRIES", "2")

    result = render_charts_and_formulas_sync(
        "```plantuml\n@startuml\nAlice -> Bob: ok\n@enduml\n```",
        ["plantuml"],
    )

    assert calls["count"] == 2
    assert len(result.images) == 1
    assert next(iter(result.images.values())).png_bytes == b"\x89PNG\r\n\x1a\nplantuml-ok"
    assert result.warnings == []


def test_rendered_images_to_base64_does_not_enlarge_small_chart_images():
    buf = BytesIO()
    Image.new("RGB", (360, 180), color="white").save(buf, format="PNG")

    encoded = rendered_images_to_base64({
        "mdv__chart__abcdef12__": RenderedImage(
            id="mdv__chart__abcdef12__",
            png_bytes=buf.getvalue(),
            width_cm=15.5,
        )
    })[0]

    assert 6.0 <= encoded["widthCm"] <= 7.0


@pytest.mark.parametrize(("lang", "code"), [
    ("mermaid", "graph LR\n  A[Start] --> B[End]"),
    ("echarts", "{ xAxis: { type: 'category', data: ['A', 'B'] }, yAxis: {}, series: [{ type: 'bar', data: [1, 2] }] }"),
    ("markmap", "# Root\n## Branch A\n## Branch B"),
])
def test_full_mode_browser_renderers_produce_real_png(lang, code):
    pytest.importorskip("playwright.sync_api")
    if not _has_browser_assets():
        pytest.skip("browser chart renderer assets are not installed")
    markdown = f"```{lang}\n{code}\n```"

    result = render_charts_and_formulas_sync(markdown, [lang])

    assert len(result.images) == 1
    image = next(iter(result.images.values()))
    assert len(image.png_bytes) > 2_000
    png = Image.open(BytesIO(image.png_bytes))
    assert png.width == 2340
    assert png.height > 400
