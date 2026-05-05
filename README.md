# md-viewer-docx-service

MD Viewer 的 DOCX 导出服务。服务用 FastAPI + python-docx 把 Markdown 转为 Word 文档，解决客户端本地 Pandoc 路径里的中文字体、表格边框、图表图片和公文模板问题。

## 快速启动

```bash
docker run --rm --name md-viewer-docx-service \
  -p 127.0.0.1:3179:3000 \
  mdviewer/docx-service:latest
```

客户端设置里填写：

```text
http://localhost:3179
```

## 镜像

| 镜像 | 用途 |
|---|---|
| `mdviewer/docx-service:<version>-slim` | 推荐给 MD Viewer 客户端，支持客户端预渲染图片模式 |
| `mdviewer/docx-service:<version>-full` | 支持服务端图表/公式预渲染模式 |
| `mdviewer/docx-service:<version>` | 默认指向 slim |
| `mdviewer/docx-service:latest` | 最新稳定版 slim |

## API

### `GET /healthz`

返回服务状态、版本、样式、字体、服务端渲染器、客户端最低版本。

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

- 客户端启动或用户修改服务地址后，先调用 `/healthz` 判断服务是否可用。
- `mode=slim` 适合 MD Viewer 客户端预渲染图片后上传，是推荐模式。
- `mode=full` 才支持服务端浏览器渲染 Mermaid、ECharts、Markmap 等图表。
- `styles` 是当前服务支持的 DOCX 样式列表，客户端不应写死。
- `minClientVersion` 低于客户端版本要求时，客户端应提示升级。

### `POST /convert`

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

服务返回 DOCX 二进制，响应头包含：

- `X-Service-Version`
- `X-Service-Mode`
- `X-Convert-Warnings`
- `X-Charts-Rendered`
- `X-Charts-Failed`
- `X-Min-Client-Version`

### 鉴权

默认未设置 `API_KEY` 时不校验鉴权，适合只绑定 `127.0.0.1` 的本地桌面用法。

如果设置了环境变量 `API_KEY`，所有 `/convert` 请求都必须携带：

```http
X-API-Key: your-api-key
```

未携带或错误时返回 `401`：

```json
{
  "detail": "Invalid API key"
}
```

### `/convert` 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `markdown` | string | 是 | - | Markdown 正文，长度 1 到 500000 字符 |
| `style` | string | 否 | `standard` | DOCX 样式，支持 `preview`、`standard`、`official`、`internal`、`report` |
| `title` | string \| null | 否 | `null` | 文档标题，最长 200 字符 |
| `footerText` | string \| null | 否 | `由 MD Viewer 生成` | 页脚文本，最长 200 字符 |
| `images` | array | 否 | `[]` | 客户端预渲染图片列表，推荐由 MD Viewer 客户端传入 |
| `renderCharts` | boolean | 否 | `false` | 是否由服务端渲染图表；仅 full 镜像可用 |
| `chartRenderers` | string[] | 否 | `[]` | 限定服务端图表渲染器，例如 `["mermaid", "dot"]` |
| `embedFont` | boolean | 否 | `false` | 是否尝试把可嵌入字体写入 DOCX |
| `clientVersion` | string \| null | 否 | `null` | 客户端版本，最长 20 字符 |
| `referenceDocxBase64` | string \| null | 否 | `null` | 自定义参考 DOCX 模板，base64 最大 20000000 字符 |

`images` 中每一项的结构：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `id` | string | 是 | - | 占位符 ID，格式必须是 `mdv__chart__xxxxxxxx__`，其中 `x` 为 8 位小写十六进制 |
| `pngBase64` | string | 是 | - | PNG 图片 base64，单项最大 2800000 字符 |
| `widthCm` | number | 否 | `15.5` | 期望图片宽度，范围 1.0 到 30.0 厘米，服务会按样式和页面限制再收敛 |

### 推荐调用模式

#### 1. 客户端预渲染模式

这是 MD Viewer 推荐的调用方式：客户端先把 Mermaid、DrawIO、Excalidraw、KaTeX 等渲染为 PNG，再把 Markdown 和图片一起发给服务。优点是图表效果与预览一致，也不要求服务端安装浏览器渲染环境。

Markdown 中使用图片占位符：

```markdown
# 示例

下面是一张客户端已渲染图：

![](mdv__chart__aabbccdd__)
```

请求示例：

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

#### 2. 服务端渲染模式

只有 full 镜像支持服务端浏览器渲染。适合没有客户端预渲染能力的集成方，但效果可能与 MD Viewer 预览存在差异。

