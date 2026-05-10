# Renderer Runtime Decision

## Phase 0

Use a one-shot Node CLI to prove correctness and simplify failure isolation.

The current one-shot path supports:

- Markdown source
- Markdown URL source
- Bundle source
- Mermaid screenshots
- KaTeX screenshots
- ECharts screenshots
- Markmap screenshots
- Graphviz screenshots
- DrawIO code block screenshots
- Excalidraw file references from bundle resources

## Phase 1 Decision Gate

Before expanding to more browser-heavy renderers, compare:

| Option | Pros | Cons | Decision |
|---|---|---|---|
| one-shot CLI | simple isolation | slow cold start | keep as baseline and fallback |
| browser pool | faster repeated renders | needs lifecycle management | preferred if p95 improves by 30% |
| long-lived Node renderer | best latency | more protocol work | evaluate after browser pool |

## Required Decision

If one-shot CLI p95 exceeds 10 seconds for a one-chart document in Docker, implement browser pool before expanding more renderers.

Keep `MDV_RENDER_SUBPROCESS_MODE=one-shot` available as a fallback even after a pool is added.
