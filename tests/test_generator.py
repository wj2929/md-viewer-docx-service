import os
import pytest
from docx import Document

from app.generator import parse_inline, parse_markdown, generate_docx_from_content, BlockType


class TestParseInline:
    def test_bold(self):
        runs = parse_inline("**粗体** text")
        bold_runs = [r for r in runs if r.bold]
        assert len(bold_runs) == 1
        assert bold_runs[0].text == "粗体"

    def test_italic(self):
        runs = parse_inline("*斜体* text")
        italic_runs = [r for r in runs if r.italic]
        assert len(italic_runs) == 1
        assert italic_runs[0].text == "斜体"

    def test_code(self):
        runs = parse_inline("使用 `print()` 函数")
        code_runs = [r for r in runs if r.code]
        assert len(code_runs) == 1
        assert code_runs[0].text == "print()"

    def test_link(self):
        runs = parse_inline("点击 [链接](https://example.com) 跳转")
        link_runs = [r for r in runs if r.link]
        assert len(link_runs) == 1
        assert link_runs[0].text == "链接"
        assert link_runs[0].link == "https://example.com"

    def test_plain_text(self):
        runs = parse_inline("纯文本内容")
        assert len(runs) == 1
        assert runs[0].text == "纯文本内容"
        assert not runs[0].bold and not runs[0].italic and not runs[0].code


class TestParseMarkdown:
    def test_heading(self):
        blocks = parse_markdown("# 标题\n\n正文")
        assert blocks[0].type == BlockType.HEADING
        assert blocks[0].level == 1

    def test_paragraph(self):
        blocks = parse_markdown("这是一段正文。")
        assert any(b.type == BlockType.PARAGRAPH for b in blocks)

    def test_unordered_list(self):
        blocks = parse_markdown("- 项目 1\n- 项目 2")
        assert any(b.type == BlockType.UNORDERED_LIST for b in blocks)

    def test_ordered_list(self):
        blocks = parse_markdown("1. 第一项\n2. 第二项")
        assert any(b.type == BlockType.ORDERED_LIST for b in blocks)

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        blocks = parse_markdown(md)
        assert any(b.type == BlockType.TABLE for b in blocks)

    def test_code_block(self):
        md = "```python\nprint('hello')\n```"
        blocks = parse_markdown(md)
        assert any(b.type == BlockType.CODE_BLOCK for b in blocks)

    def test_blockquote(self):
        blocks = parse_markdown("> 引用文本")
        assert any(b.type == BlockType.BLOCKQUOTE for b in blocks)

    def test_horizontal_rule(self):
        blocks = parse_markdown("---")
        assert any(b.type == BlockType.HORIZONTAL_RULE for b in blocks)


class TestGenerateDocx:
    @pytest.mark.parametrize("style", ["standard", "official", "internal", "report"])
    def test_generate_each_style(self, tmp_path, sample_markdown, style):
        out_path = str(tmp_path / f"out_{style}.docx")
        generate_docx_from_content(
            content=sample_markdown,
            output_path=out_path,
            style=style,
        )
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0
        doc = Document(out_path)
        assert len(doc.paragraphs) > 0

    def test_auto_extract_title(self, tmp_path):
        md = "# 自动提取的标题\n\n正文内容"
        out_path = str(tmp_path / "title_test.docx")
        generate_docx_from_content(content=md, output_path=out_path, style="standard")
        doc = Document(out_path)
        texts = [p.text for p in doc.paragraphs if p.text.strip()]
        assert any("自动提取的标题" in t for t in texts)

    def test_invalid_style_falls_back_to_standard(self, tmp_path):
        out_path = str(tmp_path / "fallback.docx")
        generate_docx_from_content(
            content="# Test\n\nBody",
            output_path=out_path,
            style="nonexistent",
        )
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0
