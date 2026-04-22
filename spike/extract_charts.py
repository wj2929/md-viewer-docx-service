#!/usr/bin/env python3
"""
Spike-2 数据准备: 从 CCE 文档提取所有图表代码块
输出 JSON 供客户端 benchmark 使用
"""
import re
import json
from pathlib import Path

SOURCE = Path("/Users/mac/Documents/SynologyDrive/国开在线/研发中心/专项工作/一网/cce/华为云/CCE集群外挂存储详情.md")
OUTPUT = Path(__file__).parent / "chart_blocks.json"

md = SOURCE.read_text(encoding="utf-8")
blocks = re.findall(
    r'```(mermaid|echarts|dot|graphviz|markmap|drawio|plantuml)\s*\n(.*?)```',
    md, re.DOTALL | re.IGNORECASE
)

data = [{"lang": lang.lower(), "code": code.strip()} for lang, code in blocks]

OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"提取 {len(data)} 个图表代码块 → {OUTPUT}")
