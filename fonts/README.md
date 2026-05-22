# Fonts

本目录用于存放 `md-viewer-docx-service` 在 Docker 镜像和本地开发中可扫描的字体文件。服务会用这些字体改善中文 DOCX 排版，并在调用方设置 `embedFont=true` 时按需把 DOCX 实际引用的匹配字体写入文件。

## 默认字体

Dockerfile.slim 和 Dockerfile.full 都会安装 Debian 的 `fonts-noto-cjk` 包，并执行：

```dockerfile
COPY fonts/ /usr/share/fonts/truetype/custom/
RUN fc-cache -fv
```

当前仓库内置的开源兜底字体：

| 文件名 | 字体名 | 用途 | 许可证 |
|---|---|---|---|
| `NotoSansCJKsc-Regular.otf` | Noto Sans CJK SC | 中文排版与字体嵌入兜底 | SIL Open Font License 1.1 |

`preview` 样式会优先使用该内置字体，而不是 macOS 上的 `PingFang SC` 等系统字体。这样本地服务和远程 Docker 服务生成的 DOCX 更一致，也能在 `embedFont=true` 时默认完成字体嵌入。

授权文本见 `OFL.txt`。第三方声明见仓库根目录 `NOTICE.md`。

## 字体扫描顺序

服务会从以下来源查找 `.ttf`、`.otf`、`.ttc` 候选字体：

1. `MD_VIEWER_DOCX_FONT_PATHS` 指定的字体文件。
2. 代码内置的候选字体路径。
3. `MD_VIEWER_DOCX_FONT_DIRS` 指定的字体目录。
4. 本目录、Docker 自定义字体目录、Linux Noto 字体目录。

服务不会默认扫描 macOS 系统字体目录。Docker 部署时也只会读取容器内置字体或显式挂载到容器内的授权字体目录。

环境变量支持冒号分隔，也兼容逗号分隔：

```bash
export MD_VIEWER_DOCX_FONT_PATHS="/path/to/custom.ttf:/path/to/another.ttc"
export MD_VIEWER_DOCX_FONT_DIRS="/path/to/font-dir"
```

## 可选商业或系统字体

如果部署环境有合法授权，可以把下列字体放入私有目录，或通过 `MD_VIEWER_DOCX_FONT_PATHS` / `MD_VIEWER_DOCX_FONT_DIRS` 挂载给服务。公开仓库、公开 Release、公开 Docker 镜像和自动下载脚本不应分发这些未确认再分发授权的字体：

| 文件名示例 | 字体名 | 常见用途 | 授权说明 |
|---|---|---|---|
| `msyh.ttc` | 微软雅黑 | `standard` 样式 | Windows 系统字体，需遵循 Microsoft 授权 |
| `simhei.ttf` | 黑体 | `official`、`internal`、`report` 标题 | Windows 系统字体，需遵循 Microsoft 授权 |
| `simsun.ttc` | 宋体 | `internal`、`report` 正文 | Windows 系统字体，需遵循 Microsoft 授权 |
| `simfang.ttf` | 仿宋_GB2312 | `official` 正文 | Windows 系统字体，需遵循 Microsoft 授权 |
| `simkai.ttf` | 楷体_GB2312 | `official` 二级标题 | Windows 系统字体，需遵循 Microsoft 授权 |
| `FZXBSJW.TTF` | 方正小标宋简体 | 公文标题 | 需遵循方正字库授权 |

不要把未确认授权的商业字体提交到开源仓库。推荐在私有部署环境中通过 Docker volume 或环境变量挂载，并把私有字体目录加入 `.gitignore`。

## Docker 挂载示例

```bash
docker run --rm \
  -p 127.0.0.1:3179:3000 \
  -v /path/to/fonts:/opt/mdv-fonts:ro \
  -e MD_VIEWER_DOCX_FONT_DIRS=/opt/mdv-fonts \
  mdviewer/docx-service:latest
```

## 字体嵌入行为

- 只有请求中设置 `embedFont=true` 时才会尝试嵌入字体。
- 服务会先读取 DOCX 内容中的字体引用，只嵌入与实际引用匹配的候选字体，避免把整个字体目录打包进 DOCX。
- 找不到可嵌入字体时，服务会保留字体名称并返回 warning，DOCX 仍会生成。warning 会提示普通用户关闭“嵌入字体”，或提示服务管理员通过 `MD_VIEWER_DOCX_FONT_DIRS` / `MD_VIEWER_DOCX_FONT_PATHS` 挂载授权字体。
- 字体是否能被 Word / WPS 正确识别，还受字体文件格式、Office 支持情况和字体授权位影响。
- 服务当前采用保守策略：优先保证 DOCX 可打开，字体嵌入失败时降级并报告 warning。

## 开源注意事项

- 本目录可以提交开源授权明确的字体及其许可证文本。
- 本目录不应提交 Windows 系统字体、商业字体、内部字体包或无法确认授权来源的字体。
- 新增字体时请同步更新 `NOTICE.md` 和本 README。
