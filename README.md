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

## 已知限制

- DrawIO 服务端模式不渲染，MD Viewer 客户端预渲染模式可导出。
- KaTeX 当前优先保证 Word 中可见，不保证公式可编辑。
- 字体嵌入受 Office/WPS 支持和字体授权影响，服务会失败降级并返回 warning。
