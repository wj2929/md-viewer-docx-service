# md-viewer-docx-service

`md-viewer-docx-service` 是 MD Viewer 的 DOCX 导出服务。它通过 FastAPI、python-docx、Graphviz、PlantUML 和可选的 Playwright 浏览器渲染能力，把 Markdown 转成可下载的 Word 文档。

服务可以作为 MD Viewer 桌面客户端的本地导出后端，也可以独立部署成 Docker 服务，供其他系统提交 Markdown 内容、Markdown URL 或资源 bundle 后生成 DOCX。

## 功能特性

- 支持 Markdown 到 DOCX：标题、段落、列表、表格、代码块、图片、页脚和多种文档样式。
- 支持客户端预渲染图片：MD Viewer 可先把图表渲染为 PNG，再由服务注入 DOCX，适合本地桌面场景。
- 支持服务端完整渲染：full 镜像可直接消费 Markdown / URL / bundle，并对 Mermaid、KaTeX、ECharts、Markmap、Graphviz、DrawIO、Infographic、Excalidraw 等内容截图后导出。
- 支持 PlantUML / PUML：服务端通过 PlantUML Server 渲染为图片后注入 DOCX。
- 支持字体嵌入：可按授权情况配置本地字体路径，服务会在无法嵌入时降级并返回 warning。
- 支持 slim / full 两类镜像：本地轻量导出和服务端高保真导出可以分开部署。

## 运行模式

| 模式 | 镜像 | 适用场景 | 主要能力 |
|---|---|---|---|
| 客户端预渲染 | `wj2929/md-viewer-docx-service:<version>-slim` | MD Viewer 桌面客户端、本地导出 | 客户端传 Markdown + PNG 图片，服务拼装 DOCX |
| 轻量服务端渲染 | `wj2929/md-viewer-docx-service:<version>-slim` | 普通 Markdown、少量服务端图表 | 支持 Graphviz `dot` 等轻量能力，具体以 `/healthz` 为准 |
| 完整服务端渲染 | `wj2929/md-viewer-docx-service:<version>` | 独立 Docker 服务、CI、后端集成 | 支持 `/convert-source`，用浏览器渲染图表/公式/Excalidraw 后导出 |

镜像标签约定：

| 镜像 | 说明 |
|---|---|
| `wj2929/md-viewer-docx-service:<version>` | 完整镜像，包含 Node、Playwright、Chromium 和 renderer artifact |
| `wj2929/md-viewer-docx-service:<version>-full` | 完整镜像的显式标签 |
| `wj2929/md-viewer-docx-service:latest` | 最新稳定版完整镜像 |
| `wj2929/md-viewer-docx-service:<version>-slim` | 轻量镜像，推荐给 MD Viewer 客户端预渲染场景 |
| `wj2929/md-viewer-docx-service:slim` | 最新稳定版轻量镜像 |

## 快速启动

本地桌面用法建议只绑定 `127.0.0.1`：

```bash
docker run --rm --name md-viewer-docx-service \
  -p 127.0.0.1:3179:3000 \
  wj2929/md-viewer-docx-service:latest
```

MD Viewer 客户端服务地址填写：

```text
http://localhost:3179
```

Docker Compose：

```bash
docker compose up --build md-viewer-docx
```

启动 full 镜像：

```bash
docker compose --profile full up --build md-viewer-docx-full
```

Compose 文件默认把 slim 服务映射到 `127.0.0.1:3179`，把 full 服务映射到 `127.0.0.1:3180`。

从源码本地构建 full 镜像前，需要先按“本地开发”章节生成并同步 renderer artifact；否则服务可以启动，但 `/readyz` 会返回 `503`。

