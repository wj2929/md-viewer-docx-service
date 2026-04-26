from app.chart_renderers import render_charts_and_formulas_sync


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
