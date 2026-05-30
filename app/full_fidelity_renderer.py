import json
import os
import re
import subprocess
from pathlib import Path
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, Field

from app.render_runtime import assert_output_path_inside


class RenderedImage(BaseModel):
    id: str
    type: Literal[
        "mermaid",
        "katex",
        "echarts",
        "markmap",
        "graphviz",
        "excalidraw",
        "drawio",
        "infographic",
        "plantuml",
        "vega-lite",
        "d2",
        "bpmn",
        "wavedrom",
        "c4plantuml",
    ]
    pngPath: str
    widthPx: int = Field(..., ge=1)
    heightPx: int = Field(..., ge=1)
    widthCm: float = Field(..., gt=0)
    durationMs: int = Field(default=0, ge=0)
    sourceIndex: Optional[int] = Field(default=None, ge=0)
    blockId: Optional[str] = None


class RenderStats(BaseModel):
    totalBlocks: int = Field(default=0, ge=0)
    renderedBlocks: int = Field(default=0, ge=0)
    failedBlocks: int = Field(default=0, ge=0)
    durationMs: int = Field(default=0, ge=0)


class RenderSummary(BaseModel):
    totalBlocks: int = Field(default=0, ge=0)
    renderedBlocks: int = Field(default=0, ge=0)
    failedBlocks: int = Field(default=0, ge=0)
    warningCount: int = Field(default=0, ge=0)
    statusText: str


class RenderWarning(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    title: str
    message: str
    recoverable: bool = True


class FullFidelityRenderResult(BaseModel):
    schemaVersion: Literal["1.0"]
    ok: bool
    status: Literal["success", "partial", "failed", "timeout"]
    htmlPath: str
    images: list[RenderedImage] = Field(default_factory=list)
    warnings: list[RenderWarning] = Field(default_factory=list)
    stats: RenderStats
    renderSummary: RenderSummary


SUPPORTED_BLOCK_RE = re.compile(
    r"^```(?:mermaid|echarts|markmap|graphviz|dot|excalidraw|excalidraw-json|drawio|dio|infographic|vega-lite|vegalite|d2|bpmn|wavedrom|c4|c4plantuml)\b[^\n]*\n[\s\S]*?^```\s*$",
    re.IGNORECASE | re.MULTILINE,
)
EXCALIDRAW_REF_RE = re.compile(r"!\[[^\]\n]*\]\(\s*[^)\s]+\.excalidraw(?:[?#][^)\s]*)?\s*\)", re.IGNORECASE)
BPMN_REF_RE = re.compile(r"!\[[^\]\n]*\]\(\s*[^)\s]+\.bpmn(?:[?#][^)\s]*)?\s*\)", re.IGNORECASE)
BLOCK_MATH_RE = re.compile(r"\$\$\n?[\s\S]*?\n?\$\$", re.MULTILINE)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")


def _count_supported_blocks(markdown: str) -> int:
    without_fences = SUPPORTED_BLOCK_RE.sub("", markdown)
    without_block_math = BLOCK_MATH_RE.sub("", without_fences)
    return (
        len(SUPPORTED_BLOCK_RE.findall(markdown))
        + len(EXCALIDRAW_REF_RE.findall(markdown))
        + len(BPMN_REF_RE.findall(markdown))
        + len(BLOCK_MATH_RE.findall(without_fences))
        + len(INLINE_MATH_RE.findall(without_block_math))
    )


def _timeout_result(output_dir: Path, markdown: str, message: str) -> FullFidelityRenderResult:
    html_path = output_dir / "rendered.html"
    html_path.write_text("", encoding="utf-8")
    total_blocks = _count_supported_blocks(markdown)
    return FullFidelityRenderResult(
        schemaVersion="1.0",
        ok=False,
        status="timeout",
        htmlPath=str(html_path),
        images=[],
        warnings=[RenderWarning(
            code="RENDER_TIMEOUT",
            severity="warning",
            title="渲染超时",
            message=message,
            recoverable=True,
        )],
        stats=RenderStats(
            totalBlocks=total_blocks,
            renderedBlocks=0,
            failedBlocks=total_blocks,
            durationMs=0,
        ),
        renderSummary=RenderSummary(
            totalBlocks=total_blocks,
            renderedBlocks=0,
            failedBlocks=total_blocks,
            warningCount=1,
            statusText="renderer cli timed out",
        ),
    )


def render_markdown_full_fidelity(
    *,
    markdown: str,
    renderer_cli: Sequence[str],
    output_dir: Path,
    resources: Optional[list[dict]] = None,
    markdown_file_path: Optional[str] = None,
    timeout_ms: Optional[int] = None,
) -> FullFidelityRenderResult:
    output_dir = output_dir.resolve()
    total_timeout_ms = timeout_ms or int(os.environ.get("MDV_RENDER_TIMEOUT_MS", "60000"))
    grace_ms = int(os.environ.get("MDV_RENDER_CLI_GRACE_MS", str(max(15000, total_timeout_ms))))
    timeout = (total_timeout_ms + grace_ms) / 1000
    page_timeout_ms = max(1000, total_timeout_ms - 5000)
    payload = {
        "schemaVersion": "1.0",
        "markdown": markdown,
        "markdownFilePath": markdown_file_path,
        "resources": resources or [],
        "theme": "light",
        "enabledRenderers": [
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
        ],
        "networkPolicy": os.environ.get("MDV_RENDER_NETWORK_POLICY", "local-friendly"),
        "allowlistHosts": [
            host.strip()
            for host in os.environ.get("MDV_RENDER_ALLOWLIST_HOSTS", "").split(",")
            if host.strip()
        ],
        "outputDir": str(output_dir),
        "timeoutMs": page_timeout_ms,
    }

    try:
        completed = subprocess.run(
            list(renderer_cli),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _timeout_result(output_dir, markdown, str(exc))

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()[:2000]
        raise RuntimeError(f"renderer cli failed: {stderr}")

    result = FullFidelityRenderResult.model_validate_json(completed.stdout)
    assert_output_path_inside(output_dir, Path(result.htmlPath))
    for image in result.images:
        assert_output_path_inside(output_dir, Path(image.pngPath))
    return result
