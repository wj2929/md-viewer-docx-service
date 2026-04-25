import base64
import io
import pytest
from PIL import Image


@pytest.fixture
def sample_markdown():
    return "# 测试标题\n\n这是一段正文。\n\n## 二级标题\n\n- 列表项 1\n- 列表项 2\n\n| A | B |\n|---|---|\n| 1 | 2 |"


@pytest.fixture
def minimal_png_base64():
    """1x1 红色 PNG 的 base64"""
    buf = io.BytesIO()
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def small_png_base64():
    """100x100 蓝色 PNG 的 base64"""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(0, 0, 255))
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
