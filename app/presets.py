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


@dataclass(frozen=True)
class TableStyleDef:
    """非 preview 表格块级样式定义"""
    content_width_cm: float
    alignment: str = "center"
    adaptive_width: bool = False
    header_fill: str = ""
    border_color: str = "D0D7DE"
    border_size: str = "4"
    header_font_size: float = 9.5
    body_font_size: float = 9.5
    cell_margin_top: int = 70
    cell_margin_start: int = 120
    cell_margin_bottom: int = 70
    cell_margin_end: int = 120
    line_spacing: float = 1.0
    gap_after_pt: float = 4.0


@dataclass(frozen=True)
class CalloutStyleDef:
    """非 preview 引用/提示块级样式定义"""
    mode: str
    fill: str = ""
    font_size_delta: float = -0.5
    note_prefix: str = "注："


@dataclass(frozen=True)
class CodeStyleDef:
    """非 preview 代码块样式定义"""
    font_size: float = 9.0
    fill: str = "F5F5F5"
    line_spacing: float = 1.0


@dataclass(frozen=True)
class ImageStyleDef:
    """非 preview 图片布局样式定义"""
    max_width_cm: float
    max_height_cm: float = 14.8
    min_width_cm: float = 0.0
    min_width_source_threshold_cm: float = 0.0
    margin_cm: float = 0.3


@dataclass(frozen=True)
class BlockStyleDef:
    """非 preview 块级样式定义"""
    table: TableStyleDef
    callout: CalloutStyleDef
    code: CodeStyleDef
    image: ImageStyleDef


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
        "first_line_indent_chars": 2,
        "align": "justify",
    },
    # ── 机关内部文件 ──
    # ## = 一级标题 → 黑体, ### = 二级标题 → 宋体加粗
    "internal": {
        "display_name": "机关内部文件",
        "page_margins": {"top": 2.3, "bottom": 2.3, "left": 2.54, "right": 2.54},
        "title_font": "黑体", "title_size": 18,
        "heading_styles": {
            1: HeadingStyleDef("黑体", 18),                    # # 文档标题（兜底）
            2: HeadingStyleDef("黑体", 15),                    # ## 一级标题
            3: HeadingStyleDef("宋体", 15, bold=True),         # ### 二级标题
            4: HeadingStyleDef("宋体", 15, bold=True),         # #### 三级标题
        },
        "body_font": "宋体", "body_size": 15,
        "line_spacing_multiple": 1.35,
        "first_line_indent_chars": 2,
        "align": "justify",
    },
    # ── 调研/分析报告 ──
    # ## = 一级标题 → 黑体, ### = 二级标题 → 宋体加粗
    "report": {
        "display_name": "调研/分析报告",
        "page_margins": {"top": 2.2, "bottom": 2.2, "left": 2.54, "right": 2.54},
        "title_font": "黑体", "title_size": 16,
        "heading_styles": {
            1: HeadingStyleDef("黑体", 16),                    # # 文档标题（兜底）
            2: HeadingStyleDef("黑体", 14),                    # ## 一级标题
            3: HeadingStyleDef("宋体", 12, bold=True),         # ### 二级标题
            4: HeadingStyleDef("宋体", 12, bold=True),         # #### 三级标题
        },
        "body_font": "宋体", "body_size": 12,
        "line_spacing_multiple": 1.3,
        "first_line_indent_chars": 2,
        "align": "justify",
    },
}

NON_PREVIEW_BLOCK_STYLES = {
    "standard": BlockStyleDef(
        table=TableStyleDef(
            content_width_cm=15.5,
            adaptive_width=True,
            header_fill="F6F8FA",
            border_color="D0D7DE",
            header_font_size=9.5,
            body_font_size=9.5,
        ),
        callout=CalloutStyleDef(mode="box", fill="F6F8FA"),
        code=CodeStyleDef(font_size=9.0, fill="F5F5F5"),
        image=ImageStyleDef(max_width_cm=15.5, max_height_cm=14.8, margin_cm=0.3),
    ),
    "official": BlockStyleDef(
        table=TableStyleDef(
            content_width_cm=15.2,
            adaptive_width=False,
            header_fill="",
            border_color="666666",
            header_font_size=9.5,
            body_font_size=9.5,
            cell_margin_top=45,
            cell_margin_start=100,
            cell_margin_bottom=45,
            cell_margin_end=100,
            gap_after_pt=2.0,
        ),
        callout=CalloutStyleDef(mode="official"),
        code=CodeStyleDef(font_size=9.0, fill="FAFAFA"),
        image=ImageStyleDef(max_width_cm=14.8, max_height_cm=14.8, margin_cm=0.25),
    ),
    "internal": BlockStyleDef(
        table=TableStyleDef(
            content_width_cm=15.5,
            adaptive_width=True,
            header_fill="F2F3F5",
            border_color="BFC5CC",
            header_font_size=10.0,
            body_font_size=10.0,
            gap_after_pt=3.0,
        ),
        callout=CalloutStyleDef(mode="box", fill="F5F6F7"),
        code=CodeStyleDef(font_size=9.0, fill="F5F5F5"),
        image=ImageStyleDef(max_width_cm=15.5, max_height_cm=14.8, margin_cm=0.25),
    ),
    "report": BlockStyleDef(
        table=TableStyleDef(
            content_width_cm=15.8,
            adaptive_width=True,
            header_fill="F3F4F6",
            border_color="CBD5E1",
            header_font_size=9.5,
            body_font_size=9.5,
            gap_after_pt=3.0,
        ),
        callout=CalloutStyleDef(mode="box", fill="F6F8FA"),
        code=CodeStyleDef(font_size=9.0, fill="F6F8FA"),
        image=ImageStyleDef(
            max_width_cm=15.8,
            max_height_cm=14.8,
            min_width_cm=15.0,
            min_width_source_threshold_cm=8.0,
            margin_cm=0.28,
        ),
    ),
}

VALID_STYLES = frozenset(STYLE_ORDER)
