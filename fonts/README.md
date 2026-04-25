# Docker 镜像字体文件

Dockerfile.slim 通过 `COPY fonts/ /usr/share/fonts/truetype/custom/` 将此目录的字体安装到容器中。

## 已通过 apt 自动安装的字体

`fonts-noto-cjk` 包提供 Noto Sans CJK SC / Noto Serif CJK SC，作为 CJK 字体的兜底 fallback。

## 需手动放入此目录的字体

| 文件名 | 字体名 | 被哪些样式使用 | 来源说明 |
|--------|--------|---------------|---------|
| `msyh.ttc` | 微软雅黑 (Microsoft YaHei) | standard | Windows 系统字体 |
| `simhei.ttf` | 黑体 (SimHei) | official, internal, report | Windows 系统字体 |
| `simsun.ttc` | 宋体 (SimSun) | internal, report | Windows 系统字体 |
| `simfang.ttf` | 仿宋_GB2312 (FangSong) | official | Windows 系统字体 |
| `simkai.ttf` | 楷体_GB2312 (KaiTi) | official | Windows 系统字体 |
| `FZXBSJW.TTF` | 方正小标宋简体 | official | 方正字库（公文排版常用） |

## 各样式字体依赖

- **standard**：微软雅黑（正文 + 标题）
- **official**（GB/T 9704 公文）：方正小标宋简体（标题）、仿宋_GB2312（正文）、黑体（一级标题）、楷体_GB2312（二级标题）
- **internal**（机关内部）：黑体（标题）、宋体（正文）
- **report**（调研报告）：黑体（标题）、宋体（正文）

## macOS 本地开发说明

直接在 macOS 上运行 uvicorn 时无需此目录中的字体文件。macOS 自带 Songti SC（宋体替代）、Heiti SC（黑体替代），但缺少仿宋、楷体和方正小标宋。使用 `official` 样式时相关字体会 fallback 到 Noto Sans CJK。

## 许可证

Windows 系统字体受 Microsoft 许可证约束，仅可在合法授权的环境中使用。方正小标宋简体需遵循方正字库授权协议。请确保合规后再将字体文件放入此目录。
