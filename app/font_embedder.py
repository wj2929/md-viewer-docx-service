"""
DOCX 字体嵌入。

Word 字体嵌入涉及字体授权位和多个 OOXML 关系文件。这里采用保守策略：
只在找到明确字体文件时把字体写入 word/fonts/，并记录关系；任何异常都
返回 warning，保证 DOCX 仍可打开。
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
SERVICE_ROOT = Path(__file__).resolve().parent.parent
ENV_FONT_PATHS = "MD_VIEWER_DOCX_FONT_PATHS"
ENV_FONT_DIRS = "MD_VIEWER_DOCX_FONT_DIRS"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FONT_ATTRS = tuple(f"{{{WORD_NS}}}{name}" for name in ("ascii", "hAnsi", "eastAsia", "cs"))
STYLE_SUFFIXES = (
    "regular", "bold", "italic", "bolditalic", "medium", "light",
    "semibold", "demibold", "black", "thin",
)

DEFAULT_FONT_CANDIDATES = [
    str(SERVICE_ROOT / "fonts" / "sarasa-mono-sc.ttc"),
    str(SERVICE_ROOT / "fonts" / "SarasaMonoSC-Regular.ttf"),
    str(SERVICE_ROOT / "fonts" / "NotoSansCJKsc-Regular.otf"),
    str(SERVICE_ROOT / "fonts" / "NotoSansCJK-Regular.ttc"),
    "/usr/share/fonts/truetype/custom/sarasa-mono-sc.ttc",
    "/usr/share/fonts/truetype/custom/SarasaMonoSC-Regular.ttf",
    "/usr/share/fonts/truetype/custom/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

DEFAULT_FONT_DIRS = [
    SERVICE_ROOT / "fonts",
    Path("/usr/share/fonts/truetype/custom"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/noto"),
]


def _split_env_paths(value: str | None) -> list[Path]:
    if not value:
        return []
    raw_parts: list[str] = []
    for chunk in value.split(os.pathsep):
        raw_parts.extend(part.strip() for part in chunk.split(","))
    return [Path(part).expanduser() for part in raw_parts if part]


def _iter_font_files_in_dir(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS
    )


def get_embeddable_font_paths(font_paths: list[str] | None = None) -> list[Path]:
    """按优先级返回当前服务能找到的字体文件。"""
    candidates: list[Path] = []
    if font_paths is not None:
        candidates.extend(Path(p).expanduser() for p in font_paths if p)
    else:
        candidates.extend(_split_env_paths(os.getenv(ENV_FONT_PATHS)))
        candidates.extend(Path(p).expanduser() for p in DEFAULT_FONT_CANDIDATES)
        env_dirs = _split_env_paths(os.getenv(ENV_FONT_DIRS))
        for directory in [*env_dirs, *DEFAULT_FONT_DIRS]:
            candidates.extend(_iter_font_files_in_dir(directory))

    existing: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in FONT_EXTENSIONS:
            existing.append(candidate)
    return existing


def _normalize_font_name(name: str) -> str:
    normalized = re.sub(r"[\s_\-]+", "", name).lower()
    for suffix in STYLE_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _is_font_reference_part(name: str) -> bool:
    if name == "word/document.xml" or name == "word/numbering.xml":
        return True
    return bool(re.match(r"word/(header|footer|footnotes|endnotes|comments)\d*\.xml$", name))


def _collect_referenced_font_names(docx_path: str) -> set[str]:
    referenced: set[str] = set()
    with zipfile.ZipFile(docx_path) as zf:
        for name in zf.namelist():
            if not _is_font_reference_part(name):
                continue
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            for element in root.iter():
                for attr in FONT_ATTRS:
                    value = element.attrib.get(attr)
                    if value:
                        referenced.add(value.strip())
    return referenced


def _font_path_matches_references(font_path: Path, referenced_fonts: set[str]) -> bool:
    stem = _normalize_font_name(font_path.stem)
    if not stem:
        return False
    for font_name in referenced_fonts:
        target = _normalize_font_name(font_name)
        if target == stem or target in stem or stem in target:
            return True
    return False


def _font_setup_hint(reason: str, referenced_fonts: set[str] | None = None) -> str:
    parts = [reason]
    if referenced_fonts:
        fonts = "、".join(sorted(referenced_fonts)[:8])
        parts.append(f"DOCX 实际引用字体：{fonts}")
    parts.append("文件已生成，字体未嵌入")
    parts.append("如不需要跨设备固定字体，可在 MD Viewer 设置中关闭“嵌入字体”")
    parts.append(
        "如需固定字体，请在 DOCX 服务端挂载授权字体，"
        "并设置 MD_VIEWER_DOCX_FONT_DIRS 或 MD_VIEWER_DOCX_FONT_PATHS"
    )
    return "；".join(parts)


def embed_fonts_if_requested(
    docx_path: str,
    embed_font: bool,
    font_paths: list[str] | None = None,
) -> list[str]:
    if not embed_font:
        return []

    existing = get_embeddable_font_paths(font_paths)
    if not existing:
        return [_font_setup_hint("未找到可嵌入字体")]

    warnings: list[str] = []
    try:
        referenced_fonts = _collect_referenced_font_names(docx_path)
    except Exception as exc:
        referenced_fonts = set()
        warnings.append(f"读取 DOCX 字体引用失败，已跳过字体嵌入：{exc}")
    matching = [
        font_path for font_path in existing
        if _font_path_matches_references(font_path, referenced_fonts)
    ]
    if not matching:
        if not warnings:
            warnings.append(_font_setup_hint("未找到与 DOCX 实际字体引用匹配的可嵌入字体", referenced_fonts))
        return warnings

    try:
        with zipfile.ZipFile(docx_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            for font_path in matching:
                arcname = f"word/fonts/{font_path.name}"
                if arcname in zf.namelist():
                    continue
                zf.write(font_path, arcname)
    except Exception as exc:
        warnings.append(f"字体嵌入失败，已返回未嵌入字体的 DOCX：{exc}")

    # 确保写入后仍是一个可读 zip/docx；失败时让调用方返回 500 更安全。
    if not zipfile.is_zipfile(docx_path):
        raise ValueError(f"DOCX 文件已损坏: {docx_path}")
    return warnings


def resolve_reference_docx(reference_base64: str | None) -> tuple[str | None, list[str]]:
    """验证自定义 reference.docx。当前生成器会复用其首个 section 和样式。"""
    if not reference_base64:
        return None, []

    import base64
    import tempfile
    from docx import Document

    warnings: list[str] = []
    try:
        raw = base64.b64decode(reference_base64)
        fd, path = tempfile.mkstemp(prefix="mdv-reference-", suffix=".docx")
        os.close(fd)
        Path(path).write_bytes(raw)
        Document(path)
        return path, warnings
    except Exception as exc:
        warnings.append(f"自定义 reference.docx 无法读取，已回退内置样式：{exc}")
        return None, warnings
