"""
DOCX 排版预设定义

零依赖纯数据模块：只使用 Python 内置类型和 dataclasses，
不引用 docx / generator 等外部模块，避免循环导入。
"""
from dataclasses import dataclass


@dataclass
class HeadingStyleDef:
    """标题层级样式定义"""
    font: str
    size: int       # pt
    bold: bool = False


STYLE_ORDER = ("preview", "standard", "official", "internal", "report")


DOCX_PRESETS = {
    # ── 预览一致：接近 Markdown 预览 / PDF 导出的紧凑排版 ──
    "preview": {
        "display_name": "预览一致",
        "page_margins": {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
        "title_font": "auto", "title_size": 18,
        "body_font": "auto", "body_size": 10,
        "mono_font": "auto",
        "line_spacing_multiple": 1.45,
        "first_line_indent": 0,
        "align": "left",
        "content_width_cm": 19.0,
    },
    # ── 正式公文：GB/T 9704-2012 严格版，四级标题体系 ──
    # heading_styles 按 markdown heading level 映射（# 已被 title_font 单独处理）
    # ## = 公文一级标题（一、）→ 黑体
    # ### = 公文二级标题（（一））→ 楷体_GB2312 加粗
    # #### = 公文三级标题（1.）→ 仿宋_GB2312 加粗
    # H5 = 公文四级标题（（1））→ 仿宋_GB2312 加粗
    "official": {
        "display_name": "正式公文",
        "page_margins": {"top": 3.7, "bottom": 3.5, "left": 2.8, "right": 2.6},
        "title_font": "方正小标宋简体", "title_size": 22,
        "heading_styles": {
            1: HeadingStyleDef("方正小标宋简体", 22),          # # 文档标题（与 title_font 一致，兜底）
            2: HeadingStyleDef("黑体", 16),                   # ## 一、公文一级标题
            3: HeadingStyleDef("楷体_GB2312", 16, bold=True), # ### （一）公文二级标题
            4: HeadingStyleDef("仿宋_GB2312", 16, bold=True), # #### 1. 公文三级标题
        },
        "body_font": "仿宋_GB2312", "body_size": 16,
        "line_spacing": 28,
        "first_line_indent": 0.74,
        "align": "justify",
    },
    # ── 机关内部文件 ──
    # ## = 一级标题 → 黑体, ### = 二级标题 → 宋体加粗
    "internal": {
        "display_name": "机关内部文件",
        "page_margins": {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17},
        "title_font": "黑体", "title_size": 18,
        "heading_styles": {
            1: HeadingStyleDef("黑体", 18),                    # # 文档标题（兜底）
            2: HeadingStyleDef("黑体", 15),                    # ## 一级标题
            3: HeadingStyleDef("宋体", 15, bold=True),         # ### 二级标题
            4: HeadingStyleDef("宋体", 15, bold=True),         # #### 三级标题
        },
        "body_font": "宋体", "body_size": 15,
        "line_spacing_multiple": 1.5,
        "first_line_indent": 0.74,
        "align": "justify",
    },
    # ── 调研/分析报告 ──
    # ## = 一级标题 → 黑体, ### = 二级标题 → 宋体加粗
    "report": {
        "display_name": "调研/分析报告",
        "page_margins": {"top": 2.54, "bottom": 2.54, "left": 3.17, "right": 3.17},
        "title_font": "黑体", "title_size": 16,
        "heading_styles": {
            1: HeadingStyleDef("黑体", 16),                    # # 文档标题（兜底）
            2: HeadingStyleDef("黑体", 14),                    # ## 一级标题
            3: HeadingStyleDef("宋体", 12, bold=True),         # ### 二级标题
            4: HeadingStyleDef("宋体", 12, bold=True),         # #### 三级标题
        },
        "body_font": "宋体", "body_size": 12,
        "line_spacing_multiple": 1.5,
        "first_line_indent": 0.56,
        "align": "justify",
    },
}

VALID_STYLES = frozenset(STYLE_ORDER)
