# 变更日志

本文档记录 `md-viewer-docx-service` 的重要变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号原则上遵循语义化版本。当前服务仍以独立 DOCX 导出服务身份发布；与 MD Viewer 桌面端的版本协同关系以 README 和发布说明为准。

---

## [0.2.3] - 2026-08-07

> 状态：配套 MD Viewer v2.6.0
> 类型：导出诚实化（图表源码不外泄）+ DOCX 排版质量修复

### 修复

- **图表源码不再泄漏进 DOCX**：渲染失败或不支持的图表围栏，在服务端上游做中性化替换（此前根因在 `main.py` 的上游替换而非 `generator.py`），不再把失败图表的源码块原样写进 Word；配合桌面端 CLI + GUI 两路，构成服务端安全网。围栏（```/~~~ 反引号配对）与行内代码内的内容不误伤。
- 修复有序列表编号被嵌套无序子列表重置的问题。
- 修复行内/块级公式图片按位置配对错乱（对调）的问题，行内公式保持段内排版。
- 修复普通本地图片在 bundle 模式下资源嵌入、以及缺资源时静默不报的问题，改为缺资源时给 warning。
- 修复表格分隔行 `:---:` 对齐标记未生效的问题。

### 改进

- 服务版本升至 `0.2.3`，推荐与 MD Viewer v2.6.0 同步部署；`MIN_CLIENT_VERSION` 保持 `1.7.0`（无客户端协议破坏）。

### 测试

- 新增 `test_docx_quality_fixes.py` 覆盖上述四个已确认排版 bug；补充图表中性化（`test_chart_neutralization.py`）与 image injector 回归。全量 355 用例通过。

---

## [0.2.2] - 2026-05-30

> 状态：配套 MD Viewer v2.4.0
> 类型：补丁修复，DOCX 图表/公式导出尺寸、对齐和诊断优化

### 修复

- 修复部分图表、公式或客户端预渲染图片在 DOCX 中过小、过大、未居中或被正文缩进影响的问题。
- 修复 `preview` 与非 `preview` 样式下宽幅架构图、流程图、ERD、拓扑图等内容可读性不足的问题，按图片宽高和版心约束做最小可读宽度提升。
- 修复图表标题与紧随其后的图表图片在 Word 中容易分页分离的问题。
- 修复默认品牌信息被写入 Word 页脚的问题，改为输出在正文末尾，与 MD Viewer PDF 导出行为保持一致。
- 修复重复渲染 warning 在响应头中多次出现的问题，改为去重后返回。
- 改进 Playwright/Chromium 缺失时的图表降级 warning，直接说明 full 镜像或安装 Chromium 的处理办法。

### 改进

- 服务版本升至 `0.2.2`，推荐与 MD Viewer v2.4.0 同步部署。
- `package.json` / `package-lock.json` 版本同步到 `0.2.2`，避免 renderer 依赖包版本和 FastAPI 服务版本长期不一致。
- 保持 renderer artifact schema `2.0` 不变，继续兼容 MD Viewer v2.2+ 的图表渲染产物。
- 补充 DOCX 图片注入和非 preview 样式契约测试，覆盖内联占位图、宽图放大、竖图高度约束、图表标题分页和品牌信息位置。

### 测试

- 新增/更新 chart renderer、image injector、generator、convert-source、main 和 non-preview style contracts 测试。
- 重点覆盖真实导出中暴露的图表尺寸、居中、源码降级 warning、品牌信息和服务端 full fidelity 图片宽度逻辑。

---

## [0.2.1] - 2026-05-22

> 状态：配套 MD Viewer v2.3.0
> 类型：补丁修复，DOCX 字体嵌入体积与提示优化

### 修复

- 修复本地 macOS 服务在 `preview` 样式下优先引用 `PingFang SC`，但字体嵌入策略无法匹配内置字体，导致正常导出仍出现字体 warning 的问题。
- 修复默认字体候选曾扫描 macOS 系统字体目录，可能把 `Apple Color Emoji.ttc`、`PingFang.ttc`、`Songti.ttc` 等系统字体一并写入 DOCX，造成文件体积异常膨胀的问题。
- 修复 `embedFont=true` 时按候选目录全量嵌入字体的问题，改为只嵌入 DOCX 实际引用且服务端可匹配到的字体。

### 改进

- `preview` 样式默认优先使用服务内置的 `Noto Sans CJK SC`，使本地服务、Docker 本地部署和远程 Docker 服务的默认导出行为更一致。
- 字体 warning 改为可操作提示：普通用户可关闭“嵌入字体”，需要固定跨设备字体时由服务管理员挂载授权字体，并配置 `MD_VIEWER_DOCX_FONT_DIRS` 或 `MD_VIEWER_DOCX_FONT_PATHS`。
- 字体目录说明补充 Docker 本地和远程服务边界：服务只读取容器内置字体或显式挂载的授权字体，不默认读取宿主机系统字体目录。

### 测试

- 新增按需字体嵌入测试，覆盖多字体引用、未引用字体不嵌入、Noto CJK TTC 与 `Noto Sans CJK SC` 匹配、未匹配字体 warning 指引。
- 新增 `preview` 字体选择测试，确认即使系统存在 `PingFang SC`，也优先使用服务内置可嵌入字体。
- 最近一次验证通过：
  - `/opt/anaconda3/bin/python3.11 -m pytest -q`，293 个用例通过。
  - 真实 Markdown 预览样式 DOCX 导出 `warnings=[]`，仅嵌入 `NotoSansCJKsc-Regular.otf`。

### 兼容性说明

- 服务版本升至 `0.2.1`，推荐与 MD Viewer v2.3.0 同步部署。
- 如果用户额外选择公文、内部材料或报告样式，并要求嵌入未随服务分发的商业/系统字体，仍需由部署方自行挂载已授权字体。

---

## [0.2.0] - 2026-05-21

> 状态：配套 MD Viewer v2.2.0
> 类型：RendererPlugin schema 2.0 适配、服务端 full fidelity 图表导出增强

### 新增

- 新增 renderer artifact schema `2.x` 兼容能力，支持读取 `renderers[]` 能力清单。
- 新增 DOCX 服务端 allowlist，覆盖 Mermaid、KaTeX、Excalidraw、DrawIO、ECharts、Markmap、Graphviz、Infographic、PlantUML、Vega-Lite、D2、BPMN、WaveDrom、C4-PlantUML。
- 新增 `/readyz.rendererWarnings`，当 manifest 与服务 allowlist 不一致或 schema minor 版本较新时返回诊断信息。
- 新增 BPMN 文件引用识别，支持 Markdown 图片语法引用 `.bpmn` 后由 full fidelity 渲染链路替换为图片。

### 改进

- full fidelity 渲染 payload 启用 MD Viewer v2.2.0 新增的 RendererPlugin 图表类型。
- 图表替换逻辑优先使用 renderer 返回的 `blockId`，减少同类型多图表文档中因 `sourceIndex` 偏移导致的替换错误。
- 保留 `rendererSupportedCharts` 作为旧客户端兼容字段，同时在 schema 2.0 下使用更完整的 renderer manifest 做能力判断。
- README 和 renderer artifact 文档补充 schema 2.0、allowlist、RendererPlugin 能力矩阵和 `/readyz` 示例。

### 修复

- 修复新增 RendererPlugin 图表在服务端 DOCX full fidelity 导出时可能退化为源码的问题。
- 修复 BPMN 代码块与 `.bpmn` 文件引用混排时图片替换顺序不稳定的问题。
- 修复 manifest 声明新图表但 DOCX 服务未显式允许时静默启用的风险。

### 测试

- 新增 renderer artifact schema 2.0、allowlist warning、schema minor warning 覆盖。
- 新增 Vega-Lite、D2、BPMN、WaveDrom、C4-PlantUML 的 full fidelity 计数与替换测试。
- 最近一次验证通过：
  - `uv run --python 3.12 --with-requirements requirements.txt python -m pytest`

### 兼容性说明

- 服务版本升至 `0.2.0`，仍兼容 schema `1.x` artifact。
- 推荐与 MD Viewer v2.2.0 及其 server renderer artifact 同步部署。

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
