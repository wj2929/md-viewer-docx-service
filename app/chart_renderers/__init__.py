"""
服务端图表与公式预渲染。

full 镜像优先使用真实渲染器；当前稳定路径先覆盖 Graphviz 的原生
dot 渲染，其余图表和 KaTeX 公式退化为等宽 PNG 代码图，确保 DOCX
里可见且不会破坏导出流程。退化信息通过 warnings 返回给客户端。
"""
from __future__ import annotations

import base64
import io
import re
import subprocess
import textwrap
import uuid
from dataclasses import dataclass, field
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


SUPPORTED_CHART_LANGS = {"mermaid", "echarts", "dot", "graphviz", "markmap", "plantuml"}
FENCE_RE = re.compile(r"```([A-Za-z0-9_-]+)\n([\s\S]*?)```", re.MULTILINE)
BLOCK_MATH_RE = re.compile(r"\$\$\n?([\s\S]*?)\n?\$\$", re.MULTILINE)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")


@dataclass
class RenderedImage:
    id: str
    png_bytes: bytes
    width_cm: float = 15.5


@dataclass
class RenderResult:
    markdown: str
    images: dict[str, RenderedImage] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def render_charts_and_formulas_sync(
    markdown: str,
    chart_renderers: Iterable[str] | None = None,
) -> RenderResult:
    """把服务端可识别的图表代码块和 KaTeX 公式转换为图片占位符。"""
    if chart_renderers is None:
        enabled = set(SUPPORTED_CHART_LANGS)
    else:
        enabled = {r.lower() for r in chart_renderers}

    result = RenderResult(markdown=markdown)

    def replace_fence(match: re.Match[str]) -> str:
        lang = match.group(1).lower()
        code = match.group(2).strip("\n")
        if lang not in SUPPORTED_CHART_LANGS or lang not in enabled:
            return match.group(0)

        placeholder = _new_placeholder()
        try:
            png = _render_chart_png(lang, code)
        except Exception as exc:
            png = _render_text_png(f"{lang}\n\n{code}", title=f"{lang} 渲染失败，已保留源码图")
            result.warnings.append(f"{lang} render fallback: {exc}")

        result.images[placeholder] = RenderedImage(id=placeholder, png_bytes=png)
        return f"![]({placeholder})"

    result.markdown = FENCE_RE.sub(replace_fence, result.markdown)

    def replace_block_math(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        placeholder = _new_placeholder()
        result.images[placeholder] = RenderedImage(
            id=placeholder,
            png_bytes=_render_text_png(expr, title="KaTeX 公式"),
            width_cm=12.0,
        )
        return f"![]({placeholder})"

    result.markdown = BLOCK_MATH_RE.sub(replace_block_math, result.markdown)

    def replace_inline_math(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        placeholder = _new_placeholder()
        result.images[placeholder] = RenderedImage(
            id=placeholder,
            png_bytes=_render_text_png(expr, title="行内公式"),
            width_cm=8.0,
        )
        return f"\n\n![]({placeholder})\n\n"

    result.markdown = INLINE_MATH_RE.sub(replace_inline_math, result.markdown)
    return result


def _new_placeholder() -> str:
    return f"mdv__chart__{uuid.uuid4().hex[:8]}__"


def _render_chart_png(lang: str, code: str) -> bytes:
    if lang in {"dot", "graphviz"}:
        return _render_dot_png(code)
    return _render_text_png(code, title=f"{lang} 图表")


def _render_dot_png(code: str) -> bytes:
    proc = subprocess.run(
        ["dot", "-Tpng"],
        input=code.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[:300] or "dot failed")
    return proc.stdout


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/custom/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render_text_png(text: str, title: str) -> bytes:
    font = _load_font(24)
    title_font = _load_font(28)
    wrapped_lines: list[str] = []
    for raw in text.splitlines() or [""]:
        wrapped_lines.extend(textwrap.wrap(raw, width=76, replace_whitespace=False) or [""])

    width = 1400
    line_height = 34
    height = max(180, 92 + line_height * len(wrapped_lines))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=12, outline="#D0D7DE", width=2, fill="#F6F8FA")
    draw.text((42, 34), title, fill="#24292F", font=title_font)
    y = 84
    for line in wrapped_lines:
        draw.text((42, y), line, fill="#24292F", font=font)
        y += line_height

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def rendered_images_to_base64(images: dict[str, RenderedImage]) -> list[dict]:
    return [
        {
            "id": image.id,
            "pngBase64": base64.b64encode(image.png_bytes).decode("ascii"),
            "widthCm": image.width_cm,
        }
        for image in images.values()
    ]