## 本地开发

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 3179
```

如果需要调试完整服务端渲染：

```bash
.venv/bin/python -m pip install -r requirements-full.txt
python -m playwright install chromium
```

然后准备 MD Viewer renderer artifact：

```bash
cd ../md-viewer
npm install
npm run build
cd ../md-viewer-docx-service
scripts/sync-renderer-artifact.sh
export MDV_RENDER_ARTIFACT_DIR="$PWD/renderers/dist/server-render"
```

`md-viewer` 本身不提供 HTTP 服务。它只在构建期产出浏览器渲染页面 artifact；`md-viewer-docx-service` 才是 Docker 镜像和 API 服务入口。

## API 总览

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/healthz` | 服务健康状态、版本、样式、字体、镜像能力 |
| `GET` | `/readyz` | full fidelity renderer artifact 是否可用 |
| `POST` | `/convert` | 传统导出接口：提交 Markdown，可附带客户端预渲染图片 |
| `POST` | `/convert-source` | 完整服务端渲染接口：提交 Markdown、Markdown URL 或 bundle |

所有成功导出的 DOCX 响应：

- `HTTP 200`
- `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- 响应体为 DOCX 二进制

## 鉴权与限流

默认未设置 `API_KEY` 时不校验鉴权，适合只绑定 `127.0.0.1` 的本地桌面用法。

设置环境变量 `API_KEY` 后，`/convert` 和 `/convert-source` 都必须携带：

```http
X-API-Key: your-api-key
```

鉴权失败返回：

```json
{
  "detail": "Invalid API key"
}
```

默认限流为每分钟 30 次，可通过 `RATE_LIMIT_PER_MIN` 调整。触发限流时返回 `429`。

## `GET /healthz`

返回服务进程状态、镜像模式、样式、字体和轻量服务端图表渲染器。

响应示例：

```json
{
  "status": "ok",
  "version": "0.1.0",
  "mode": "slim",
  "styles": ["preview", "standard", "official", "internal", "report"],
  "fontsAvailable": ["Noto Sans CJK SC"],
  "embedFontSupported": true,
  "chartRenderersAvailable": ["dot"],
  "minClientVersion": "1.7.0",
  "maxImagesPerRequest": null,
  "maxRequestSizeMb": 30
}
```

调用建议：

- 客户端启动或服务地址变更后先调用 `/healthz`。
- `styles` 应以服务返回值为准，客户端不要写死。
- `mode=slim` 适合客户端预渲染图片后上传。
- `mode=full` 表示镜像包含 Playwright，但 `/convert-source` 是否可用还要看 `/readyz`。
- `chartRenderersAvailable` 是 `/convert` 旧服务端渲染能力，例如 Graphviz 在这里显示为 `dot`。

## `GET /readyz`

返回 `/convert-source` 依赖的 renderer artifact 是否准备好。

响应示例：

```json
{
  "fullFidelityRenderSupported": true,
  "rendererHealth": "ok",
  "rendererArtifactVersion": "1.7.0",
  "rendererSchemaVersion": "1.0",
  "rendererSupportedCharts": ["mermaid", "katex", "excalidraw", "drawio", "echarts", "markmap", "graphviz", "infographic"],
  "renderConcurrency": 1,
  "sourceUrlPolicy": "local-friendly",
  "renderNetworkPolicy": "local-friendly"
}
```

如果 artifact 缺失或版本不兼容，返回 `503`，并包含 `rendererError`。

注意：`rendererSupportedCharts` 只表示浏览器 artifact 截图能力。PlantUML / PUML 由 DOCX 服务后处理渲染，所以不会出现在该字段中。

## `POST /convert`

`/convert` 是传统导出接口，适合 MD Viewer 客户端或已经自行渲染图表的调用方。

请求示例：

```json
{
  "markdown": "# 标题\n\n正文",
  "style": "standard",
  "images": [],
  "renderCharts": false,
  "embedFont": false,
  "clientVersion": "1.7.0"
}
```

请求字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `markdown` | string | 是 | - | Markdown 正文，长度 1 到 500000 字符 |
| `style` | string | 否 | `standard` | DOCX 样式，支持 `preview`、`standard`、`official`、`internal`、`report` |
| `title` | string \| null | 否 | `null` | 文档标题，最长 200 字符 |
| `footerText` | string \| null | 否 | `由 MD Viewer 生成` | 页脚文本，最长 200 字符；传 `null` 或空字符串时不显示页脚署名 |
| `images` | array | 否 | `[]` | 客户端预渲染图片列表 |
| `renderCharts` | boolean | 否 | `false` | 是否由服务端渲染图表；完整能力建议使用 `/convert-source` |
| `chartRenderers` | string[] | 否 | `[]` | 限定服务端图表渲染器，例如 `["mermaid", "dot"]` |
| `embedFont` | boolean | 否 | `false` | 是否尝试把可嵌入字体写入 DOCX |
| `clientVersion` | string \| null | 否 | `null` | 客户端版本，最长 20 字符 |
| `referenceDocxBase64` | string \| null | 否 | `null` | 自定义参考 DOCX 模板，base64 最大 20000000 字符 |

`images` 项结构：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `id` | string | 是 | - | 占位符 ID，格式为 `mdv__chart__xxxxxxxx__`，其中 `x` 为 8 位小写十六进制 |
| `pngBase64` | string | 是 | - | PNG 图片 base64，单项最大 2800000 字符 |
| `widthCm` | number | 否 | `15.5` | 期望图片宽度，范围 1.0 到 30.0 厘米，服务会按页面样式再收敛 |

客户端预渲染示例：

```bash
curl -X POST http://localhost:3179/convert \
  -H 'Content-Type: application/json' \
  -o output.docx \
  -d '{
    "markdown": "# 示例\n\n![](mdv__chart__aabbccdd__)",
    "style": "preview",
    "images": [
      {
        "id": "mdv__chart__aabbccdd__",
        "pngBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB...",
        "widthCm": 15.5
      }
    ],
    "embedFont": true,
    "clientVersion": "1.7.0"
  }'
