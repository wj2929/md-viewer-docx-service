# 第三方声明 / Notices

本服务采用 MIT License，详见 `LICENSE`。

## 运行时依赖

Python 依赖记录在 `requirements.txt` 和 `requirements-full.txt`。
JavaScript 渲染器依赖记录在 `package.json` 和 `package-lock.json`。

主要运行时组件包括：

| 组件 | 许可证 | 用途 |
|---|---|---|
| FastAPI | MIT | HTTP API |
| Uvicorn | BSD-3-Clause | ASGI 服务 |
| python-docx | MIT | DOCX 生成 |
| Pillow | HPND | 图片处理 |
| lxml | BSD-3-Clause | XML 处理 |
| Pydantic | MIT | 请求校验 |
| SlowAPI | MIT | 限流 |
| Playwright | Apache-2.0 | 可选的浏览器图表渲染 |
| Mermaid | MIT | 可选的服务端图表渲染 |
| ECharts | Apache-2.0 | 可选的服务端图表渲染 |
| KaTeX | MIT | 可选的公式渲染 |
| Markmap | MIT | 可选的思维导图渲染 |
| D3 | ISC | 可选图表渲染依赖 |

## 字体

仓库内置 `fonts/NotoSansCJKsc-Regular.otf` 作为 CJK 兜底字体。
该字体基于 SIL Open Font License 1.1 分发，授权文本见 `fonts/OFL.txt`。

服务也可以使用用户本地提供的 Microsoft 或方正字体。
这些字体默认不随仓库分发；只有在你拥有合法使用和再分发权利时，才应将它们加入自己的部署环境。

## 发布检查清单

- `package-lock.json` 应保持使用公共 npm registry。
- 不要提交私有文档样例、本地绝对路径或内部执行记录。
- 未确认再分发授权前，不要发布包含专有字体的镜像。
