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
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.generator import generate_docx_from_content, VALID_STYLES, DOCX_PRESETS
from app.image_injector import preprocess_markdown, inject_images

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VERSION = "0.1.0"
MIN_CLIENT_VERSION = "1.7.0"

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
    fonts = []
    try:
        result = subprocess.run(
            ["fc-list", "--format=%{family}\n"],
            capture_output=True, text=True, timeout=5
        )
        all_fonts = set(result.stdout.strip().split("\n"))
        for target in ["Sarasa Mono SC", "Noto Sans CJK SC", "SimSun", "FangSong",
                        "KaiTi", "SimHei", "FZXiaoBiaoSong-B05S"]:
            if any(target.lower() in f.lower() for f in all_fonts):
                fonts.append(target)
    except Exception:
        pass
    return fonts


class ImageItem(BaseModel):
    id: str = Field(..., pattern=r"^mdv__chart__[0-9a-f]{8}__$")
    pngBase64: str = Field(..., max_length=2_800_000)
    widthCm: float = Field(default=15.5, ge=1.0, le=30.0)


class ConvertRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=500_000)
    style: str = Field(default="standard", pattern=r"^(standard|official|internal|report)$")
    title: Optional[str] = Field(default=None, max_length=200)
    footerText: Optional[str] = Field(default="由 MD Viewer 生成", max_length=200)
    images: list[ImageItem] = Field(default_factory=list, max_length=50)
    renderCharts: bool = Field(default=False)
    chartRenderers: list[str] = Field(default_factory=list)
    embedFont: bool = Field(default=False)
    clientVersion: Optional[str] = Field(default=None, max_length=20)


@app.get("/healthz")
async def healthz():
    mode = _detect_mode()
    chart_renderers = []
    if mode == "full":
        chart_renderers = ["mermaid", "echarts", "dot", "markmap", "plantuml"]
    else:
        chart_renderers = ["dot"]

    return {
        "status": "ok",
        "version": VERSION,
        "mode": mode,
        "styles": list(DOCX_PRESETS.keys()) + ["standard"],
        "fontsAvailable": _get_available_fonts(),
        "embedFontSupported": False,
        "chartRenderersAvailable": chart_renderers,
        "minClientVersion": MIN_CLIENT_VERSION,
        "maxImagesPerRequest": 50,
        "maxRequestSizeMb": 30,
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
    warnings: list[str] = []

    md = req.markdown
    image_map = {}

    if req.images:
        md, image_map = preprocess_markdown(md, [img.model_dump() for img in req.images])
        skipped = len(req.images) - len(image_map)
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
        # TODO: 阶段 2 实现服务端图表渲染（playwright + mermaid-cli 等）
        warnings.append("Server-side chart rendering not yet implemented")

    tmp_dir = tempfile.mkdtemp(prefix="mdv-docx-")
    tmp_path = os.path.join(tmp_dir, f"output-{uuid.uuid4().hex[:8]}.docx")

    try:
        await asyncio.to_thread(
            generate_docx_from_content,
            md,
            tmp_path,
            style=req.style,
            title=req.title,
            footer_text=req.footerText or "由 MD Viewer 生成",
            references=None,
        )

        if image_map:
            injected = await asyncio.to_thread(inject_images, tmp_path, image_map)
            logger.info(f"[Convert] Injected {injected} images into DOCX")

        headers = {
            "X-Service-Version": VERSION,
            "X-Service-Mode": mode_used,
            "X-Convert-Warnings": str(warnings),
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
