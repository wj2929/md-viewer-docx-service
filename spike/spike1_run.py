#!/usr/bin/env python3
"""
Spike-1: 验证 python-docx + generator.py 对真实 md-viewer 文档的渲染能力

目标:
  用参考项目 generator.py 直接处理用户真实 CCE 文档, 产出 DOCX, 人工评估质量.

做法:
  1. 读 /Users/mac/Documents/SynologyDrive/国开在线/研发中心/专项工作/一网/cce/华为云/CCE集群外挂存储详情.md
  2. 把其中的图表代码块 (mermaid/echarts/dot/markmap/drawio/graphviz/plantuml)
     替换为 [图表: {lang} - N] 占位文本 (Spike-1 不测图片插入)
  3. 调 generate_docx_from_content(content, out_path, style='standard')
  4. 再跑一次 style='official'
  5. Word/WPS 人工打开评估
"""

import os
import re
import sys
import time
import traceback
from pathlib import Path

# 让 Python 能 import 同目录下的 generator
sys.path.insert(0, str(Path(__file__).parent))

from generator import generate_docx_from_content, VALID_STYLES

# ────────────────────────────────────────────────────────────────────────
# 配置
# ────────────────────────────────────────────────────────────────────────
SOURCE_MD = Path("/Users/mac/Documents/SynologyDrive/国开在线/研发中心/专项工作/一网/cce/华为云/CCE集群外挂存储详情.md")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 需要替换为占位符的图表语言
CHART_LANGS = {"mermaid", "echarts", "dot", "graphviz", "markmap", "drawio", "plantuml"}

