from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


FORMAL_STYLES_WITHOUT_DEFAULT_FOOTER = {"official", "internal", "report"}


class BundleResource(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
    kind: Literal["text", "binary"]
    content: Optional[str] = Field(default=None, max_length=5_000_000)
    base64: Optional[str] = Field(default=None, max_length=7_000_000)
    mediaType: str = Field(default="application/octet-stream", max_length=120)
    size: int = Field(..., ge=0, le=5_000_000)

    @model_validator(mode="after")
    def validate_content(self):
        if self.kind == "text" and self.content is None:
            raise ValueError("content is required for text bundle resources")
        if self.kind == "binary" and self.base64 is None:
            raise ValueError("base64 is required for binary bundle resources")
        return self


class ConvertSourceRequest(BaseModel):
    sourceType: Literal["markdown", "url", "bundle"]
    markdown: Optional[str] = Field(default=None, min_length=1, max_length=500_000)
    url: Optional[str] = Field(default=None, max_length=2048)
    entryPath: Optional[str] = Field(default=None, max_length=1024)
    resources: list[BundleResource] = Field(default_factory=list)
    style: str = Field(default="standard", max_length=20)
    renderMode: Literal["fullFidelity"] = "fullFidelity"
    fallbackMode: Literal["partial", "fail"] = "partial"
    theme: Literal["light", "dark"] = "light"
    embedFont: bool = False
    footerText: Optional[str] = Field(default=None, max_length=200)
    debugManifest: bool = False
    clientVersion: Optional[str] = Field(default=None, max_length=20)
    referenceDocxBase64: Optional[str] = Field(default=None, max_length=20_000_000)

    @model_validator(mode="after")
    def validate_markdown_source(self):
        if "footerText" not in self.model_fields_set:
            self.footerText = None if self.style in FORMAL_STYLES_WITHOUT_DEFAULT_FOOTER else "由 MD Viewer 生成 · github.com/wj2929/md-viewer"
        if self.sourceType == "markdown" and not self.markdown:
            raise ValueError("markdown is required when sourceType=markdown")
        if self.sourceType == "url" and not self.url:
            raise ValueError("url is required when sourceType=url")
        if self.sourceType == "bundle" and not self.markdown and not self.entryPath:
            raise ValueError("markdown or entryPath is required when sourceType=bundle")
        return self
