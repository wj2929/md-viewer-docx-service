"""
md-viewer-docx-service · FastAPI 入口

双模式 API：
  模式 B（客户端预渲染）：客户端传 markdown + base64 PNG images → 服务端拼 DOCX
  模式 A（服务端渲染）：客户端传 markdown，服务端自己渲染图表 → 需要 full 镜像
"""
import os
import uuid
import asyncio
import logging
import tempfile
import json
import shutil
import base64
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.generator import generate_docx_from_content
from app.presets import VALID_STYLES, DOCX_PRESETS, STYLE_ORDER, NON_PREVIEW_BLOCK_STYLES
from app.image_injector import preprocess_markdown, inject_images, ImageLayout
from app.chart_renderers import render_charts_and_formulas_sync, rendered_images_to_base64
from app.font_embedder import embed_fonts_if_requested, get_embeddable_font_paths, resolve_reference_docx
from app.bundle_loader import normalize_bundle_path, normalize_bundle_resources
from app.full_fidelity_renderer import render_markdown_full_fidelity
from app.render_runtime import cleanup_output_dir, create_output_dir
from app.renderer_artifact import RendererArtifactError, inspect_renderer_artifact
from app.source_loader import SourceLoadError, load_source_markdown
from app.source_models import ConvertSourceRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VERSION = "0.2.0"
MIN_CLIENT_VERSION = "1.7.0"
KATEX_WIDTH_CM_PER_CSS_PX = 0.018
KATEX_MIN_WIDTH_CM = 2.8
KATEX_MAX_WIDTH_CM = 10.5
CHART_WIDTH_CM_PER_CSS_PX = 0.018
CHART_MIN_WIDTH_CM = 2.8
CHART_MAX_WIDTH_CM = 15.5
DEFAULT_RENDERER_CHART_WIDTH_CM = 15.5

API_KEY = os.environ.get("API_KEY", "")
RATE_LIMIT = os.environ.get("RATE_LIMIT_PER_MIN", "30")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="md-viewer-docx-service", version=VERSION)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _check_api_key(request: Request):
    if not API_KEY:
        return
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _detect_mode() -> str:
    """检测当前镜像能力：slim 或 full"""
    try:
        from playwright.async_api import async_playwright  # noqa: F401
        return "full"
    except ImportError:
        return "slim"


def _get_available_fonts() -> list[str]:
    """检测系统可用的 CJK 字体"""
    import subprocess
    fonts = set()
    target_fonts = [
        "Sarasa Mono SC", "Noto Sans CJK SC", "SimSun", "FangSong",
        "KaiTi", "SimHei", "FZXiaoBiaoSong-B05S", "PingFang SC",
        "Hiragino Sans GB", "Songti SC", "Heiti SC",
    ]
    try:
        result = subprocess.run(
            ["fc-list", "--format=%{family}\n"],
            capture_output=True, text=True, timeout=5
        )
        all_fonts = set(result.stdout.strip().split("\n"))
        for target in target_fonts:
            if any(target.lower() in f.lower() for f in all_fonts):
                fonts.add(target)
    except Exception:
        pass

    for font_path in get_embeddable_font_paths():
        if font_path.parent.name == "fonts" or any(target.lower().replace(" ", "") in font_path.stem.lower() for target in target_fonts):
            fonts.add(font_path.stem)
    return sorted(fonts)


FONT_ALIASES = {
    "微软雅黑": ("Microsoft YaHei", "微软雅黑", "msyh"),
    "方正小标宋简体": ("FZXiaoBiaoSong-B05S", "方正小标宋简体", "FZXiaoBiaoSong"),
    "仿宋_GB2312": ("FangSong", "仿宋_GB2312", "仿宋"),
    "楷体_GB2312": ("KaiTi", "楷体_GB2312", "楷体"),
    "宋体": ("SimSun", "Songti SC", "宋体"),
    "黑体": ("SimHei", "Heiti SC", "黑体"),
}