```bash
curl -X POST http://localhost:3179/convert \
  -H 'Content-Type: application/json' \
  -o output.docx \
  -d '{
    "markdown": "# 图表\n\n```mermaid\ngraph TD\n  A --> B\n```",
    "style": "standard",
    "renderCharts": true,
    "chartRenderers": ["mermaid"],
    "embedFont": false
  }'
```

如果当前是 slim 镜像并传入 `renderCharts: true`，返回 `400`：

```json
{
  "detail": {
    "error": "Server-side chart rendering requires full image (with playwright)",
    "code": "RENDER_UNAVAILABLE"
  }
}
```

#### 3. 纯 Markdown 模式

不传 `images` 且 `renderCharts=false` 时，服务按普通 Markdown 生成 DOCX。该模式适合无图表文档，或调用方已经接受代码块以文本形式保留。

```bash
curl -X POST http://localhost:3179/convert \
  -H 'Content-Type: application/json' \
  -o output.docx \
  -d '{
    "markdown": "# 标题\n\n正文\n\n| A | B |\n|---|---|\n| 1 | 2 |",
    "style": "report"
  }'
```

### `/convert` 响应

成功时：

- HTTP 状态码：`200`
- `Content-Type`: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- 响应体：DOCX 二进制

重要响应头：

| 响应头 | 说明 |
|---|---|
| `X-Service-Version` | 服务版本 |
| `X-Service-Mode` | 实际转换模式，常见值为 `clientRendered` 或 `serverRendered` |
| `X-Convert-Warnings` | JSON 字符串数组，包含字体降级、图片校验失败等 warning |
| `X-Charts-Rendered` | 已注入或渲染的图表/公式图片数量 |
| `X-Charts-Failed` | 校验失败或渲染失败数量 |
| `X-Min-Client-Version` | 服务要求的最低客户端版本 |

调用方建议：

- 即使状态码是 `200`，也应读取 `X-Convert-Warnings` 并展示给用户。
- `X-Charts-Failed` 大于 0 时，建议提示“部分图表未成功导出”。
- 下载文件名可由调用方自行决定；服务默认返回 `export.docx`。

### 错误响应

| 状态码 | 场景 | 响应特征 |
|---:|---|---|
| `400` | `style` 不在支持列表内 | `detail.code=STYLE_INVALID` |
| `400` | slim 镜像请求服务端图表渲染 | `detail.code=RENDER_UNAVAILABLE` |
| `401` | `API_KEY` 校验失败 | `detail=Invalid API key` |
| `422` | 请求字段不符合 schema，例如 `markdown` 为空、图片 ID 格式错误、字段过长 | FastAPI / Pydantic validation error |
| `429` | 超过限流 | SlowAPI rate limit error |
| `500` | DOCX 生成或图片注入异常 | `detail.code=INTERNAL` |

### 限制与兼容性建议

- `markdown` 最大 500000 字符。
- 单张 `pngBase64` 最大 2800000 字符。
- `referenceDocxBase64` 最大 20000000 字符。
- `/healthz.maxImagesPerRequest` 为 `null` 时表示服务端不设置固定图片数量上限，但仍受请求体大小、内存和超时限制。
- 默认限流是每分钟 30 次，可通过 `RATE_LIMIT_PER_MIN` 环境变量调整。
- 暴露到局域网或公网时必须配置 `API_KEY`，并建议放在 HTTPS 反向代理之后。

## 样式

- `standard`：通用文档
- `official`：正式公文
- `internal`：机关内部文件
- `report`：调研/分析报告

## 安全配置

默认建议只绑定本机地址：

```bash
-p 127.0.0.1:3179:3000
```

如果部署到局域网或公网：

- 设置 `API_KEY`
- 使用 HTTPS 反向代理
- 不要裸露无鉴权 HTTP 服务

示例：

```bash
docker run --rm \
  -p 127.0.0.1:3179:3000 \
  -e API_KEY="change-me" \
  mdviewer/docx-service:latest
```

环境变量示例见 `.env.example`。

## 验证

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest
```

Docker 验证：

```bash
docker build -t mdviewer/docx-service:dev-slim -f Dockerfile.slim .
docker run --rm -p 127.0.0.1:3179:3000 mdviewer/docx-service:dev-slim
curl http://localhost:3179/healthz
```

## 开源说明

- 主许可证：`LICENSE`
- 第三方依赖和字体声明：`NOTICE.md`
- 安全反馈和部署建议：`SECURITY.md`
- 本仓库不应提交私有文档、内部执行记录、本地绝对路径或未确认授权的字体文件。

## 已知限制

- DrawIO 服务端模式不渲染，MD Viewer 客户端预渲染模式可导出。
- KaTeX 当前优先保证 Word 中可见，不保证公式可编辑。
- 字体嵌入受 Office/WPS 支持和字体授权影响，服务会失败降级并返回 warning。
