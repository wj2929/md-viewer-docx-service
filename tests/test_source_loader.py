import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.source_loader import load_source_markdown
from app.source_models import ConvertSourceRequest


def test_load_source_markdown_returns_direct_markdown():
    req = ConvertSourceRequest(sourceType="markdown", markdown="# 标题")

    assert load_source_markdown(req) == "# 标题"


def test_load_source_markdown_fetches_url_source(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.end_headers()
            self.wfile.write("# 远程标题\n\n正文".encode("utf-8"))

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("MDV_SOURCE_URL_POLICY", "local-friendly")
        req = ConvertSourceRequest(
            sourceType="url",
            url=f"http://127.0.0.1:{server.server_port}/doc.md",
        )

        assert load_source_markdown(req) == "# 远程标题\n\n正文"
    finally:
        server.shutdown()