# ────────────────────────────────────────────────────────────────────────
# Markdown 预处理: 图表代码块 -> 占位文本
# ────────────────────────────────────────────────────────────────────────
CHART_CODE_BLOCK_RE = re.compile(
    r"^```(" + "|".join(CHART_LANGS) + r")\s*\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def replace_chart_blocks(md: str) -> tuple[str, dict[str, int]]:
    """将图表代码块替换为占位文本, 返回处理后的 md 和统计"""
    stats: dict[str, int] = {}
    counter = {"n": 0}

    def _sub(m):
        lang = m.group(1).lower()
        counter["n"] += 1
        stats[lang] = stats.get(lang, 0) + 1
        return f"\n> **[图表占位 {counter['n']}]** 类型: {lang} — 原图表代码已略\n"

    return CHART_CODE_BLOCK_RE.sub(_sub, md), stats


# ────────────────────────────────────────────────────────────────────────
# 文档统计
# ────────────────────────────────────────────────────────────────────────
def doc_stats(md: str) -> dict:
    lines = md.split("\n")
    tables = sum(1 for l in lines if re.match(r"^\|.*\|\s*$", l))
    headings = {
        "h1": sum(1 for l in lines if l.startswith("# ")),
        "h2": sum(1 for l in lines if l.startswith("## ")),
        "h3": sum(1 for l in lines if l.startswith("### ")),
        "h4": sum(1 for l in lines if l.startswith("#### ")),
    }
    box_drawing = sum(1 for l in lines if re.search(r"[┌┐└┘├┤┬┴┼─│┃┏┓┗┛]", l))
    code_fences = sum(1 for l in lines if l.startswith("```"))
    return {
        "lines": len(lines),
        "bytes": len(md.encode("utf-8")),
        "table_rows": tables,
        "headings": headings,
        "box_drawing_lines": box_drawing,
        "code_fences": code_fences // 2,
    }


# ────────────────────────────────────────────────────────────────────────
# 主流程
# ────────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*70}")
    print("Spike-1: python-docx + generator.py 真实文档渲染能力验证")
    print(f"{'='*70}\n")

    # 1. 读源文件
    if not SOURCE_MD.exists():
        print(f"[FATAL] 源文件不存在: {SOURCE_MD}")
        sys.exit(1)

    md_raw = SOURCE_MD.read_text(encoding="utf-8")
    print(f"[1/5] 读入源文档: {SOURCE_MD}")
    stats = doc_stats(md_raw)
    print(f"  行数:          {stats['lines']}")
    print(f"  字节:          {stats['bytes']:,}")
    print(f"  表格行:        {stats['table_rows']}")
    print(f"  标题:          H1={stats['headings']['h1']} "
          f"H2={stats['headings']['h2']} "
          f"H3={stats['headings']['h3']} "
          f"H4={stats['headings']['h4']}")
    print(f"  框线字符行:    {stats['box_drawing_lines']}")
    print(f"  代码块对:      {stats['code_fences']}")

    # 2. 预处理: 图表代码块替换占位
    md_processed, chart_stats = replace_chart_blocks(md_raw)
    total_charts = sum(chart_stats.values())
    print(f"\n[2/5] 图表代码块替换占位:")
    for lang, count in sorted(chart_stats.items()):
        print(f"  {lang:10s}: {count} 个")
    print(f"  合计:        {total_charts} 个图表替换为占位文本")

    # 3. 遍历所有 4 个预设分别跑一遍
    styles_to_test = ["standard", "official", "internal", "report"]
    results = []

    for style in styles_to_test:
        out_path = OUTPUT_DIR / f"spike1_{style}.docx"
        print(f"\n[3-{style}] 生成 DOCX: style={style}")
        t0 = time.time()
        try:
            generate_docx_from_content(
                md_processed,
                str(out_path),
                style=style,
                title="CCE集群外挂存储详情 · Spike-1",
                footer_text=f"md-viewer-docx-service Spike-1 · style={style}",
                references=None,
            )
            elapsed_ms = (time.time() - t0) * 1000
            size_kb = out_path.stat().st_size / 1024
            print(f"  ✓ 完成: {elapsed_ms:.0f}ms, {size_kb:.1f}KB, {out_path}")
            results.append({
                "style": style,
                "path": str(out_path),
                "elapsed_ms": round(elapsed_ms),
                "size_kb": round(size_kb, 1),
                "ok": True,
                "error": None,
            })
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            err_msg = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()
            print(f"  ✗ 失败: {err_msg}")
            print(tb)
            results.append({
                "style": style,
                "path": str(out_path),
                "elapsed_ms": round(elapsed_ms),
                "size_kb": 0,
                "ok": False,
                "error": err_msg,
                "traceback": tb,
            })

    # 4. 汇总
    print(f"\n{'='*70}")
    print("[4/5] 执行汇总")
    print(f"{'='*70}")
    print(f"{'style':<12}{'结果':<8}{'耗时':>10}{'大小':>12}  路径")
    print("-" * 70)
    for r in results:
        status = "✓ OK" if r["ok"] else "✗ FAIL"
        size = f"{r['size_kb']:.1f}KB" if r["ok"] else "-"
        print(f"{r['style']:<12}{status:<8}{r['elapsed_ms']:>6}ms  {size:>10}  {r['path']}")

    # 5. 评估引导
    print(f"\n[5/5] 人工评估引导\n")
    print("请打开以下文件做人工评估:")
    for r in results:
        if r["ok"]:
            print(f"  open {r['path']}")
    print("\n评估检查清单:")
    print("  □ 标题层级是否清晰 (H1-H4)")
    print("  □ 段落字体/字号是否符合样式预设")
    print("  □ 表格边框是否完整, 列对齐是否正确 (重点: 含 323 行表格)")
    print("  □ 有序/无序列表缩进是否正常")
    print("  □ 代码块字体是否等宽, 背景底纹是否显示")
    print("  □ 中英混排对齐是否正常")
    print("  □ 图表占位文本是否可见 (引用块样式)")
    print("  □ 框线字符行是否在代码块中对齐 (核心痛点: 9 行 ASCII 框线)")
    print("  □ 4 种预设之间样式差异是否符合预期")
    print("")
    print(f"对比参考: 当前 md-viewer 的 DOCX 输出 (若有保留样本)")

    # 返回码
    fail_count = sum(1 for r in results if not r["ok"])
    if fail_count > 0:
        print(f"\n[RESULT] {fail_count}/{len(results)} 个样式生成失败, Spike-1 未完全通过")
        sys.exit(1)
    print(f"\n[RESULT] {len(results)} 个样式全部生成成功, Spike-1 技术可行性初步验证")
    print("(最终通过还需人工评估质量, 见 5/5 检查清单)")


if __name__ == "__main__":
    main()
