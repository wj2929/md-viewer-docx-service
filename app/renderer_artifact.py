import json
from pathlib import Path

from pydantic import BaseModel, Field


SUPPORTED_RENDERER_SCHEMA_MAJORS = {"1", "2"}
SUPPORTED_RENDERER_SCHEMA_VERSION = "2.0"
DOCX_SERVICE_RENDERER_ALLOWLIST = {
    "mermaid",
    "katex",
    "excalidraw",
    "drawio",
    "echarts",
    "markmap",
    "graphviz",
    "infographic",
    "plantuml",
    "vega-lite",
    "d2",
    "bpmn",
    "wavedrom",
    "c4plantuml",
}


class RendererArtifactError(RuntimeError):
    pass


class RendererManifestEntry(BaseModel):
    type: str
    displayName: str | None = None
    capabilities: dict = Field(default_factory=dict)


class RendererArtifactInfo(BaseModel):
    ok: bool
    version: str
    schemaVersion: str
    entryHtml: str
    assetsDir: str
    supportedCharts: list[str] = Field(default_factory=list)
    minDocxServiceVersion: str
    renderers: list[RendererManifestEntry] = Field(default_factory=list)
    rendererWarnings: list[dict] = Field(default_factory=list)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = []
    for part in version.split("."):
        numeric = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(numeric or "0"))
    return tuple(parts)


def _version_greater(left: str, right: str) -> bool:
    left_parts = _version_tuple(left)
    right_parts = _version_tuple(right)
    width = max(len(left_parts), len(right_parts))
    return left_parts + (0,) * (width - len(left_parts)) > right_parts + (0,) * (width - len(right_parts))


def _schema_major(schema_version: str) -> str:
    return schema_version.split(".", 1)[0]


def _renderer_warnings(info: RendererArtifactInfo) -> list[dict]:
    if _schema_major(info.schemaVersion) != "2":
        return []

    manifest_types = {renderer.type for renderer in info.renderers} or set(info.supportedCharts)
    warnings: list[dict] = []

    if _version_greater(info.schemaVersion, SUPPORTED_RENDERER_SCHEMA_VERSION):
        warnings.append({
            "code": "RENDERER_SCHEMA_MINOR_NEWER",
            "schemaVersion": info.schemaVersion,
            "supportedSchemaVersion": SUPPORTED_RENDERER_SCHEMA_VERSION,
            "reason": f"renderer schema {info.schemaVersion} is newer than docx-service schema {SUPPORTED_RENDERER_SCHEMA_VERSION}; unknown fields are ignored",
        })

    for renderer_type in sorted(manifest_types - DOCX_SERVICE_RENDERER_ALLOWLIST):
        warnings.append({
            "code": "RENDERER_MANIFEST_NOT_ALLOWLISTED",
            "rendererType": renderer_type,
            "reason": f"renderer {renderer_type} is declared by manifest but blocked by docx-service allowlist",
        })

    for renderer_type in sorted(DOCX_SERVICE_RENDERER_ALLOWLIST - manifest_types):
        warnings.append({
            "code": "RENDERER_ALLOWLIST_NOT_IN_MANIFEST",
            "rendererType": renderer_type,
            "reason": f"renderer {renderer_type} is allowed by docx-service but absent from manifest",
        })

    return warnings


def inspect_renderer_artifact(
    artifact_dir: Path,
    *,
    service_version: str,
) -> RendererArtifactInfo:
    artifact_dir = artifact_dir.resolve()
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.exists():
        raise RendererArtifactError(f"renderer manifest not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RendererArtifactError(f"renderer manifest is invalid JSON: {exc}") from exc

    info = RendererArtifactInfo(ok=True, **manifest)
    if _schema_major(info.schemaVersion) not in SUPPORTED_RENDERER_SCHEMA_MAJORS:
        raise RendererArtifactError(
            f"incompatible renderer schema: {info.schemaVersion}, supported majors {sorted(SUPPORTED_RENDERER_SCHEMA_MAJORS)}"
        )

    info.rendererWarnings = _renderer_warnings(info)

    entry_path = artifact_dir / info.entryHtml
    if not entry_path.exists():
        raise RendererArtifactError(f"renderer entry html not found: {entry_path}")

    assets_path = artifact_dir / info.assetsDir
    if not assets_path.is_dir():
        raise RendererArtifactError(f"renderer assets directory not found: {assets_path}")

    if _version_greater(info.minDocxServiceVersion, service_version):
        raise RendererArtifactError(
            f"renderer requires docx service {info.minDocxServiceVersion}, current {service_version}"
        )

    return info
