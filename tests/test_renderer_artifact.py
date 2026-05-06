import json

import pytest

from app.renderer_artifact import RendererArtifactError, inspect_renderer_artifact


def test_inspect_renderer_artifact_reports_manifest(tmp_path):
    artifact_dir = tmp_path / "server-render"
    assets_dir = artifact_dir / "assets"
    assets_dir.mkdir(parents=True)
    (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "1.0.0",
        "schemaVersion": "1.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid"],
        "minDocxServiceVersion": "0.1.0",
    }), encoding="utf-8")

    info = inspect_renderer_artifact(artifact_dir, service_version="0.1.0")

    assert info.ok is True
    assert info.version == "1.0.0"
    assert info.schemaVersion == "1.0"
    assert info.supportedCharts == ["mermaid"]


def test_inspect_renderer_artifact_rejects_missing_entry_html(tmp_path):
    artifact_dir = tmp_path / "server-render"
    (artifact_dir / "assets").mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "1.0.0",
        "schemaVersion": "1.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid"],
        "minDocxServiceVersion": "0.1.0",
    }), encoding="utf-8")

    with pytest.raises(RendererArtifactError):
        inspect_renderer_artifact(artifact_dir, service_version="0.1.0")


def test_inspect_renderer_artifact_rejects_incompatible_schema(tmp_path):
    artifact_dir = tmp_path / "server-render"
    assets_dir = artifact_dir / "assets"
    assets_dir.mkdir(parents=True)
    (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "1.0.0",
        "schemaVersion": "2.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid"],
        "minDocxServiceVersion": "0.1.0",
    }), encoding="utf-8")

    with pytest.raises(RendererArtifactError):
        inspect_renderer_artifact(artifact_dir, service_version="0.1.0")


def test_inspect_renderer_artifact_compares_semver_versions(tmp_path):
    artifact_dir = tmp_path / "server-render"
    assets_dir = artifact_dir / "assets"
    assets_dir.mkdir(parents=True)
    (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "1.0.0",
        "schemaVersion": "1.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid"],
        "minDocxServiceVersion": "0.10.0",
    }), encoding="utf-8")

    with pytest.raises(RendererArtifactError):
        inspect_renderer_artifact(artifact_dir, service_version="0.9.0")