```

纯 Markdown 示例：

```bash
curl -X POST http://localhost:3179/convert \
  -H 'Content-Type: application/json' \
  -o output.docx \
  -d '{
    "markdown": "# 标题\n\n正文\n\n| A | B |\n|---|---|\n| 1 | 2 |",
    "style": "report"
  }'
```

响应头：

| 响应头 | 说明 |
|---|---|
| `X-Service-Version` | 服务版本 |
| `X-Service-Mode` | 实际转换模式，常见值为 `clientRendered` 或 `serverRendered` |
| `X-Convert-Warnings` | JSON 字符串数组，包含字体降级、图片校验失败等 warning |
| `X-Charts-Rendered` | 已注入或服务端渲染的图表/公式图片数量 |
| `X-Charts-Failed` | 校验失败或渲染失败数量 |
| `X-Min-Client-Version` | 服务要求的最低客户端版本 |

调用方建议：

- 即使状态码是 `200`，也应读取 `X-Convert-Warnings` 并展示给用户。
- `X-Charts-Failed` 大于 0 时，建议提示“部分图表未成功导出”。
- 下载文件名可由调用方自行决定；服务默认返回 `export.docx`。

## `POST /convert-source`

`/convert-source` 是完整服务端渲染接口。调用方只需要提供 Markdown 内容、可访问的 Markdown URL，或包含 Markdown 与资源的 bundle，服务端即可生成 DOCX。

该接口适合脱离 MD Viewer 的服务端集成。它会复用 MD Viewer 构建产物中的浏览器渲染页面来生成图表/公式截图，再由 DOCX 服务完成 Word 文档生成。

三种输入模型：

| `sourceType` | 用途 |
|---|---|
| `markdown` | 调用方已经有 Markdown 字符串 |
| `url` | 调用方有一个可访问的 Markdown URL |
| `bundle` | 调用方有 Markdown 和相对图片、`.excalidraw` 等资源 |

请求字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `sourceType` | `markdown` \| `url` \| `bundle` | 是 | - | 输入来源类型 |
| `markdown` | string \| null | 条件必填 | `null` | `sourceType=markdown` 时必填；`bundle` 也可直接传入口 Markdown |
| `url` | string \| null | 条件必填 | `null` | `sourceType=url` 时必填，最长 2048 字符 |
| `entryPath` | string \| null | 条件必填 | `null` | `bundle` 入口 Markdown 路径；当 bundle 未直接传 `markdown` 时必填 |
| `resources` | `BundleResource[]` | 否 | `[]` | bundle 资源列表 |
| `style` | string | 否 | `standard` | DOCX 样式 |
| `renderMode` | `fullFidelity` | 否 | `fullFidelity` | 当前仅支持 `fullFidelity` |
| `fallbackMode` | `partial` \| `fail` | 否 | `partial` | 渲染失败时部分导出还是直接失败 |
| `theme` | `light` \| `dark` | 否 | `light` | 预留主题字段 |
| `embedFont` | boolean | 否 | `false` | 是否尝试嵌入字体 |
| `footerText` | string \| null | 否 | `由 MD Viewer 生成` | 页脚文本，传 `null` 或空字符串时不显示页脚署名 |
| `debugManifest` | boolean | 否 | `false` | 预留调试字段，生产环境通常保持 `false` |
| `clientVersion` | string \| null | 否 | `null` | 客户端版本，最长 20 字符 |
| `referenceDocxBase64` | string \| null | 否 | `null` | 自定义参考 DOCX 模板，base64 最大 20000000 字符 |

`BundleResource` 字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `path` | string | 是 | - | POSIX 相对路径，不能是绝对路径，不能跳出包根目录 |
| `kind` | `text` \| `binary` | 是 | - | 文本或二进制资源 |
| `content` | string \| null | 条件必填 | `null` | `kind=text` 时必填，最大 5000000 字符 |
| `base64` | string \| null | 条件必填 | `null` | `kind=binary` 时必填，最大 7000000 字符 |
| `mediaType` | string | 否 | `application/octet-stream` | 资源媒体类型 |
| `size` | number | 是 | - | 解码后的资源大小，0 到 5000000 字节 |

Markdown 输入示例：

````bash
curl -X POST http://localhost:3180/convert-source \
  -H 'Content-Type: application/json' \
  -o output.docx \
  -d '{
    "sourceType": "markdown",
    "markdown": "# 图表\n\n```mermaid\ngraph TD\n  A[开始] --> B[结束]\n```",
    "style": "preview",
    "fallbackMode": "partial"
  }'
````

URL 输入示例：

```bash
curl -X POST http://localhost:3180/convert-source \
  -H 'Content-Type: application/json' \
  -o output.docx \
  -d '{
    "sourceType": "url",
    "url": "http://127.0.0.1:8080/docs/demo.md",
    "style": "preview",
    "fallbackMode": "partial"
  }'
