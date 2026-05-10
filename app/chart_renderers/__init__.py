"""服务端图表与公式预渲染。"""
from __future__ import annotations

import base64
import io
import html
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import tempfile
import time
import uuid
import zlib
from dataclasses import dataclass, field
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


SUPPORTED_CHART_LANGS = {"mermaid", "echarts", "dot", "graphviz", "markmap", "plantuml", "puml"}
CHART_LANG_ALIASES = {
    "dot": "graphviz",
    "puml": "plantuml",
}
FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]+)[^\n]*\n([\s\S]*?)^```\s*$", re.MULTILINE)
BLOCK_MATH_RE = re.compile(r"\$\$\n?([\s\S]*?)\n?\$\$", re.MULTILINE)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")
DOCX_IMAGE_MAX_PIXELS = 20_000_000
DOCX_CHART_MAX_WIDTH_CM = 15.5
DOCX_CHART_MAX_HEIGHT_CM = 24.0
DOCX_CHART_WIDTH_CM_PER_PX = 0.018


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
        enabled = {_canonical_chart_lang(r.lower()) for r in chart_renderers}

    result = RenderResult(markdown=markdown)

    def replace_fence(match: re.Match[str]) -> str:
        lang = match.group(1).lower()
        canonical_lang = _canonical_chart_lang(lang)
        code = match.group(2).strip("\n")
        if lang not in SUPPORTED_CHART_LANGS or canonical_lang not in enabled:
            return match.group(0)

        placeholder = _new_placeholder()
        try:
            png = _render_chart_png(canonical_lang, code)
        except Exception as exc:
            png = _render_text_png(f"{lang}\n\n{code}", title=f"{lang} 渲染失败，已保留源码图")
            result.warnings.append(f"{lang} render fallback: {exc}")

        result.images[placeholder] = RenderedImage(id=placeholder, png_bytes=png)
        return f"\n\n![]({placeholder})\n\n"

    result.markdown = FENCE_RE.sub(replace_fence, result.markdown)

    def replace_block_math(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        placeholder = _new_placeholder()
        try:
            png = _render_katex_png(expr, display_mode=True)
        except Exception as exc:
            png = _render_text_png(expr, title="KaTeX 公式渲染失败，已保留源码图")
            result.warnings.append(f"katex render fallback: {exc}")
        result.images[placeholder] = RenderedImage(
            id=placeholder,
            png_bytes=png,
            width_cm=12.0,
        )
        return f"![]({placeholder})"

    result.markdown = BLOCK_MATH_RE.sub(replace_block_math, result.markdown)

    def replace_inline_math(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        placeholder = _new_placeholder()
        try:
            png = _render_katex_png(expr, display_mode=False)
        except Exception as exc:
            png = _render_text_png(expr, title="行内公式渲染失败，已保留源码图")
            result.warnings.append(f"katex render fallback: {exc}")
        result.images[placeholder] = RenderedImage(
            id=placeholder,
            png_bytes=png,
            width_cm=8.0,
        )
        return f"\n\n![]({placeholder})\n\n"

    result.markdown = INLINE_MATH_RE.sub(replace_inline_math, result.markdown)
    return result


def _canonical_chart_lang(lang: str) -> str:
    return CHART_LANG_ALIASES.get(lang, lang)


def _new_placeholder() -> str:
    return f"mdv__chart__{uuid.uuid4().hex[:8]}__"


def _render_chart_png(lang: str, code: str) -> bytes:
    if lang in {"dot", "graphviz"}:
        return _render_dot_png(code)
    if lang in {"mermaid", "echarts", "markmap"}:
        return _render_browser_chart_png(lang, code)
    if lang == "plantuml":
        return _render_plantuml_png(code)
    return _render_text_png(code, title=f"{lang} 图表")


def _render_dot_png(code: str) -> bytes:
    if not shutil.which("dot"):
        raise RuntimeError("dot binary is not installed")
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


PLANTUML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"


def _append_plantuml_3bytes(data: list[str], b1: int, b2: int, b3: int) -> None:
    c1 = b1 >> 2
    c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
    c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
    c4 = b3 & 0x3F
    data.extend([
        PLANTUML_ALPHABET[c1 & 0x3F],
        PLANTUML_ALPHABET[c2 & 0x3F],
        PLANTUML_ALPHABET[c3 & 0x3F],
        PLANTUML_ALPHABET[c4 & 0x3F],
    ])


def _encode_plantuml(code: str) -> str:
    compressed = zlib.compress(code.encode("utf-8"), 9)[2:-4]
    result: list[str] = []
    for index in range(0, len(compressed), 3):
        chunk = compressed[index:index + 3]
        b1 = chunk[0]
        b2 = chunk[1] if len(chunk) > 1 else 0
        b3 = chunk[2] if len(chunk) > 2 else 0
        _append_plantuml_3bytes(result, b1, b2, b3)
    return "".join(result)


def _normalize_plantuml_code(code: str) -> str:
    normalized = code
    if re.search(r"(?m)^\s*nwdiag\s*\{", normalized):
        normalized = re.sub(r"(?m)^@startuml\s*$", "@startnwdiag", normalized, count=1)
        normalized = re.sub(r"(?m)^@enduml\s*$", "@endnwdiag", normalized)

    def expand_single_line_class(match: re.Match[str]) -> str:
        name = match.group(1)
        body = match.group(2).strip()
        return f"class {name} {{\n  {body}\n}}"

    normalized = re.sub(
        r"(?m)^class\s+([A-Za-z_][\w.]*)\s*\{\s*([^{}\n]+?)\s*\}\s*$",
        expand_single_line_class,
        normalized,
    )
    return normalized


def _render_plantuml_png(code: str) -> bytes:
    import requests

    server_url = os.environ.get("MDV_PLANTUML_SERVER_URL") or os.environ.get("PLANTUML_SERVER_URL") or "https://www.plantuml.com/plantuml"
    server_url = server_url.rstrip("/")
    code = _normalize_plantuml_code(code)
    encoded = _encode_plantuml(code)
    timeout = float(os.environ.get("MDV_PLANTUML_TIMEOUT_SEC", "12"))
    retries = max(1, int(os.environ.get("MDV_PLANTUML_RETRIES", "3")))

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            if len(encoded) <= 4000:
                response = requests.get(f"{server_url}/png/{encoded}", timeout=timeout)
            else:
                response = requests.post(
                    f"{server_url}/png",
                    data=code.encode("utf-8"),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                    timeout=timeout,
                )
            if response.content.startswith(b"\x89PNG\r\n\x1a\n"):
                return response.content
            if response.status_code != 200:
                last_error = RuntimeError(f"PlantUML server returned {response.status_code}")
            else:
                last_error = RuntimeError("PlantUML server returned non-PNG content")
        except Exception as exc:
            last_error = exc

        if attempt < retries - 1:
            time.sleep(min(0.25 * (attempt + 1), 1.0))

    raise RuntimeError(str(last_error) if last_error else "PlantUML render failed")


def _render_browser_chart_png(lang: str, code: str) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is not installed") from exc

    html_path = _write_chart_html(lang, code)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
            page.goto(html_path.as_uri(), wait_until="networkidle", timeout=20_000)
            page.wait_for_function("window.__mdvDone === true || window.__mdvError", timeout=20_000)
            error = page.evaluate("window.__mdvError || ''")
            if error:
                raise RuntimeError(str(error)[:300])
            locator = page.locator("#capture")
            png = locator.screenshot(type="png", timeout=10_000)
            browser.close()
            return png
    finally:
        try:
            html_path.unlink(missing_ok=True)
        except Exception:
            pass


def _render_katex_png(expr: str, display_mode: bool) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is not installed") from exc

    html_path = _write_katex_html(expr, display_mode)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 420}, device_scale_factor=2)
            page.goto(html_path.as_uri(), wait_until="networkidle", timeout=20_000)
            page.wait_for_function("window.__mdvDone === true || window.__mdvError", timeout=20_000)
            error = page.evaluate("window.__mdvError || ''")
            if error:
                raise RuntimeError(str(error)[:300])
            locator = page.locator("#capture")
            png = locator.screenshot(type="png", timeout=10_000)
            browser.close()
            return png
    finally:
        try:
            html_path.unlink(missing_ok=True)
        except Exception:
            pass


def _write_chart_html(lang: str, code: str) -> Path:
    if lang == "echarts":
        assets = _resolve_browser_assets(["echarts"])
        body = _echarts_html(code, assets)
    elif lang == "mermaid":
        assets = _resolve_browser_assets(["mermaid"])
        body = _mermaid_html(code, assets)
    elif lang == "markmap":
        assets = _resolve_browser_assets(["d3", "markmap_lib", "markmap_view"])
        body = _markmap_html(code, assets)
    else:
        raise RuntimeError(f"unsupported browser renderer: {lang}")

    fd, tmp_name = tempfile.mkstemp(prefix=f"mdv-{lang}-", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    return Path(tmp_name)


def _write_katex_html(expr: str, display_mode: bool) -> Path:
    assets = _resolve_browser_assets(["katex", "katex_css"])
    scripts = f"""
  <link rel="stylesheet" href="{html.escape(assets["katex_css"])}">
  <script src="{html.escape(assets["katex"])}"></script>
"""
    render_script = """
    (() => {
      try {
        const el = document.getElementById('capture');
        katex.render(SOURCE, el, {
          throwOnError: false,
          displayMode: DISPLAY_MODE,
          output: 'html',
          strict: false,
          trust: false
        });
        requestAnimationFrame(() => { window.__mdvDone = true; });
      } catch (error) {
        window.__mdvError = error && error.message ? error.message : String(error);
      }
    })();
    """.replace("DISPLAY_MODE", "true" if display_mode else "false")

    body = _base_html(expr, scripts, render_script, capture_class="katex-capture")
    fd, tmp_name = tempfile.mkstemp(prefix="mdv-katex-", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    return Path(tmp_name)


def _resolve_browser_assets(required: Iterable[str]) -> dict[str, str]:
    roots = [
        Path(__file__).resolve().parents[2] / "node_modules",
        Path(__file__).resolve().parents[3] / "md-viewer" / "node_modules",
    ]
    found_root = next((root for root in roots if root.exists()), None)
    if not found_root:
        raise RuntimeError("node_modules with chart renderers is not installed")

    paths = {
        "echarts": found_root / "echarts" / "dist" / "echarts.min.js",
        "mermaid": found_root / "mermaid" / "dist" / "mermaid.min.js",
        "d3": found_root / "d3" / "dist" / "d3.min.js",
        "markmap_lib": found_root / "markmap-lib" / "dist" / "browser" / "index.iife.js",
        "markmap_view": found_root / "markmap-view" / "dist" / "browser" / "index.js",
        "katex": found_root / "katex" / "dist" / "katex.min.js",
        "katex_css": found_root / "katex" / "dist" / "katex.min.css",
    }
    required_set = set(required)
    missing = [name for name in required_set if not paths[name].exists()]
    if missing:
        raise RuntimeError(f"missing chart renderer assets: {', '.join(missing)}")
    return {name: path.as_uri() for name, path in paths.items() if name in required_set}


def _base_html(source: str, scripts: str, render_script: str, capture_class: str = "") -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{ margin: 0; padding: 0; background: white; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC", "PingFang SC", Arial, sans-serif; }}
    #capture {{ width: 1170px; min-height: 420px; background: white; padding: 24px; box-sizing: border-box; }}
    #capture.katex-capture {{ min-height: 0; display: inline-block; width: auto; max-width: 1170px; padding: 28px 36px; font-size: 28px; line-height: 1.6; }}
    #capture.katex-capture .katex-display {{ margin: 0; text-align: center; }}
    #capture.katex-capture .katex {{ color: #1A1A1A; }}
    svg {{ max-width: 100%; }}
  </style>
  {scripts}
</head>
<body>
  <div id="capture" class="{html.escape(capture_class)}"></div>
  <script>
    const SOURCE = {source!r};
    {render_script}
  </script>
</body>
</html>"""


def _echarts_html(code: str, assets: dict[str, str]) -> str:
    scripts = f'<script src="{html.escape(assets["echarts"])}"></script>'
    render_script = """
    (async () => {
      try {
        const option = Function('"use strict"; return (' + SOURCE.replace(/\\/\\/.*$/gm, '').replace(/\\/\\*[\\s\\S]*?\\*\\//g, '').replace(/^(?:const|let|var)\\s+\\w+\\s*=\\s*/, '').replace(/^\\w+\\s*=\\s*/, '').replace(/;\\s*$/, '') + ')')();
        const el = document.getElementById('capture');
        el.style.height = '620px';
        const chart = echarts.init(el, null, { renderer: 'svg', width: 1170, height: 620 });
        chart.setOption({ ...option, animation: false });
        await new Promise(resolve => setTimeout(resolve, 300));
        window.__mdvDone = true;
      } catch (error) {
        window.__mdvError = error && error.message ? error.message : String(error);
      }
    })();
    """
    return _base_html(code, scripts, render_script)


def _mermaid_html(code: str, assets: dict[str, str]) -> str:
    scripts = f'<script src="{html.escape(assets["mermaid"])}"></script>'
    render_script = """
    (async () => {
      try {
        mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default', flowchart: { htmlLabels: true, useMaxWidth: true }, sequence: { useMaxWidth: true } });
        const result = await mermaid.render('mdv-mermaid-' + Date.now(), SOURCE);
        const el = document.getElementById('capture');
        el.innerHTML = result.svg;
        const svg = el.querySelector('svg');
        if (svg) {
          svg.removeAttribute('height');
          svg.setAttribute('width', '1120');
          svg.style.maxWidth = '1120px';
          svg.style.display = 'block';
        }
        await new Promise(resolve => setTimeout(resolve, 200));
        window.__mdvDone = true;
      } catch (error) {
        window.__mdvError = error && error.message ? error.message : String(error);
      }
    })();
    """
    return _base_html(code, scripts, render_script)


def _markmap_html(code: str, assets: dict[str, str]) -> str:
    scripts = "\n".join([
        f'<script src="{html.escape(assets["d3"])}"></script>',
        f'<script src="{html.escape(assets["markmap_lib"])}"></script>',
        f'<script src="{html.escape(assets["markmap_view"])}"></script>',
    ])
    render_script = """
    (async () => {
      try {
        const el = document.getElementById('capture');
        el.style.height = '640px';
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '1120');
        svg.setAttribute('height', '600');
        el.appendChild(svg);
        const transformer = new markmap.Transformer();
        const { root, features } = transformer.transform(SOURCE);
        const opts = markmap.deriveOptions(features);
        const mm = markmap.Markmap.create(svg, opts, root);
        await new Promise(resolve => requestAnimationFrame(resolve));
        await mm.fit();
        await new Promise(resolve => setTimeout(resolve, 500));
        window.__mdvDone = true;
      } catch (error) {
        window.__mdvError = error && error.message ? error.message : String(error);
      }
    })();
    """
    return _base_html(code, scripts, render_script)


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


def _docx_safe_chart_image(image: RenderedImage) -> RenderedImage:
    with Image.open(io.BytesIO(image.png_bytes)) as source:
        width, height = source.size
        next_image = source.copy()

    if width * height > DOCX_IMAGE_MAX_PIXELS:
        scale = math.sqrt(DOCX_IMAGE_MAX_PIXELS / (width * height))
        width = max(1, int(width * scale))
        height = max(1, int(height * scale))
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        next_image = next_image.resize((width, height), resampling)

    ratio = height / width if width > 0 else 1
    pixel_based_width_cm = width * DOCX_CHART_WIDTH_CM_PER_PX
    width_cm = min(image.width_cm, DOCX_CHART_MAX_WIDTH_CM, pixel_based_width_cm, DOCX_CHART_MAX_HEIGHT_CM / ratio)
    width_cm = max(4.0, round(width_cm, 2))

    buf = io.BytesIO()
    next_image.save(buf, format="PNG")
    return RenderedImage(id=image.id, png_bytes=buf.getvalue(), width_cm=width_cm)


def rendered_images_to_base64(images: dict[str, RenderedImage]) -> list[dict]:
    return [
        {
            "id": safe_image.id,
            "pngBase64": base64.b64encode(safe_image.png_bytes).decode("ascii"),
            "widthCm": safe_image.width_cm,
        }
        for safe_image in (_docx_safe_chart_image(image) for image in images.values())
    ]
