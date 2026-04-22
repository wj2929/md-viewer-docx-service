// Spike-2 Benchmark
var CHARTS = [
  {lang: "echarts", code: JSON.stringify({"title":{"text":"test"},"xAxis":{"type":"category","data":["A","B","C"]},"yAxis":{"type":"value"},"series":[{"type":"bar","data":[10,20,30]}]})},
  {lang: "mermaid", code: "graph LR\n  A --> B"},
  {lang: "mermaid", code: "sequenceDiagram\n  A ->> B: hello\n  B -->> A: world"},
  {lang: "dot", code: "digraph G { A -> B; }"},
  {lang: "markmap", code: "# Root\n## A\n## B"}
];

window.api.benchmarkChartRender(CHARTS).then(function(result) {
  console.log("=== Spike-2 Results ===");
  result.results.forEach(function(r, i) {
    console.log("[" + i + "] " + r.lang + " | " + r.elapsed + "ms | " + (r.pngSize ? (r.pngSize/1024).toFixed(1) + "KB" : "FAIL: " + r.error));
  });
  var ok = result.results.filter(function(r) { return !r.error; });
  var avg = ok.length ? ok.reduce(function(s, r) { return s + r.elapsed; }, 0) / ok.length : 0;
  console.log("---");
  console.log("total: " + result.totalElapsed + "ms");
  console.log("success: " + ok.length + "/" + result.results.length);
  console.log("avg per chart: " + avg.toFixed(0) + "ms");
  console.log("estimated 25 charts: " + (avg * 25 / 1000).toFixed(1) + "s");
});
