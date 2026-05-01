"""
图片占位符注入模块

将 markdown 中的 ![](mdv__chart__xxxxxxxx__) 占位符替换为实际图片。
在 python-docx 生成 DOCX 后，扫描段落找到占位符文本，替换为 InlineImage。
"""
import re
import base64
import io
import logging
from typing import Dict, Optional
from docx import Document
from docx.shared import Cm
from PIL import Image

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"^!\[\]\((mdv__chart__[0-9a-f]{8}__)\)$")
IMAGE_MAX_PIXELS = 20_000_000
IMAGE_MAX_B64_LEN = 2_800_000
PREVIEW_IMAGE_MARGIN_CM = 0.45
DEFAULT_IMAGE_MARGIN_CM = 0.3

class ImageData:
    __slots__ = ("id", "png_bytes", "width_cm")

    def __init__(self, id: str, png_base64: str, width_cm: float = 15.5):
        self.id = id
        if len(png_base64) > IMAGE_MAX_B64_LEN:
            raise ValueError(f"Image {id}: base64 exceeds {IMAGE_MAX_B64_LEN} chars")
        self.png_bytes = base64.b64decode(png_base64)
        self.width_cm = width_cm

        img = Image.open(io.BytesIO(self.png_bytes))
        img.verify()
        w, h = img.size
        if w * h > IMAGE_MAX_PIXELS:
            raise ValueError(f"Image {id}: {w}x{h} = {w*h} pixels exceeds limit {IMAGE_MAX_PIXELS}")


def resolve_image_width_cm(width_cm: float, style: str = "standard") -> float:
    """根据导出样式解析图片插入宽度。"""
    if style != "preview":
        return width_cm
    if width_cm < 18.0:
        return 18.5
    return min(width_cm, 19.0)


def preprocess_markdown(md: str, images: list[dict]) -> tuple[str, Dict[str, ImageData]]:
    """预处理 markdown：验证图片数据，构建 id→ImageData 映射。

    不修改 markdown 文本——占位符由客户端已经写入。
    返回 (原始 md, {id: ImageData})
    """
    image_map: Dict[str, ImageData] = {}
    for img in images:
        try:
            data = ImageData(
                id=img["id"],
                png_base64=img["pngBase64"],
                width_cm=img.get("widthCm", 15.5),
            )
            image_map[data.id] = data
        except Exception as e:
            logger.warning(f"[ImageInjector] Skipping image {img.get('id', '?')}: {e}")

    return md, image_map


def inject_images(doc_path: str, image_map: Dict[str, ImageData], style: str = "standard") -> int:
    """在生成好的 DOCX 中，把占位符段落替换为图片。

    扫描所有段落，找到 ![](mdv__chart__xxx__) 格式的文本，替换为图片。
    返回成功注入的图片数量。
    """
    if not image_map:
        return 0

    doc = Document(doc_path)
    injected = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        m = PLACEHOLDER_PATTERN.match(text)
        if not m:
            continue

        placeholder_id = m.group(1)
        if placeholder_id not in image_map:
            logger.warning(f"[ImageInjector] Placeholder {placeholder_id} not found in image_map")
            continue

        img_data = image_map[placeholder_id]

        for run in para.runs:
            run.clear()

        run = para.add_run()
        run.add_picture(io.BytesIO(img_data.png_bytes), width=Cm(resolve_image_width_cm(img_data.width_cm, style)))
        injected += 1

        # 清除图片段落的固定行距和首行缩进（公文等样式的固定行距会压扁图片）
        pf = para.paragraph_format
        pf.line_spacing = None
        pf.line_spacing_rule = None
        pf.first_line_indent = None
        margin_cm = PREVIEW_IMAGE_MARGIN_CM if style == "preview" else DEFAULT_IMAGE_MARGIN_CM
        pf.space_before = Cm(margin_cm)
        pf.space_after = Cm(margin_cm)

        logger.info(f"[ImageInjector] Injected {placeholder_id} ({len(img_data.png_bytes)} bytes)")

    doc.save(doc_path)
    return injected