```

URL 输入只读取 Markdown 文本，不导出网页、不执行网页 JavaScript、不继承浏览器登录态、不自动抓取页面内资源。相对图片、`.excalidraw`、DrawIO XML 等完整资源应使用 bundle 输入。

URL 读取规则：

- 只支持 `http` / `https`。
- 默认最大下载 5MB，超时 10 秒，最多 3 次 redirect。
- 每次 redirect 后都会重新校验目标 URL。
- 默认接受 `.md`、`.markdown`、`.txt` 路径，或响应 `Content-Type` 为 `text/markdown`、`text/x-markdown`、`text/plain` 的内容。
- 不发送 cookie、token 或浏览器登录态。

Bundle 输入示例：

```json
{
  "sourceType": "bundle",
  "entryPath": "docs/readme.md",
  "resources": [
    {
      "path": "docs/readme.md",
      "kind": "text",
      "content": "# 图\n\n![架构](../diagrams/a.excalidraw)",
      "mediaType": "text/markdown",
      "size": 38
    },
    {
      "path": "diagrams/a.excalidraw",
      "kind": "text",
      "content": "{\"type\":\"excalidraw\",\"version\":2,\"source\":\"\",\"elements\":[]}",
      "mediaType": "application/json",
      "size": 60
    }
  ],
  "style": "preview",
  "fallbackMode": "partial"
}
```

Bundle 路径使用 POSIX 相对路径，不允许绝对路径或跳出包根目录的 `..`。Markdown 内的相对 `.excalidraw` 引用会按入口 Markdown 所在目录解析。

响应头：

| 响应头 | 说明 |
|---|---|
| `X-Service-Version` | 服务版本 |
| `X-Service-Mode` | 固定为 `fullFidelity` |
| `X-Render-Status` | `success`、`partial`、`failed` 或 `timeout` |
| `X-Render-Warning-Count` | renderer 和 DOCX 生成阶段 warning 数 |
| `X-Render-Failed-Blocks` | renderer 报告的失败块数量 |
| `X-Charts-Rendered` | 已注入 DOCX 的截图数量 |
| `X-Render-Summary-Base64` | UTF-8 JSON 摘要的 base64 编码 |
| `X-Min-Client-Version` | 服务要求的最低客户端版本 |

## 图表支持

| 类型 | `/convert` | `/convert-source` | 说明 |
|---|---|---|---|
| Mermaid | 视镜像能力而定 | 支持 | full 模式由浏览器截图 |
| KaTeX | 视镜像能力而定 | 支持 | 导出为图片，不保证 Word 中可编辑 |
| ECharts | 视镜像能力而定 | 支持 | full 模式由浏览器截图 |
| Markmap | 视镜像能力而定 | 支持 | full 模式由浏览器截图 |
| Graphviz / DOT | 支持 `dot` | 支持 `graphviz` / `dot` | `/healthz` 中轻量渲染器名为 `dot` |
| DrawIO | 客户端预渲染推荐 | 支持 fenced code block | full 模式由浏览器截图 |
| Excalidraw | 客户端预渲染推荐 | 支持 fenced code block 与 bundle `.excalidraw` 引用 | 仅渲染，不提供编辑 |
| Infographic | 客户端预渲染推荐 | 支持 | full 模式由浏览器截图 |
| PlantUML / PUML | 支持 | 支持 | 由服务端调用 PlantUML Server 渲染 |

DOCX 输出不是浏览器页面截图。图表、公式和画板类内容会尽量以截图保持视觉效果，普通 Markdown 结构会映射为 DOCX 样式。

## 样式

| 样式 | 用途 |
|---|---|
| `preview` | 尽量接近 MD Viewer 预览排版，适合图表较多的文档 |
| `standard` | 通用文档 |
| `official` | 正式公文 |
| `internal` | 机关内部文件 |
| `report` | 调研/分析报告 |

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `API_KEY` | 空 | 设置后 `/convert` 和 `/convert-source` 必须携带 `X-API-Key` |
| `RATE_LIMIT_PER_MIN` | `30` | 每个来源 IP 每分钟请求数 |
| `MD_VIEWER_DOCX_FONT_PATHS` | 空 | 额外字体文件路径，macOS/Linux 用冒号分隔 |
| `MD_VIEWER_DOCX_FONT_DIRS` | 空 | 额外字体目录，macOS/Linux 用冒号分隔 |
| `MDV_SOURCE_URL_POLICY` | `local-friendly` | `/convert-source` URL 输入策略：`local-friendly`、`strict`、`allowlist` |
| `MDV_SOURCE_URL_ALLOWLIST` | 空 | URL 输入 allowlist 主机，逗号分隔 |
| `MDV_RENDER_ARTIFACT_DIR` | `/app/renderers/dist/server-render` | renderer artifact 目录 |
| `MDV_RENDER_CLI` | `/app/renderers/mdv-renderer-cli.mjs` | renderer CLI 路径 |
| `MDV_RENDER_TIMEOUT_MS` | `60000` | 单次浏览器渲染页面超时 |
| `MDV_RENDER_CLI_GRACE_MS` | `max(15000, MDV_RENDER_TIMEOUT_MS)` | renderer CLI 子进程额外等待时间 |
| `MDV_RENDER_NETWORK_POLICY` | `local-friendly` | 浏览器渲染阶段资源访问策略 |
| `MDV_RENDER_ALLOWLIST_HOSTS` | 空 | 浏览器渲染阶段允许访问的主机，逗号分隔 |
| `MDV_RENDER_CONCURRENCY` | `1` | `/readyz` 暴露的渲染并发配置 |
| `MDV_PLANTUML_SERVER_URL` | `https://www.plantuml.com/plantuml` | PlantUML Server 地址 |
| `PLANTUML_SERVER_URL` | 空 | 兼容旧变量；优先级低于 `MDV_PLANTUML_SERVER_URL` |
| `MDV_PLANTUML_TIMEOUT_SEC` | `12` | PlantUML 单次请求超时秒数 |
| `MDV_PLANTUML_RETRIES` | `3` | PlantUML 渲染重试次数 |

