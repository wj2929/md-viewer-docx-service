"""W2-DOCX：未渲染图表围栏 → 中性占位（杜绝图表源码漏进 DOCX）。

覆盖：
- 纯函数 _neutralize_unrendered_chart_blocks：A 类(已支持但失败) / B 类(不支持) / 边界(普通代码块) / 占位符不动 / 多围栏偏移。
- 集成：/convert-source(CLI 全保真) 与 /convert(GUI 客户端送图) 两条路在图表渲染失败时产物不漏源码。
"""

import base64
import io
import zipfile

import pytest

from app.main import _neutralize_unrendered_chart_blocks, NEUTRAL_CHART_PLACEHOLDER


# --------------------------------------------------------------------------- #
# 纯函数单测
# --------------------------------------------------------------------------- #

class TestNeutralizePure:
    def test_a_class_failed_mermaid_becomes_placeholder(self):
        md = "# 标题\n\n```mermaid\nsankey-beta 客户,产品,100\n```\n\n正文"
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 1
        assert "sankey-beta" not in out
        assert "客户,产品" not in out
        assert NEUTRAL_CHART_PLACEHOLDER in out
        assert "正文" in out  # 周边正文保留

    @pytest.mark.parametrize("lang,source", [
        ("kroki", "[A] -> [B] KROKILEAK"),
        ("dbml", "Table users { id int DBMLLEAK }"),
        ("antv-g6", '{"nodes": "G6LEAK"}'),
        ("g6", '{"nodes": "G6ALIASLEAK"}'),
        ("plotly", '{"data": "PLOTLYLEAK"}'),
        ("structurizr", "workspace { STRUCTURIZRLEAK }"),
        ("pikchr", "box PIKCHRLEAK"),
        ("kroki-svgbob", "+--+ SVGBOBLEAK"),
    ])
    def test_b_class_unsupported_chart_becomes_placeholder(self, lang, source):
        md = f"前言\n\n```{lang}\n{source}\n```\n\n后语"
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 1, f"{lang} 应被中性化"
        assert source not in out, f"{lang} 源码不得残留"
        assert NEUTRAL_CHART_PLACEHOLDER in out

    @pytest.mark.parametrize("lang,source", [
        ("python", "import os  # 这是给人看的真实代码"),
        ("text", "graph TD 这是教学示例源码，不是图表"),
        ("bash", "rm -rf /tmp/x  # 普通脚本"),
        ("json", '{"config": "真实配置不是图表"}'),
        ("", "无语言围栏的纯代码"),
    ])
    def test_boundary_normal_code_blocks_untouched(self, lang, source):
        md = f"说明\n\n```{lang}\n{source}\n```\n\n结束"
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 0, f"```{lang} 不是图表语言，不得被中性化"
        assert source in out
        assert NEUTRAL_CHART_PLACEHOLDER not in out

    def test_image_placeholder_not_touched(self):
        # 成功渲染的图表此时已是 ![](mdv__chart__...) 占位（非围栏），不得被误伤
        md = "# t\n\n![](mdv__chart__aabbccdd__)\n\n正文"
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 0
        assert "mdv__chart__aabbccdd__" in out

    def test_mixed_success_placeholder_kept_failures_neutralized(self):
        md = (
            "# 报告\n\n"
            "![](mdv__chart__11111111__)\n\n"      # 成功图：图片占位，保留
            "```mermaid\nFAILMERMAID 客户\n```\n\n"  # A 类失败
            "中间段落\n\n"
            "```kroki\nFAILKROKI [A]->[B]\n```\n"    # B 类不支持
        )
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 2
        assert "mdv__chart__11111111__" in out      # 成功图占位不动
        assert "FAILMERMAID" not in out
        assert "FAILKROKI" not in out
        assert "中间段落" in out
        assert out.count(NEUTRAL_CHART_PLACEHOLDER) == 2

    def test_multiple_same_type_offsets_correct(self):
        md = (
            "```mermaid\nAAA\n```\n\n"
            "```mermaid\nBBB\n```\n\n"
            "```mermaid\nCCC\n```\n"
        )
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 3
        for token in ("AAA", "BBB", "CCC"):
            assert token not in out
        assert out.count(NEUTRAL_CHART_PLACEHOLDER) == 3

    def test_no_charts_returns_unchanged(self):
        md = "# 纯文本\n\n没有任何图表。\n\n```python\nx = 1\n```"
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 0
        assert out == md

    def test_case_insensitive_language(self):
        md = "```Mermaid\nUPPERLEAK\n```"
        out, count = _neutralize_unrendered_chart_blocks(md)
        assert count == 1
        assert "UPPERLEAK" not in out


