import pytest
import base64
from PIL import Image
from io import BytesIO
from pathlib import Path

from app.chart_renderers import RenderedImage, render_charts_and_formulas_sync, rendered_images_to_base64


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
