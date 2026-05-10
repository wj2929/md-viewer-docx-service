import pytest

from app.bundle_loader import load_bundle_markdown, normalize_bundle_path
from app.source_models import BundleResource, ConvertSourceRequest


@pytest.mark.parametrize("path", ["/abs.md", "../escape.md", "a/../../b.md", ""])
def test_rejects_unsafe_bundle_paths(path):
    with pytest.raises(ValueError):
        normalize_bundle_path(path)


def test_accepts_posix_relative_path():
    assert normalize_bundle_path("./docs/readme.md") == "docs/readme.md"


def test_load_bundle_markdown_from_inline_markdown():
    req = ConvertSourceRequest(
        sourceType="bundle",
        markdown="# 内联",
        resources=[],
    )

    assert load_bundle_markdown(req) == "# 内联"


def test_load_bundle_markdown_from_entry_resource():
    req = ConvertSourceRequest(
        sourceType="bundle",
        entryPath="docs/readme.md",
        resources=[
            BundleResource(
                path="docs/readme.md",
                kind="text",
                content="# 入口",
                mediaType="text/markdown",
                size=8,
            )
        ],
    )

    assert load_bundle_markdown(req) == "# 入口"


def test_bundle_resource_binary_requires_base64():
    with pytest.raises(ValueError):
        BundleResource(
            path="images/a.png",
            kind="binary",
            mediaType="image/png",
            size=8,
        )
