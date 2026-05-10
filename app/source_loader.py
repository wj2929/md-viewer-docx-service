import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler

from app.bundle_loader import BundleLoadError, load_bundle_markdown
from app.source_models import ConvertSourceRequest
from app.url_safety import assert_safe_source_url


MAX_SOURCE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 3


class SourceLoadError(RuntimeError):
    pass


def _source_policy() -> str:
    return os.environ.get("MDV_SOURCE_URL_POLICY", "local-friendly")


def _allowlist_hosts() -> list[str]:
    raw = os.environ.get("MDV_SOURCE_URL_ALLOWLIST", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, *, policy: str, allowlist_hosts: list[str]):
        self.policy = policy
        self.allowlist_hosts = allowlist_hosts
        self.redirect_count = 0
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > MAX_REDIRECTS:
            raise SourceLoadError("source url redirected too many times")
        target_url = urljoin(req.full_url, newurl)
        assert_safe_source_url(
            target_url,
            policy=self.policy,
            allowlist_hosts=self.allowlist_hosts,
            validate_markdown_hint=False,
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_markdown_url(url: str) -> str:
    policy = _source_policy()
    allowlist_hosts = _allowlist_hosts()
    assert_safe_source_url(
        url,
        policy=policy,
        allowlist_hosts=allowlist_hosts,
        validate_markdown_hint=False,
    )

    opener = build_opener(SafeRedirectHandler(policy=policy, allowlist_hosts=allowlist_hosts))
    request = Request(url, headers={"Accept": "text/markdown, text/plain;q=0.9, */*;q=0.1"})
    try:
        with opener.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            assert_safe_source_url(
                final_url,
                policy=policy,
                allowlist_hosts=allowlist_hosts,
                content_type=content_type,
            )
            data = response.read(MAX_SOURCE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise SourceLoadError(str(exc)) from exc

    if len(data) > MAX_SOURCE_BYTES:
        raise SourceLoadError("source markdown exceeds 5MB limit")

    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceLoadError("source markdown must be utf-8 text") from exc


def load_source_markdown(req: ConvertSourceRequest) -> str:
    if req.sourceType == "markdown":
        return req.markdown or ""
    if req.sourceType == "url":
        return _fetch_markdown_url(req.url or "")
    if req.sourceType == "bundle":
        try:
            return load_bundle_markdown(req)
        except BundleLoadError as exc:
            raise SourceLoadError(str(exc)) from exc
    raise SourceLoadError(f"unsupported sourceType: {req.sourceType}")