# --------------------------------------------------------------------------- #
# 集成：/convert-source（CLI 全保真路径）
# --------------------------------------------------------------------------- #

def _make_fake_render_result(images, status="partial", failed=1):
    class FakeSummary:
        def model_dump(self):
            return {"totalBlocks": 1, "renderedBlocks": len(images),
                    "failedBlocks": failed, "warningCount": 0, "statusText": status}

    class FakeResult:
        ok = status == "success"
        warnings = []
        renderSummary = FakeSummary()

    FakeResult.status = status
    FakeResult.images = images
    FakeResult.stats = {"totalBlocks": 1, "renderedBlocks": len(images),
                        "failedBlocks": failed, "durationMs": 10}
    return FakeResult()


def test_convert_source_failed_chart_no_source_leak(client, monkeypatch):
    """A 类：full-fidelity 渲染失败（无图片）→ 产物不得残留图表源码，应为中性占位。"""
    from app import main

    monkeypatch.setattr(
        main, "render_markdown_full_fidelity",
        lambda **kwargs: _make_fake_render_result(images=[], status="partial", failed=1),
    )

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n```mermaid\nsankey-beta SANKEYLEAK,产品,42\n```\n\n正文",
        "style": "preview",
    })

    assert resp.status_code == 200
    assert resp.headers["x-charts-neutralized"] == "1"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    assert "sankey-beta" not in document_xml
    assert "SANKEYLEAK" not in document_xml
    assert "图表未渲染" in document_xml


def test_convert_source_unsupported_kroki_no_source_leak(client, monkeypatch):
    """B 类：不支持的 kroki 即使渲染器没认它，产物也不得漏源码。"""
    from app import main

    monkeypatch.setattr(
        main, "render_markdown_full_fidelity",
        lambda **kwargs: _make_fake_render_result(images=[], status="partial", failed=1),
    )

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n```kroki\nKROKISECRET [A] -> [B]\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    assert resp.headers["x-charts-neutralized"] == "1"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    assert "KROKISECRET" not in document_xml
    assert "图表未渲染" in document_xml


def test_convert_source_normal_doc_zero_neutralized(client, monkeypatch):
    """对照：正常文档（无图表）→ 零中性化、零误伤。"""
    from app import main

    monkeypatch.setattr(
        main, "render_markdown_full_fidelity",
        lambda **kwargs: _make_fake_render_result(images=[], status="success", failed=0),
    )

    resp = client.post("/convert-source", json={
        "sourceType": "markdown",
        "markdown": "# 标题\n\n正文段落\n\n```python\nprint('hello')\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    assert resp.headers["x-charts-neutralized"] == "0"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    assert "print('hello')" in document_xml  # 真实代码块保留
    assert "图表未渲染" not in document_xml


# --------------------------------------------------------------------------- #
# 集成：/convert（GUI 客户端送图路径）
# --------------------------------------------------------------------------- #

def test_convert_client_path_unsupported_chart_no_source_leak(client):
    """GUI 路径：客户端送来的 md 含未渲染图表围栏 → 服务端安全网中性化，不漏源码。"""
    resp = client.post("/convert", json={
        "markdown": "# 标题\n\n```kroki\nGUIKROKILEAK [X] -> [Y]\n```\n\n正文",
        "style": "preview",
    })

    assert resp.status_code == 200
    assert resp.headers["x-charts-neutralized"] == "1"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    assert "GUIKROKILEAK" not in document_xml
    assert "图表未渲染" in document_xml


def test_convert_client_path_normal_code_untouched(client):
    """GUI 路径对照：普通代码块不被误伤。"""
    resp = client.post("/convert", json={
        "markdown": "# 标题\n\n```python\nKEEPME = 42\n```",
        "style": "preview",
    })

    assert resp.status_code == 200
    assert resp.headers["x-charts-neutralized"] == "0"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
    assert "KEEPME" in document_xml