FONT_FALLBACKS = {
    "微软雅黑": ("Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "NotoSansCJKsc-Regular"),
    "方正小标宋简体": ("Noto Serif CJK SC", "Source Han Serif SC", "Noto Sans CJK SC", "NotoSansCJKsc-Regular"),
    "仿宋_GB2312": ("Noto Serif CJK SC", "Source Han Serif SC", "Noto Sans CJK SC", "NotoSansCJKsc-Regular"),
    "楷体_GB2312": ("Noto Serif CJK SC", "Source Han Serif SC", "Noto Sans CJK SC", "NotoSansCJKsc-Regular"),
    "宋体": ("Noto Serif CJK SC", "Source Han Serif SC", "Noto Sans CJK SC", "NotoSansCJKsc-Regular"),
    "黑体": ("Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "NotoSansCJKsc-Regular"),
}


def _normalize_font_name(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", name).lower()


def _has_font_name(name: str, available: set[str]) -> bool:
    target = _normalize_font_name(name)
    for font in available:
        normalized = _normalize_font_name(font)
        if target == normalized or target in normalized or normalized in target:
            return True
    return False


def _is_embeddable_font_name(name: str, font_paths=None) -> bool:
    target = _normalize_font_name(name)
    paths = font_paths if font_paths is not None else get_embeddable_font_paths()
    for font_path in paths:
        stem = _normalize_font_name(font_path.stem)
        if target == stem or target in stem or stem in target:
            return True
    return False


def _font_status_for_name(name: str, available: set[str], font_paths=None) -> dict:
    aliases = FONT_ALIASES.get(name, (name,))
    for alias in aliases:
        if _has_font_name(alias, available):
            return {
                "status": "exact",
                "resolved": alias,
                "fallback": None,
                "embeddable": _is_embeddable_font_name(alias, font_paths),
            }

    for fallback in FONT_FALLBACKS.get(name, ()):
        if _has_font_name(fallback, available):
            return {
                "status": "fallback",
                "resolved": fallback,
                "fallback": fallback,
                "embeddable": _is_embeddable_font_name(fallback, font_paths),
            }

    return {
        "status": "missing",
        "resolved": None,
        "fallback": None,
        "embeddable": False,
    }


def _font_status_by_style() -> dict[str, dict[str, dict]]:
    available = set(_get_available_fonts())
    font_paths = get_embeddable_font_paths()
    status: dict[str, dict[str, dict]] = {}
    for style in ("standard", "official", "internal", "report"):
        names: list[str] = []
        if style == "standard":
            names.append("微软雅黑")
        else:
            preset = DOCX_PRESETS[style]
            for key in ("title_font", "body_font"):
                value = preset.get(key)
                if value and value != "auto":
                    names.append(value)
            for heading_style in preset.get("heading_styles", {}).values():
                names.append(heading_style.font)

        style_status: dict[str, dict] = {}
        for name in dict.fromkeys(names):
            style_status[name] = _font_status_for_name(name, available, font_paths)
        status[style] = style_status
    return status


FORMAL_STYLES_WITHOUT_DEFAULT_FOOTER = {"official", "internal", "report"}


def _default_footer_for_style(style: str) -> str | None:
    if style in FORMAL_STYLES_WITHOUT_DEFAULT_FOOTER:
        return None
    return "由 MD Viewer 生成"


def _font_warnings_for_style(style: str) -> list[str]:
    if style not in {"official", "internal", "report"}:
        return []

    warnings: list[str] = []
    for font_name, status in _font_status_by_style().get(style, {}).items():
        state = status.get("status")
        if state == "fallback":
            fallback = status.get("fallback") or status.get("resolved") or "可用替代字体"
            warnings.append(f"未检测到 {font_name}，已使用 {fallback} 近似替代，实际显示取决于 Word/WPS 字体环境")
        elif state == "missing":
            warnings.append(f"未检测到 {font_name}，且未找到可用替代字体，实际显示取决于 Word/WPS 字体替换")
    return warnings


def _image_layout_for_style(style: str) -> ImageLayout | None:
    if style == "preview":
        return ImageLayout(
            max_width_cm=DOCX_PRESETS["preview"]["content_width_cm"],
            max_height_cm=14.8,
            margin_cm=0.45,
        )
    block_style = NON_PREVIEW_BLOCK_STYLES.get(style)
    if not block_style:
        return None
    image = block_style.image
    return ImageLayout(
        max_width_cm=image.max_width_cm,
        max_height_cm=image.max_height_cm,
        min_width_cm=image.min_width_cm,
        min_width_source_threshold_cm=image.min_width_source_threshold_cm,
        margin_cm=image.margin_cm,
    )


class ImageItem(BaseModel):
    id: str = Field(..., pattern=r"^mdv__chart__[0-9a-f]{8}__$")
    pngBase64: str = Field(..., max_length=2_800_000)
    widthCm: float = Field(default=15.5, ge=1.0, le=30.0)


class ConvertRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=500_000)
    style: str = Field(default="standard", max_length=20)
    title: Optional[str] = Field(default=None, max_length=200)
    footerText: Optional[str] = Field(default=None, max_length=200)
    images: list[ImageItem] = Field(default_factory=list)
    renderCharts: bool = Field(default=False)
    chartRenderers: list[str] = Field(default_factory=list)
    embedFont: bool = Field(default=False)
    clientVersion: Optional[str] = Field(default=None, max_length=20)
    referenceDocxBase64: Optional[str] = Field(default=None, max_length=20_000_000)

    @model_validator(mode="after")
    def default_footer_by_style(self):
        if "footerText" not in self.model_fields_set:
            self.footerText = _default_footer_for_style(self.style)
        return self


def _model_or_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _render_summary_header(summary) -> str:
    raw = json.dumps(_model_or_dict(summary), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


MERMAID_BLOCK_PATTERN = re.compile(r"^```mermaid\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
EXCALIDRAW_BLOCK_PATTERN = re.compile(r"^```(?:excalidraw|excalidraw-json)\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
EXCALIDRAW_FILE_REF_PATTERN = re.compile(r"!\[[^\]\n]*\]\(\s*[^)\s]+\.excalidraw(?:[?#][^)\s]*)?\s*\)", re.IGNORECASE)
DRAWIO_BLOCK_PATTERN = re.compile(r"^```(?:drawio|dio)\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
ECHARTS_BLOCK_PATTERN = re.compile(r"^```echarts\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
MARKMAP_BLOCK_PATTERN = re.compile(r"^```markmap\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
GRAPHVIZ_BLOCK_PATTERN = re.compile(r"^```(?:graphviz|dot)\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
INFOGRAPHIC_BLOCK_PATTERN = re.compile(r"^```infographic\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
PLANTUML_BLOCK_PATTERN = re.compile(r"^```(?:plantuml|puml)\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
VEGA_LITE_BLOCK_PATTERN = re.compile(r"^```(?:vega-lite|vegalite)\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
D2_BLOCK_PATTERN = re.compile(r"^```d2\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
BPMN_BLOCK_PATTERN = re.compile(r"^```bpmn\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
BPMN_FILE_REF_PATTERN = re.compile(r"!\[[^\]\n]*\]\(\s*[^)\s]+\.bpmn(?:[?#][^)\s]*)?\s*\)", re.IGNORECASE)
WAVEDROM_BLOCK_PATTERN = re.compile(r"^```wavedrom\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
C4PLANTUML_BLOCK_PATTERN = re.compile(r"^```(?:c4|c4plantuml)\b[^\n]*\n[\s\S]*?^```\s*$", re.IGNORECASE | re.MULTILINE)
KATEX_BLOCK_PATTERN = re.compile(r"\$\$\n?([\s\S]*?)\n?\$\$", re.MULTILINE)
KATEX_INLINE_PATTERN = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")
FULL_FIDELITY_FENCE_PATTERN = re.compile(
    r"^```(?P<lang>[\w-]+)\b[^\n]*\n(?P<code>[\s\S]*?)^```\s*$",
    re.IGNORECASE | re.MULTILINE,
)
FULL_FIDELITY_LANGUAGE_TYPES = {
    "mermaid": ("mermaid", "mermaid"),
    "echarts": ("echarts", "echarts"),
    "markmap": ("markmap", "markmap"),
    "graphviz": ("graphviz", "graphviz"),
    "dot": ("graphviz", "graphviz"),
    "drawio": ("drawio", "drawio"),
    "dio": ("drawio", "drawio"),
    "infographic": ("infographic", "infographic"),
    "plantuml": ("plantuml", "plantuml"),
    "puml": ("plantuml", "plantuml"),
    "excalidraw": ("excalidraw", "excalidraw"),
    "excalidraw-json": ("excalidraw", "excalidraw"),
    "vega-lite": ("vega-lite", "vega-lite"),
    "vegalite": ("vega-lite", "vega-lite"),
    "d2": ("d2", "d2"),
    "bpmn": ("bpmn", "bpmn"),
    "wavedrom": ("wavedrom", "wavedrom"),
    "c4": ("c4plantuml", "c4plantuml"),
    "c4plantuml": ("c4plantuml", "c4plantuml"),
}
FULL_FIDELITY_FILE_REF_TYPES = {
    "excalidraw": ("excalidraw", "excalidraw"),
    "bpmn": ("bpmn", "bpmn"),
}

FULL_FIDELITY_IMAGE_TYPES = {
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
}


def _get_field(value, field: str, default=None):
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def _resolve_full_fidelity_width_cm(image) -> float:
    image_type = _get_field(image, "type")
    fallback_width_cm = _get_field(image, "widthCm", 15.5)
    width_px = _get_field(image, "widthPx", 0) or 0
    if width_px <= 0:
        return fallback_width_cm

    if image_type == "katex":
        return min(KATEX_MAX_WIDTH_CM, max(KATEX_MIN_WIDTH_CM, round(width_px * KATEX_WIDTH_CM_PER_CSS_PX, 2)))
    if 0 < fallback_width_cm < DEFAULT_RENDERER_CHART_WIDTH_CM:
        return min(CHART_MAX_WIDTH_CM, max(CHART_MIN_WIDTH_CM, round(fallback_width_cm, 2)))
    if image_type in {"echarts", "drawio", "graphviz"}:
        return CHART_MAX_WIDTH_CM
    return min(CHART_MAX_WIDTH_CM, max(CHART_MIN_WIDTH_CM, round(width_px * CHART_WIDTH_CM_PER_CSS_PX, 2)))


def _full_fidelity_images_to_base64(images) -> list[dict]:
    rendered_images = []
    for image in images:
        png_path = Path(_get_field(image, "pngPath", ""))
        if not png_path.exists():
            continue
        image_type = _get_field(image, "type")
        width_cm = _resolve_full_fidelity_width_cm(image)
        rendered_image = {
            "id": _get_field(image, "id"),
            "type": image_type,
            "pngBase64": base64.b64encode(png_path.read_bytes()).decode("ascii"),
            "widthCm": width_cm,
        }
        source_index = _get_field(image, "sourceIndex")
        if source_index is not None:
            rendered_image["sourceIndex"] = source_index
        block_id = _get_field(image, "blockId")
        if block_id:
            rendered_image["blockId"] = block_id
        rendered_images.append(rendered_image)
    return rendered_images


def _replace_nth_match(pattern: re.Pattern, text: str, replacement: str, index: int) -> str:
    matches = list(pattern.finditer(text))
    if index < 0 or index >= len(matches):
        return text
    match = matches[index]
    return f"{text[:match.start()]}{replacement}{text[match.end():]}"


def _replace_nth_ordered_match(patterns: list[re.Pattern], text: str, replacement: str, index: int) -> str:
    matches = []
    for pattern in patterns:
        matches.extend(pattern.finditer(text))
    matches.sort(key=lambda match: match.start())
    if index < 0 or index >= len(matches):
        return text
    match = matches[index]
    return f"{text[:match.start()]}{replacement}{text[match.end():]}"


def _stable_hash(value: str) -> str:
    hash_value = 0x811C9DC5
    utf16_units = memoryview(value.encode("utf-16-le")).cast("H")
    for code_unit in utf16_units:
        hash_value ^= int(code_unit)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return f"{hash_value:08x}"


def _create_full_fidelity_block_id(
    *,
    renderer_type: str,
    source_kind: str,
    canonical_language: str,
    start_offset: int,
    end_offset: int,
    source: str,
    resolved_path: str | None = None,
) -> tuple[str, str]:
    source_hash = _stable_hash(source)
    identity_parts = [
        renderer_type,
        source_kind,
        canonical_language.strip().lower(),
        str(start_offset),
        str(end_offset),
        source_hash,
        (resolved_path or "").replace("\\", "/"),
    ]
    identity_hash = _stable_hash("\n".join(identity_parts))
    return f"mdv-{renderer_type}-{identity_hash}", source_hash


def _clean_markdown_ref_path(ref_path: str) -> str:
    clean = ref_path.strip().removeprefix("<").removesuffix(">")
    return re.split(r"[?#]", clean.replace("\\", "/"), maxsplit=1)[0] or ref_path


def _is_inside_ranges(index: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in ranges)


def _collect_full_fidelity_source_locators(markdown: str) -> list[dict]:
    candidates: list[dict] = []
    counters: dict[str, int] = {}
    fenced_ranges: list[tuple[int, int]] = []

    for match in FULL_FIDELITY_FENCE_PATTERN.finditer(markdown):
        fenced_ranges.append((match.start(), match.end()))
        raw_language = (match.group("lang") or "").strip().lower()
        resolved = FULL_FIDELITY_LANGUAGE_TYPES.get(raw_language)
        if not resolved:
            continue

        renderer_type, canonical_language = resolved
        source = match.group("code")
        candidates.append({
            "type": renderer_type,
            "sourceKind": "fence",
            "canonicalLanguage": canonical_language,
            "startOffset": match.start(),
            "endOffset": match.end(),
            "source": source,
            "resolvedPath": None,
        })

    for pattern, extension in (
        (EXCALIDRAW_FILE_REF_PATTERN, "excalidraw"),
        (BPMN_FILE_REF_PATTERN, "bpmn"),
    ):
        resolved = FULL_FIDELITY_FILE_REF_TYPES[extension]
        renderer_type, canonical_language = resolved
        for match in pattern.finditer(markdown):
            if _is_inside_ranges(match.start(), fenced_ranges):
                continue
            ref_match = re.search(r"\(\s*(?:<([^>\n]+)>|([^\s)]+))", match.group(0))
            ref_path = (ref_match.group(1) or ref_match.group(2)) if ref_match else ""
            candidates.append({
                "type": renderer_type,
                "sourceKind": "imageRef",
                "canonicalLanguage": canonical_language,
                "startOffset": match.start(),
                "endOffset": match.end(),
                "source": match.group(0),
                "resolvedPath": _clean_markdown_ref_path(ref_path),
            })

    locators: list[dict] = []
    for candidate in sorted(candidates, key=lambda item: item["startOffset"]):
        renderer_type = candidate["type"]
        source_index = counters.get(renderer_type, 0)
        counters[renderer_type] = source_index + 1
        block_id, source_hash = _create_full_fidelity_block_id(
            renderer_type=renderer_type,
            source_kind=candidate["sourceKind"],
            canonical_language=candidate["canonicalLanguage"],
            start_offset=candidate["startOffset"],
            end_offset=candidate["endOffset"],
            source=candidate["source"],
            resolved_path=candidate["resolvedPath"],
        )
        locator = {
            "blockId": block_id,
            "type": renderer_type,
            "sourceKind": candidate["sourceKind"],
            "canonicalLanguage": candidate["canonicalLanguage"],
            "sourceIndex": source_index,
            "startOffset": candidate["startOffset"],
            "endOffset": candidate["endOffset"],
            "sourceHash": source_hash,
        }
        if candidate["resolvedPath"]:
            locator["resolvedPath"] = candidate["resolvedPath"]
        locators.append(locator)

    return locators


def _replace_full_fidelity_chart_blocks(markdown: str, images: list[dict]) -> str:
    result = markdown
    locators_by_block_id = {
        locator["blockId"]: locator
        for locator in _collect_full_fidelity_source_locators(markdown)
    }
    block_id_replacements = []
    block_id_images = set()

    for image in images:
        block_id = image.get("blockId")
        if not isinstance(block_id, str):
            continue
        locator = locators_by_block_id.get(block_id)
        if not locator or locator["type"] != image.get("type"):
            continue
        block_id_images.add(id(image))
        block_id_replacements.append({
            "start": locator["startOffset"],
            "end": locator["endOffset"],
            "value": f"![]({image['id']})",
        })

    for replacement in sorted(block_id_replacements, key=lambda item: item["start"], reverse=True):
        result = f"{result[:replacement['start']]}{replacement['value']}{result[replacement['end']:]}"

    indexed_images = [
        image for image in images
        if id(image) not in block_id_images and isinstance(image.get("sourceIndex"), int)
    ]
    for image in sorted(indexed_images, key=lambda item: item["sourceIndex"], reverse=True):
        image_type = image.get("type")
        if image_type not in FULL_FIDELITY_IMAGE_TYPES:
            continue
        placeholder = f"![]({image['id']})"
        source_index = image["sourceIndex"]
        if image_type == "mermaid":
            result = _replace_nth_match(MERMAID_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "echarts":
            result = _replace_nth_match(ECHARTS_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "markmap":
            result = _replace_nth_match(MARKMAP_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "graphviz":
            result = _replace_nth_match(GRAPHVIZ_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "drawio":
            result = _replace_nth_match(DRAWIO_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "infographic":
            result = _replace_nth_match(INFOGRAPHIC_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "plantuml":
            result = _replace_nth_match(PLANTUML_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "vega-lite":
            result = _replace_nth_match(VEGA_LITE_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "d2":
            result = _replace_nth_match(D2_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "bpmn":
            result = _replace_nth_ordered_match([BPMN_BLOCK_PATTERN, BPMN_FILE_REF_PATTERN], result, placeholder, source_index)
        elif image_type == "wavedrom":
            result = _replace_nth_match(WAVEDROM_BLOCK_PATTERN, result, placeholder, source_index)
        elif image_type == "c4plantuml":
            result = _replace_nth_match(C4PLANTUML_BLOCK_PATTERN, result, placeholder, source_index)

    for image in images:
        if id(image) in block_id_images:
            continue
        if isinstance(image.get("sourceIndex"), int):
            continue
        image_type = image.get("type")
        if image_type not in FULL_FIDELITY_IMAGE_TYPES:
            continue
        placeholder = f"![]({image['id']})"
        if image_type == "mermaid":
            result, _ = MERMAID_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "echarts":
            result, _ = ECHARTS_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "markmap":
            result, _ = MARKMAP_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "graphviz":
            result, _ = GRAPHVIZ_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "drawio":
            result, _ = DRAWIO_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "infographic":
            result, _ = INFOGRAPHIC_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "plantuml":
            result, _ = PLANTUML_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "excalidraw":
            result, replaced = EXCALIDRAW_BLOCK_PATTERN.subn(placeholder, result, count=1)
            if replaced == 0:
                result, _ = EXCALIDRAW_FILE_REF_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "vega-lite":
            result, _ = VEGA_LITE_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "d2":
            result, _ = D2_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "bpmn":
            result = _replace_nth_ordered_match([BPMN_BLOCK_PATTERN, BPMN_FILE_REF_PATTERN], result, placeholder, 0)
        elif image_type == "wavedrom":
            result, _ = WAVEDROM_BLOCK_PATTERN.subn(placeholder, result, count=1)
        elif image_type == "c4plantuml":
            result, _ = C4PLANTUML_BLOCK_PATTERN.subn(placeholder, result, count=1)
        else:
            result, replaced = KATEX_BLOCK_PATTERN.subn(placeholder, result, count=1)
            if replaced == 0:
                result, _ = KATEX_INLINE_PATTERN.subn(f"\n\n{placeholder}\n\n", result, count=1)
    return result


@app.get("/healthz")
async def healthz():
    mode = _detect_mode()
    chart_renderers = []
    if mode == "full":
        chart_renderers = ["mermaid", "echarts", "markmap", "plantuml"]
        if shutil.which("dot"):
            chart_renderers.append("dot")
    else:
        if shutil.which("dot"):
            chart_renderers = ["dot"]

    return {
        "status": "ok",
        "version": VERSION,
        "mode": mode,
        "styles": list(STYLE_ORDER),
        "fontsAvailable": _get_available_fonts(),
        "fontStatus": _font_status_by_style(),
        "embedFontSupported": bool(get_embeddable_font_paths()),
        "chartRenderersAvailable": chart_renderers,
        "minClientVersion": MIN_CLIENT_VERSION,
        "maxImagesPerRequest": None,
        "maxRequestSizeMb": 30,
    }


@app.get("/readyz")
async def readyz():
    artifact_dir = Path(os.environ.get("MDV_RENDER_ARTIFACT_DIR", "/app/renderers/dist/server-render"))
    common = {
        "renderConcurrency": int(os.environ.get("MDV_RENDER_CONCURRENCY", "1")),
        "sourceUrlPolicy": os.environ.get("MDV_SOURCE_URL_POLICY", "local-friendly"),
        "renderNetworkPolicy": os.environ.get("MDV_RENDER_NETWORK_POLICY", "local-friendly"),
    }

    try:
        info = inspect_renderer_artifact(artifact_dir, service_version=VERSION)
    except RendererArtifactError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "fullFidelityRenderSupported": False,
                "rendererHealth": "missing",
                "rendererError": str(exc),
                **common,
            },
        )

    return {
        "fullFidelityRenderSupported": True,
        "rendererHealth": "ok",
        "rendererArtifactVersion": info.version,
        "rendererSchemaVersion": info.schemaVersion,
        "rendererSupportedCharts": info.supportedCharts,
        "rendererWarnings": info.rendererWarnings,
        **common,
    }


@app.post("/convert")
@limiter.limit(f"{RATE_LIMIT}/minute")
async def convert(req: ConvertRequest, request: Request):
    _check_api_key(request)

    if req.style not in VALID_STYLES:
        raise HTTPException(400, detail={"error": f"Invalid style: {req.style}", "code": "STYLE_INVALID"})

    mode_used = "clientRendered"
    charts_rendered = 0
    charts_failed = 0
    warnings: list[str] = _font_warnings_for_style(req.style)

    md = req.markdown
    image_map = {}
    reference_docx_path, reference_warnings = resolve_reference_docx(req.referenceDocxBase64)
    warnings.extend(reference_warnings)

    if req.images:
        chart_result = await asyncio.to_thread(render_charts_and_formulas_sync, md, req.chartRenderers or None)
        md = chart_result.markdown
        rendered_images = rendered_images_to_base64(chart_result.images)
        warnings.extend(chart_result.warnings)
        md, image_map = preprocess_markdown(md, [img.model_dump() for img in req.images] + rendered_images)
        req_image_ids = {img.id for img in req.images}
        accepted_req_images = sum(1 for image_id in req_image_ids if image_id in image_map)
        skipped = len(req.images) - accepted_req_images
        if skipped > 0:
            warnings.append(f"{skipped} images failed validation")
            charts_failed = skipped
        charts_rendered = len(image_map)

    elif req.renderCharts:
        current_mode = _detect_mode()
        if current_mode != "full":
            raise HTTPException(400, detail={
                "error": "Server-side chart rendering requires full image (with playwright)",
                "code": "RENDER_UNAVAILABLE",
            })
        mode_used = "serverRendered"
        chart_result = await asyncio.to_thread(render_charts_and_formulas_sync, md, req.chartRenderers or None)
        md = chart_result.markdown
        warnings.extend(chart_result.warnings)
        rendered_images = rendered_images_to_base64(chart_result.images)
        _, image_map = preprocess_markdown(md, rendered_images)
        charts_rendered = len(image_map)

    else:
        chart_result = await asyncio.to_thread(render_charts_and_formulas_sync, md, [])
        md = chart_result.markdown
        warnings.extend(chart_result.warnings)
        rendered_images = rendered_images_to_base64(chart_result.images)
        _, image_map = preprocess_markdown(md, rendered_images)
        charts_rendered = len(image_map)

    tmp_dir = tempfile.mkdtemp(prefix="mdv-docx-")
    tmp_path = os.path.join(tmp_dir, f"output-{uuid.uuid4().hex[:8]}.docx")

    try:
        await asyncio.to_thread(
            generate_docx_from_content,
            md,
            tmp_path,
            style=req.style,
            title=req.title,
            footer_text=req.footerText,
            references=None,
            reference_docx_path=reference_docx_path,
        )

        if image_map:
            injected = await asyncio.to_thread(
                inject_images,
                tmp_path,
                image_map,
                req.style,
                _image_layout_for_style(req.style),
            )
            logger.info(f"[Convert] Injected {injected} images into DOCX")

        font_warnings = await asyncio.to_thread(embed_fonts_if_requested, tmp_path, req.embedFont)
        warnings.extend(font_warnings)

        headers = {
            "X-Service-Version": VERSION,
            "X-Service-Mode": mode_used,
            "X-Convert-Warnings": json.dumps(warnings, ensure_ascii=True),
            "X-Charts-Rendered": str(charts_rendered),
            "X-Charts-Failed": str(charts_failed),
            "X-Min-Client-Version": MIN_CLIENT_VERSION,
            "Content-Disposition": f'attachment; filename="export.docx"',
        }

        return FileResponse(
            tmp_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
            background=None,
        )

    except Exception as e:
        logger.error(f"[Convert] Failed: {e}", exc_info=True)
        raise HTTPException(500, detail={"error": str(e)[:500], "code": "INTERNAL"})


@app.post("/convert-source")
@limiter.limit(f"{RATE_LIMIT}/minute")
async def convert_source(req: ConvertSourceRequest, request: Request):
    _check_api_key(request)

    if req.style not in VALID_STYLES:
        raise HTTPException(400, detail={"error": f"Invalid style: {req.style}", "code": "STYLE_INVALID"})

    render_output_dir = create_output_dir()
    try:
        source_markdown = await asyncio.to_thread(load_source_markdown, req)
        source_resources = normalize_bundle_resources(req.resources) if req.sourceType == "bundle" else []
        markdown_file_path = normalize_bundle_path(req.entryPath) if req.sourceType == "bundle" and req.entryPath else None
        renderer_cli = os.environ.get("MDV_RENDER_CLI", "/app/renderers/mdv-renderer-cli.mjs")
        render_result = await asyncio.to_thread(
            render_markdown_full_fidelity,
            markdown=source_markdown,
            renderer_cli=["node", renderer_cli],
            output_dir=render_output_dir,
            resources=source_resources,
            markdown_file_path=markdown_file_path,
            timeout_ms=int(os.environ.get("MDV_RENDER_TIMEOUT_MS", "60000")),
        )

        if req.fallbackMode == "fail" and render_result.status != "success":
            raise HTTPException(502, detail={
                "error": "full fidelity renderer did not complete successfully",
                "code": "RENDER_FAILED",
                "status": render_result.status,
            })

        reference_docx_path, reference_warnings = resolve_reference_docx(req.referenceDocxBase64)
        tmp_dir = tempfile.mkdtemp(prefix="mdv-docx-source-")
        tmp_path = os.path.join(tmp_dir, f"output-{uuid.uuid4().hex[:8]}.docx")

        rendered_images = _full_fidelity_images_to_base64(render_result.images)
        md = _replace_full_fidelity_chart_blocks(source_markdown, rendered_images)

        plantuml_result = await asyncio.to_thread(render_charts_and_formulas_sync, md, ["plantuml"])
        md = plantuml_result.markdown
        rendered_images.extend(rendered_images_to_base64(plantuml_result.images))
        md, image_map = preprocess_markdown(md, rendered_images)

        await asyncio.to_thread(
            generate_docx_from_content,
            md,
            tmp_path,
            style=req.style,
            title=None,
            footer_text=req.footerText,
            references=None,
            reference_docx_path=reference_docx_path,
        )

        charts_rendered = 0
        if image_map:
            charts_rendered = await asyncio.to_thread(
                inject_images,
                tmp_path,
                image_map,
                req.style,
                _image_layout_for_style(req.style),
            )

        font_warnings = await asyncio.to_thread(embed_fonts_if_requested, tmp_path, req.embedFont)
        warnings = (
            _font_warnings_for_style(req.style)
            + reference_warnings
            + font_warnings
            + plantuml_result.warnings
        )

        failed_blocks = _model_or_dict(render_result.stats).get("failedBlocks", 0)
        headers = {
            "X-Service-Version": VERSION,
            "X-Service-Mode": "fullFidelity",
            "X-Render-Status": render_result.status,
            "X-Render-Warning-Count": str(len(render_result.warnings) + len(warnings)),
            "X-Convert-Warnings": json.dumps(warnings, ensure_ascii=True),
            "X-Render-Failed-Blocks": str(failed_blocks),
            "X-Charts-Rendered": str(charts_rendered),
            "X-Render-Summary-Base64": _render_summary_header(render_result.renderSummary),
            "X-Min-Client-Version": MIN_CLIENT_VERSION,
            "Content-Disposition": 'attachment; filename="export.docx"',
        }

        return FileResponse(
            tmp_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
            background=None,
        )
    except HTTPException:
        raise
    except SourceLoadError as e:
        raise HTTPException(400, detail={"error": str(e)[:500], "code": "SOURCE_LOAD_FAILED"})
    except Exception as e:
        logger.error(f"[ConvertSource] Failed: {e}", exc_info=True)
        raise HTTPException(500, detail={"error": str(e)[:500], "code": "INTERNAL"})
    finally:
        cleanup_output_dir(render_output_dir)
