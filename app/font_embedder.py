"""
DOCX 字体嵌入。

Word 字体嵌入涉及字体授权位和多个 OOXML 关系文件。这里采用保守策略：
只在找到明确字体文件时把字体写入 word/fonts/，并记录关系；任何异常都
返回 warning，保证 DOCX 仍可打开。
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path


DEFAULT_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/custom/sarasa-mono-sc.ttc",
    "/usr/share/fonts/truetype/custom/SarasaMonoSC-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def embed_fonts_if_requested(
    docx_path: str,
    embed_font: bool,
    font_paths: list[str] | None = None,
) -> list[str]:
    if not embed_font:
        return []

    candidates = font_paths or DEFAULT_FONT_CANDIDATES
    existing = [Path(p) for p in candidates if p and Path(p).exists()]
    if not existing:
        return ["未找到可嵌入字体，已保留字体名称并跳过嵌入"]

    warnings: list[str] = []
    try:
        with zipfile.ZipFile(docx_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            for font_path in existing[:2]:
                arcname = f"word/fonts/{font_path.name}"
                if arcname in zf.namelist():
                    continue
                zf.write(font_path, arcname)
        warnings.append("字体文件已写入 DOCX；不同 Office/WPS 对嵌入字体支持可能不同")
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
