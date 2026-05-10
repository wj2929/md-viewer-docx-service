import pytest

from app.url_safety import assert_safe_source_url


def test_local_friendly_accepts_localhost_markdown_url():
    assert_safe_source_url("http://localhost:8080/a.md", policy="local-friendly") is None


def test_local_friendly_accepts_internal_markdown_url():
    assert_safe_source_url("http://192.168.1.20/docs/a.markdown", policy="local-friendly") is None


def test_strict_rejects_localhost():
    with pytest.raises(ValueError):
        assert_safe_source_url("http://localhost:8080/a.md", policy="strict")


def test_strict_rejects_private_ip():
    with pytest.raises(ValueError):
        assert_safe_source_url("http://192.168.1.20/a.md", policy="strict")


def test_strict_rejects_metadata_ip():
    with pytest.raises(ValueError):
        assert_safe_source_url("http://169.254.169.254/latest/meta-data/a.md", policy="strict")


def test_strict_rejects_ipv6_loopback():
    with pytest.raises(ValueError):
        assert_safe_source_url("http://[::1]/a.md", policy="strict")


def test_strict_rejects_ipv6_unique_local():
    with pytest.raises(ValueError):
        assert_safe_source_url("http://[fd00::1]/a.md", policy="strict")


def test_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        assert_safe_source_url("file:///tmp/a.md", policy="local-friendly")


def test_allowlist_accepts_configured_host():
    assert_safe_source_url(
        "https://docs.example.com/demo.md",
        policy="allowlist",
        allowlist_hosts=["docs.example.com"],
    ) is None


def test_allowlist_rejects_unconfigured_host():
    with pytest.raises(ValueError):
        assert_safe_source_url(
            "https://evil.example.com/demo.md",
            policy="allowlist",
            allowlist_hosts=["docs.example.com"],
        )


def test_rejects_non_markdown_path_when_content_type_is_unknown():
    with pytest.raises(ValueError):
        assert_safe_source_url("https://example.com/index.html", policy="local-friendly")


def test_accepts_text_plain_override_for_non_md_path():
    assert_safe_source_url(
        "https://example.com/raw/123",
        policy="local-friendly",
        content_type="text/plain; charset=utf-8",
    ) is None
