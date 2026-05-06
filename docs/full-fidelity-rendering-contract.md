# Full Fidelity Rendering Contract

## Current Phase

Current implementation supports Markdown source input, Markdown URL input, bundle input, Mermaid chart screenshot injection, KaTeX formula screenshot injection, ECharts screenshot injection, Markmap screenshot injection, Graphviz screenshot injection, DrawIO code-block screenshot injection, Infographic screenshot injection, PlantUML/PUML image injection, and bundle `.excalidraw` file-reference screenshot injection.

## Service Boundary

`md-viewer` does not provide an HTTP service. It only produces the browser-only renderer artifact at build time.

`md-viewer-docx-service` owns the Docker image, FastAPI endpoints, runtime configuration, source loading, renderer invocation, DOCX generation, and health checks.

## Renderer Artifact

The renderer artifact directory must contain:

- `manifest.json`
- `server-render.html`
- `assets/`

The service must validate:

- `schemaVersion`
- `version`
- `minDocxServiceVersion`
- artifact hash when `MDV_RENDER_ARTIFACT_SHA256` is set

If the artifact is missing or incompatible, `/readyz` returns 503 and `/convert-source` returns `RENDERER_SCHEMA_INCOMPATIBLE`.

## API Defaults

- `sourceType` has no default and must be explicit.
- `renderMode` defaults to `fullFidelity`.
- `style` defaults to `standard`.
- `theme` defaults to `light`.
- `fallbackMode` defaults to `partial`.

## Source Models

### Markdown

Use `sourceType=markdown` when the caller already has Markdown text.

### URL

Use `sourceType=url` when the caller has a reachable Markdown URL. URL mode reads Markdown text only. It does not export a web page, run page JavaScript, inherit browser login state, or automatically crawl related resources.

The default URL source policy is `local-friendly`, intended for trusted local and internal automation. Public or shared deployments should set `MDV_SOURCE_URL_POLICY=strict` or `allowlist`.

### Bundle

Use `sourceType=bundle` when Markdown has relative images, `.excalidraw` references, DrawIO XML, or other resources. Bundle resources are explicit structured entries with path, kind, content or base64, media type, and decoded size.

## Warning Format

Warnings use structured `code`, `severity`, `title`, `message`, `detail`, `action`, `fallback`, `location`, `source`, `renderer`, and `recoverable` fields.

## Result Visibility

`/convert-source` returns summary headers and may return a debug manifest when `debugManifest=true`.

The debug manifest must not contain full Markdown source.

## Fidelity Levels

| Level | Meaning | Examples |
|---|---|---|
| `visual-snapshot` | Browser-rendered block is injected as an image | Mermaid, KaTeX, ECharts, Markmap, Graphviz, DrawIO, Infographic, Excalidraw |
| `service-rendered-image` | Service-rendered block is injected as an image outside the browser artifact | PlantUML/PUML |
| `style-mapped` | Markdown structure is mapped to DOCX styles | headings, paragraphs, lists, tables |
| `not-promised` | Pixel-level browser CSS parity is not guaranteed | interactive state, dynamic page behavior |

DOCX output is not a full browser screenshot. The full fidelity path promises high-fidelity screenshots for supported chart blocks and DOCX style mapping for the rest of the Markdown document.

`rendererSupportedCharts` reports only the browser artifact capabilities. PlantUML/PUML is rendered by `md-viewer-docx-service` after the browser artifact returns, because the browser renderer normally blocks external network requests in server mode.

## Capability Matrix

| Capability | Status |
|---|---|
| Markdown source | supported |
| Markdown URL source | supported |
| Mermaid screenshot | supported |
| KaTeX screenshot | supported |
| ECharts screenshot | supported |
| Markmap screenshot | supported |
| Graphviz screenshot | supported |
| DrawIO code block screenshot | supported |
| PlantUML/PUML image injection | supported |
| Bundle source | supported |
| Excalidraw file reference via bundle | supported |
