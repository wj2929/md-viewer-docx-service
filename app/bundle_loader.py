import posixpath

from app.source_models import BundleResource, ConvertSourceRequest


class BundleLoadError(RuntimeError):
    pass


def normalize_bundle_path(path: str) -> str:
    raw = path.replace("\\", "/").strip()
    if not raw or raw.startswith("/") or raw.startswith("../") or "/../" in raw:
        raise ValueError(f"unsafe bundle path: {path}")
    normalized = posixpath.normpath(raw)
    if normalized in {".", ""} or normalized.startswith("../") or normalized == "..":
        raise ValueError(f"unsafe bundle path: {path}")
    return normalized.removeprefix("./")


def _resource_map(resources: list[BundleResource]) -> dict[str, BundleResource]:
    mapped = {}
    for resource in resources:
        mapped[normalize_bundle_path(resource.path)] = resource
    return mapped


def normalize_bundle_resources(resources: list[BundleResource]) -> list[dict]:
    normalized = []
    for resource in resources:
        item = resource.model_dump()
        item["path"] = normalize_bundle_path(resource.path)
        normalized.append(item)
    return normalized


def load_bundle_markdown(req: ConvertSourceRequest) -> str:
    if req.markdown:
        return req.markdown

    if not req.entryPath:
        raise BundleLoadError("bundle entryPath is required")

    entry_path = normalize_bundle_path(req.entryPath)
    resource = _resource_map(req.resources).get(entry_path)
    if not resource:
        raise BundleLoadError(f"bundle entry resource not found: {entry_path}")
    if resource.kind != "text" or resource.content is None:
        raise BundleLoadError(f"bundle entry resource is not text: {entry_path}")
    return resource.content
