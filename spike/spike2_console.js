/**
 * Spike-2 Benchmark: 在 md-viewer DevTools console 里粘贴运行
 *
 * 使用方法:
 *   1. npm run dev 启动 md-viewer
 *   2. 打开 DevTools (Cmd+Option+I)
 *   3. 把这段代码粘贴到 Console 里回车
 *   4. 等待结果输出（约 30-90s）
 */

const CHARTS = [
  { lang: "echarts", code: `{
  "title": {"text": "存储容量趋势"},
  "xAxis": {"type": "category", "data": ["1月","2月","3月","4月","5月","6月"]},
  "yAxis": {"type": "value", "name": "GB"},
  "series": [{"type": "line", "data": [120, 200, 150, 80, 70, 110]}]
}` },
  { lang: "mermaid", code: `graph LR
  A[用户请求] --> B[API网关]
  B --> C[业务服务]
  C --> D[(数据库)]
  C --> E[缓存]` },
  { lang: "mermaid", code: `sequenceDiagram
  participant U as 用户
  participant S as 服务
  participant D as 数据库
  U->>S: 请求数据
  S->>D: 查询
  D-->>S: 返回结果
  S-->>U: 响应` },
  { lang: "dot", code: `digraph G {
  rankdir=LR;
  node [shape=box];
  A [label="PVC"];
  B [label="PV"];
  C [label="StorageClass"];
  A -> B -> C;
}` },
  { lang: "markmap", code: `# CCE存储
## 块存储
### EVS
### 本地磁盘
## 文件存储
### SFS
### SFS Turbo
## 对象存储
### OBS` },
];

async function runBenchmark() {
  console.log('=== Spike-2 Chart Render Benchmark ===');
  console.log(`测试 ${CHARTS.length} 个图表代码块...`);

  const t0 = Date.now();
  const result = await window.api.benchmarkChartRender(CHARTS);
  const total = Date.now() - t0;

  console.log('\n结果:');
  console.table(result.results.map(r => ({
    lang: r.lang,
    '耗时(ms)': r.elapsed,
    'PNG大小(KB)': r.pngSize ? (r.pngSize / 1024).toFixed(1) : 0,
    状态: r.error ? '❌ ' + r.error.slice(0, 50) : '✓'
  })));

  const ok = result.results.filter(r => !r.error);
  const fail = result.results.filter(r => r.error);
  console.log(`\n总耗时: ${total}ms`);
  console.log(`成功: ${ok.length}/${result.results.length}`);
  if (ok.length > 0) {
    const avg = ok.reduce((s, r) => s + r.elapsed, 0) / ok.length;
    const max = Math.max(...ok.map(r => r.elapsed));
    console.log(`平均耗时: ${avg.toFixed(0)}ms, 最慢: ${max}ms`);
    console.log(`25张图预估总耗时: ${(avg * 25 / 1000).toFixed(1)}s`);
  }
  if (fail.length > 0) {
    console.warn(`失败 ${fail.length} 个:`, fail);
  }
}

runBenchmark();
