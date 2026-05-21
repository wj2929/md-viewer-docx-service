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
        "schemaVersion": "3.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid"],
        "minDocxServiceVersion": "0.1.0",
    }), encoding="utf-8")

    with pytest.raises(RendererArtifactError):
        inspect_renderer_artifact(artifact_dir, service_version="0.1.0")


def test_inspect_renderer_artifact_accepts_schema_2_renderer_plugins(tmp_path):
    artifact_dir = tmp_path / "server-render"
    assets_dir = artifact_dir / "assets"
    assets_dir.mkdir(parents=True)
    (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "2.1.0",
        "schemaVersion": "2.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid", "vega-lite", "d2", "bpmn", "wavedrom", "c4plantuml"],
        "minDocxServiceVersion": "0.2.0",
        "renderers": [
            {
                "type": "mermaid",
                "displayName": "Mermaid",
                "capabilities": {"docxService": {"state": "supported"}},
            },
            {
                "type": "vega-lite",
                "displayName": "Vega-Lite",
                "capabilities": {"docxService": {"state": "supported"}},
            },
            {"type": "d2", "displayName": "D2", "capabilities": {"docxService": {"state": "supported"}}},
            {"type": "bpmn", "displayName": "BPMN", "capabilities": {"docxService": {"state": "supported"}}},
            {"type": "wavedrom", "displayName": "WaveDrom", "capabilities": {"docxService": {"state": "supported"}}},
            {"type": "c4plantuml", "displayName": "C4-PlantUML", "capabilities": {"docxService": {"state": "supported"}}},
        ],
    }), encoding="utf-8")

    info = inspect_renderer_artifact(artifact_dir, service_version="0.2.0")

    assert info.schemaVersion == "2.0"
    assert [renderer.type for renderer in info.renderers] == ["mermaid", "vega-lite", "d2", "bpmn", "wavedrom", "c4plantuml"]
    assert not any(warning["code"] == "RENDERER_MANIFEST_NOT_ALLOWLISTED" for warning in info.rendererWarnings)


def test_inspect_renderer_artifact_warns_for_unknown_schema_2_renderer(tmp_path):
    artifact_dir = tmp_path / "server-render"
    assets_dir = artifact_dir / "assets"
    assets_dir.mkdir(parents=True)
    (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "2.1.0",
        "schemaVersion": "2.0",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid", "unknown-diagram"],
        "minDocxServiceVersion": "0.2.0",
        "renderers": [
            {"type": "mermaid", "displayName": "Mermaid", "capabilities": {"docxService": {"state": "supported"}}},
            {"type": "unknown-diagram", "displayName": "Unknown", "capabilities": {"docxService": {"state": "supported"}}},
        ],
    }), encoding="utf-8")

    info = inspect_renderer_artifact(artifact_dir, service_version="0.2.0")

    assert any(
        warning["code"] == "RENDERER_MANIFEST_NOT_ALLOWLISTED"
        and warning["rendererType"] == "unknown-diagram"
        for warning in info.rendererWarnings
    )


def test_inspect_renderer_artifact_warns_for_newer_schema_2_minor(tmp_path):
    artifact_dir = tmp_path / "server-render"
    assets_dir = artifact_dir / "assets"
    assets_dir.mkdir(parents=True)
    (artifact_dir / "server-render.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "manifest.json").write_text(json.dumps({
        "name": "@md-viewer/server-renderer",
        "version": "2.2.0",
        "schemaVersion": "2.1",
        "entryHtml": "server-render.html",
        "assetsDir": "assets",
        "supportedCharts": ["mermaid"],
        "minDocxServiceVersion": "0.2.0",
        "renderers": [
            {
                "type": "mermaid",
                "displayName": "Mermaid",
                "capabilities": {"docxService": {"state": "supported"}},
                "newMinorField": True,
            },
        ],
    }), encoding="utf-8")

    info = inspect_renderer_artifact(artifact_dir, service_version="0.2.0")

    assert any(
        warning["code"] == "RENDERER_SCHEMA_MINOR_NEWER"
        and warning["schemaVersion"] == "2.1"
        for warning in info.rendererWarnings
    )


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
