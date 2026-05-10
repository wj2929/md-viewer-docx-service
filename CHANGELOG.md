# 变更日志

本文档记录 `md-viewer-docx-service` 的重要变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号原则上遵循语义化版本。当前服务仍以独立 DOCX 导出服务身份发布；与 MD Viewer 桌面端的版本协同关系以 README 和发布说明为准。

---

## [0.1.0] - 2026-05-10

> 状态：开源准备中  
> 类型：DOCX 导出服务能力收口、完整服务端渲染模式、开源发布整理

### 新增

- 新增 `/convert-source` 接口，支持调用方提交 Markdown 内容、Markdown URL 或包含资源的 bundle 后直接生成 DOCX。
- 新增 full fidelity 服务端渲染模式，可通过 Playwright 调用 MD Viewer 构建产物，对 Mermaid、KaTeX、ECharts、Markmap、Graphviz、DrawIO、Infographic、Excalidraw 等内容截图后注入 DOCX。
- 新增 renderer artifact 检查能力，`/readyz` 可返回完整渲染链路是否可用、artifact 版本、schema、支持的图表类型和渲染并发配置。
- 新增 bundle 资源加载与相对路径解析，支持 Markdown 中引用相对图片、DrawIO XML、`.excalidraw` 等资源。
- 新增 slim / full 两类 Docker 镜像边界：slim 面向 MD Viewer 客户端预渲染导出，full 面向独立服务端完整渲染。
- 新增多样式 DOCX 输出能力，覆盖 `preview`、`standard`、`official`、`internal`、`report`。
- 新增 `NOTICE.md`、`SECURITY.md`、`.env.example`、CI 工作流、字体目录说明和 renderer 目录说明，补齐开源发布基础材料。
- 新增 Docker Hub 发布工作流，可在手动触发或推送 `v*` tag 时构建并推送 full / slim 镜像。

### 改进

- 改进 DOCX 图表图片注入尺寸，使图表、公式和画板类内容更接近 MD Viewer 预览/PDF 导出的视觉比例。
- 改进 preview 与非 preview 样式的段落、标题、表格、代码块、图片居中和首行缩进规则。
- 改进公文、机关内部、报告等格式的模板参数，降低大面积空白、图表过小和段落缩进异常的风险。
- 改进 PlantUML / PUML 渲染，支持通过 PlantUML Server 转成图片后注入 DOCX。
- 改进字体处理，内置 Noto CJK 字体资源，并在字体无法嵌入时保留字体名称并返回 warning。
- 放开固定图片数量上限，导出限制改由请求体大小、单图大小、内存和超时控制。
- 改进 `footerText` 处理，调用方传 `null` 或空字符串时不再输出页脚署名。
- 改进 warning 响应头编码，避免中文 warning 或特殊字符破坏 HTTP header。
- 改进 Graphviz 能力探测，仅在 `dot` 可用时报告对应服务端渲染器。
- 切换 npm lockfile 到公开 npm registry，避免开源用户安装依赖时依赖内部 Nexus。

### 修复

- 修复 DOCX 导出时部分图表截图过大或过小的问题。
- 修复非 preview 格式下图片、公式和图表对齐不稳定的问题。
- 修复关闭导出署名后 DOCX 仍出现默认署名的问题。
- 修复部分 DrawIO、PlantUML、KaTeX 和 Graphviz 内容在 DOCX 中退化为源码或尺寸异常的问题。
- 修复部分导出 warning 在客户端无法正确展示的问题。

### 测试

- 新增 `/convert-source`、source schema、bundle loader、source loader、renderer artifact、renderer CLI、full fidelity renderer 等测试覆盖。
- 新增 DOCX generator、image injector、chart renderers、presets、font embedder、render runtime 的回归测试。
- 新增 preview 与非 preview 样式契约测试，覆盖图表尺寸、段落缩进、图片布局和公文类格式约束。
- 最近一次验证通过：
  - `pytest tests/test_convert_source.py tests/test_convert_source_schema.py tests/test_generator.py tests/test_main.py tests/test_non_preview_style_contracts.py tests/test_renderer_cli.py`

### 兼容性说明

- `/convert` 仍是传统接口，适合 MD Viewer 客户端或已经自行预渲染图表的调用方。
- `/convert-source` 需要 full 镜像和有效 renderer artifact；slim 镜像不保证完整服务端截图能力。
- DOCX 输出不是浏览器页面像素级复制：图表、公式、画板类内容尽量通过截图保真，普通 Markdown 结构仍映射为 Word 样式。
- URL 输入只读取 Markdown 文本，不导出网页、不执行网页 JavaScript、不继承浏览器登录态。

---

## [0.0.1] - 2026-04-22

> 状态：内部 MVP  
> 类型：FastAPI + python-docx 基础 DOCX 生成服务

### 新增

- 新增 FastAPI 服务入口和 `/convert` DOCX 生成接口。
- 支持 Markdown 标题、段落、列表、表格、代码块和图片写入 DOCX。
- 支持客户端提交预渲染图表图片，并通过占位符注入 Word 文档。
- 新增基础 Docker 运行方式和本地开发命令。

### 改进

- 拆分 DOCX presets，提供多种文档样式基础配置。
- 补充 pytest 测试套件，覆盖核心生成链路。
- 修复代码块字号、行距和基础样式问题。