环境变量示例见 `.env.example`。

## Docker

拉取预构建完整镜像：

```bash
docker run --rm --name md-viewer-docx-service \
  -p 127.0.0.1:3179:3000 \
  wj2929/md-viewer-docx-service:latest
curl http://localhost:3179/readyz
```

拉取轻量镜像：

```bash
docker run --rm --name md-viewer-docx-service-slim \
  -p 127.0.0.1:3179:3000 \
  wj2929/md-viewer-docx-service:slim
curl http://localhost:3179/healthz
```

构建 slim 镜像：

```bash
docker build -t md-viewer-docx-service:dev-slim -f Dockerfile.slim .
docker run --rm -p 127.0.0.1:3179:3000 md-viewer-docx-service:dev-slim
curl http://localhost:3179/healthz
```

构建 full 镜像：

```bash
cd ../md-viewer
npm install
npm run build
cd ../md-viewer-docx-service
scripts/sync-renderer-artifact.sh
docker build -t md-viewer-docx-service:dev-full -f Dockerfile.full .
docker run --rm -p 127.0.0.1:3180:3000 md-viewer-docx-service:dev-full
curl http://localhost:3180/readyz
```

发布 Docker Hub 镜像由 GitHub Actions 的 `Docker Publish` 工作流完成。需要在仓库 Actions secrets 中配置 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN`，然后手动运行 workflow 或推送 `v*` tag。full 镜像默认使用 `md-viewer` 的 `v2.0.0` 构建 renderer artifact；如需调整，可在手动运行 workflow 时填写 `renderer_ref`，或配置仓库变量 `MDV_RENDERER_REF`。

部署到局域网或公网时建议：

- 设置 `API_KEY`。
- 放在 HTTPS 反向代理之后。
- 明确设置 `MDV_SOURCE_URL_POLICY`，公网服务优先用 `strict` 或 `allowlist`。
- 不要把无鉴权服务直接暴露给不可信网络。

## 错误响应

| 状态码 | 场景 | 响应特征 |
|---:|---|---|
| `400` | `style` 不在支持列表内 | `detail.code=STYLE_INVALID` |
| `400` | slim 镜像请求 `/convert` 服务端图表渲染 | `detail.code=RENDER_UNAVAILABLE` |
| `400` | `/convert-source` 读取 Markdown、URL 或 bundle 失败 | `detail.code=SOURCE_LOAD_FAILED` |
| `401` | `API_KEY` 校验失败 | `detail=Invalid API key` |
| `422` | 请求字段不符合 schema | FastAPI / Pydantic validation error |
| `429` | 超过限流 | SlowAPI rate limit error |
| `502` | `/convert-source` 设置 `fallbackMode=fail` 且渲染未成功 | `detail.code=RENDER_FAILED` |
| `500` | DOCX 生成、图片注入或内部异常 | `detail.code=INTERNAL` |

## 限制与兼容性

- `markdown` 最大 500000 字符。
- 单张 `pngBase64` 最大 2800000 字符。
- `referenceDocxBase64` 最大 20000000 字符。
- bundle 单个资源最大 5MB。
- URL 输入最大下载 5MB。
- `/healthz.maxImagesPerRequest` 为 `null` 表示服务端不设置固定图片数量上限，但仍受请求体大小、内存和超时限制。
- 字体嵌入受 Office/WPS 支持和字体授权影响，服务会失败降级并返回 warning。
- KaTeX 当前优先保证 Word 中可见，不保证公式可编辑。

## 测试

```bash
PYTHONPATH=. pytest -q
```

如果测试 full renderer CLI，需要安装 full 依赖和 Playwright Chromium。

## 开源说明

- 主许可证：`LICENSE`
- 变更记录：`CHANGELOG.md`
- 第三方依赖和字体声明：`NOTICE.md`
- 安全反馈和部署建议：`SECURITY.md`
- 字体目录说明：`fonts/README.md`
- renderer artifact 说明：`renderers/README.md`

本仓库不应提交私有文档、内部执行记录、本地绝对路径、访问 token、未确认授权的字体文件或组织内部镜像源配置。
