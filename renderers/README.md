# Renderer Runtime

本目录保存 `/convert-source` 使用的服务端浏览器渲染入口。

`md-viewer-docx-service` 自身提供 FastAPI、Docker 镜像、Markdown 输入读取、DOCX 生成和健康检查；`md-viewer` 不作为运行时 HTTP 服务，只在构建期产出 browser-only renderer artifact。

## 目录结构

```text
renderers/
  README.md
  mdv-renderer-cli.mjs
  dist/server-render/        # 构建产物，本地生成，不提交仓库
```

`renderers/dist/` 已在 `.gitignore` 中忽略。开源仓库应提交 `mdv-renderer-cli.mjs`，但不应提交本地生成的 renderer artifact。

## Renderer CLI

`mdv-renderer-cli.mjs` 是 Python 服务调用的 Node + Playwright 入口。它从 stdin 读取 JSON payload，启动本地临时 HTTP 服务加载 artifact 中的 `server-render.html`，截图后向 stdout 输出渲染结果 JSON。

默认 CLI 路径：

```text
/app/renderers/mdv-renderer-cli.mjs
```

可通过环境变量覆盖：

```bash
export MDV_RENDER_CLI=/path/to/mdv-renderer-cli.mjs
```

## Artifact 要求

运行时默认读取：

```text
/app/renderers/dist/server-render
```

该目录必须来自 `md-viewer` 的 renderer build artifact，至少包含：

```text
manifest.json
server-render.html
assets/
```

`manifest.json` 需要包含：

| 字段 | 说明 |
|---|---|
| `schemaVersion` | renderer 契约版本，当前服务支持 `1.x` 和 `2.x` |
| `version` | renderer artifact 版本 |
| `entryHtml` | 入口 HTML，通常为 `server-render.html` |
| `assetsDir` | 静态资源目录，通常为 `assets` |
| `supportedCharts` | browser artifact 支持截图的图表类型，保留给旧客户端和诊断 UI |
| `minDocxServiceVersion` | artifact 要求的最低 DOCX 服务版本 |
| `renderers` | schema 2.0 新增，完整 renderer 能力、selector 与替换策略清单 |

`/readyz` 会校验 artifact 是否存在、schema 是否兼容、入口 HTML 与 assets 目录是否完整。

## Renderer 能力矩阵

当前 full renderer artifact 目标支持：

| 类型 | fence / 引用 | 说明 |
|---|---|---|
| Mermaid | `mermaid` | 本地浏览器渲染 |
| KaTeX | `$...$`、`$$...$$` | 公式截图 |
| ECharts | `echarts` | SVG/DOM 截图 |
| Markmap | `markmap` | SVG 截图 |
| Graphviz | `graphviz`、`dot` | WASM/SVG |
| DrawIO | `drawio`、`dio` | DOM 渲染后截图 |
| Infographic | `infographic` | SVG 渲染 |
| Excalidraw | `excalidraw`、`.excalidraw` | 代码块和 bundle 文件引用 |
| PlantUML | `plantuml`、`puml` | 由服务后处理或配置的 PlantUML 服务渲染 |
| Vega-Lite | `vega-lite`、`vegalite` | 仅允许内联数据，阻止外部 `data.url` |
| D2 | `d2` | 本地离线 SVG 渲染 |
| BPMN | `bpmn`、`.bpmn` | fenced XML 和 bundle 文件引用 |
| WaveDrom | `wavedrom` | 本地 JS 渲染 |
| C4-PlantUML | `c4`、`c4plantuml` | 复用 PlantUML 链路 |

schema 2.0 下，服务会比较 manifest `renderers[]` 与 Python allowlist。manifest 声明但 allowlist 未允许的 renderer 不会被静默启用；allowlist 中存在但 manifest 缺失的 renderer 也会在 `/readyz.rendererWarnings` 中提示。

## 本地生成 artifact

默认脚本假设 `md-viewer` 与 `md-viewer-docx-service` 是同级目录：

```bash
cd ../md-viewer
npm install
npm run build
cd ../md-viewer-docx-service
scripts/sync-renderer-artifact.sh
```

如果目录不同，可以显式指定：

```bash
MD_VIEWER_ROOT=/path/to/md-viewer scripts/sync-renderer-artifact.sh
```

也可以直接指定源和目标：

```bash
MDV_RENDER_ARTIFACT_SOURCE=/path/to/md-viewer/out/renderer \
MDV_RENDER_ARTIFACT_TARGET="$PWD/renderers/dist/server-render" \
scripts/sync-renderer-artifact.sh
```

本地运行服务时可设置：

```bash
export MDV_RENDER_ARTIFACT_DIR="$PWD/renderers/dist/server-render"
```

## Docker 构建关系

full 镜像会复制本目录：

```dockerfile
COPY renderers/ ./renderers/
```

因此从源码构建 full 镜像前，需要先同步 `renderers/dist/server-render`。如果未同步，容器仍可启动，但 `/readyz` 会返回 `503`，`/convert-source` 无法完成完整服务端渲染。

## 运行时环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MDV_RENDER_ARTIFACT_DIR` | `/app/renderers/dist/server-render` | renderer artifact 目录 |
| `MDV_RENDER_CLI` | `/app/renderers/mdv-renderer-cli.mjs` | renderer CLI 路径 |
| `MDV_RENDER_TIMEOUT_MS` | `60000` | 浏览器页面渲染超时 |
| `MDV_RENDER_CLI_GRACE_MS` | `max(15000, MDV_RENDER_TIMEOUT_MS)` | CLI 子进程额外等待时间 |
| `MDV_RENDER_NETWORK_POLICY` | `local-friendly` | 浏览器渲染阶段外部资源访问策略 |
| `MDV_RENDER_ALLOWLIST_HOSTS` | 空 | `allowlist` 策略允许访问的主机 |
| `MDV_RENDER_CONCURRENCY` | `1` | `/readyz` 暴露的渲染并发配置 |

当前浏览器网络策略：

| 策略 | 行为 |
|---|---|
| `blocked` | 仅允许 artifact 自身资源、`data:` 和 `blob:` |
| `local-friendly` | 在 `blocked` 基础上允许 `127.0.0.1`、`localhost`、`::1` |
| `allowlist` | 在 `blocked` 基础上允许 `MDV_RENDER_ALLOWLIST_HOSTS` 中的主机 |

## 故障判断

- `/readyz` 返回 `503` 且提示 `renderer manifest not found`：artifact 未同步或 `MDV_RENDER_ARTIFACT_DIR` 指错。
- `/readyz` 返回 `503` 且提示 `incompatible renderer schema`：`md-viewer` 产物与当前服务版本不兼容。
- `/convert-source` 返回 `502 RENDER_FAILED`：请求设置了 `fallbackMode=fail`，且 renderer 返回 `partial`、`failed` 或 `timeout`。
- 图表引用远程资源失败：检查 `MDV_RENDER_NETWORK_POLICY` 和 `MDV_RENDER_ALLOWLIST_HOSTS`。

## 开源注意事项

- 不提交 `renderers/dist/` 构建产物。
- 不提交包含私有域名、内网路径或访问凭据的 renderer artifact。
- 发布 full 镜像时应通过 CI 生成 artifact，并用 `/readyz` 做 smoke test。
