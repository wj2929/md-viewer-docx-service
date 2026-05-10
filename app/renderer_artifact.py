import json
from pathlib import Path

from pydantic import BaseModel, Field


SUPPORTED_RENDERER_SCHEMA = "1.0"


class RendererArtifactError(RuntimeError):
    pass


class RendererArtifactInfo(BaseModel):
    ok: bool
    version: str
    schemaVersion: str
    entryHtml: str
    assetsDir: str
    supportedCharts: list[str] = Field(default_factory=list)
    minDocxServiceVersion: str


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
    if info.schemaVersion != SUPPORTED_RENDERER_SCHEMA:
        raise RendererArtifactError(
            f"incompatible renderer schema: {info.schemaVersion}, expected {SUPPORTED_RENDERER_SCHEMA}"
        )

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
