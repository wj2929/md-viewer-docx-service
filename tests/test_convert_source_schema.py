import pytest
from pydantic import ValidationError

from app.source_models import ConvertSourceRequest


def test_markdown_source_request_accepts_plain_markdown():
    req = ConvertSourceRequest(sourceType="markdown", markdown="# 标题", style="preview")

    assert req.sourceType == "markdown"
    assert req.renderMode == "fullFidelity"
    assert req.fallbackMode == "partial"


def test_source_type_is_required():
    with pytest.raises(ValidationError):
        ConvertSourceRequest(markdown="# 标题")


def test_url_source_request_accepts_markdown_url():
    req = ConvertSourceRequest(sourceType="url", url="https://example.com/a.md")

    assert req.sourceType == "url"
    assert req.url == "https://example.com/a.md"


def test_debug_manifest_defaults_to_false():
    req = ConvertSourceRequest(sourceType="markdown", markdown="# 标题")

    assert req.debugManifest is False


def test_footer_text_can_be_disabled_with_null():
    req = ConvertSourceRequest(sourceType="markdown", markdown="# 标题", footerText=None)

    assert req.footerText is None
