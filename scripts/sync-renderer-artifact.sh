#!/usr/bin/env sh
set -eu

SERVICE_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
MD_VIEWER_ROOT="${MD_VIEWER_ROOT:-"$SERVICE_ROOT/../md-viewer"}"
SOURCE_DIR="${MDV_RENDER_ARTIFACT_SOURCE:-"$MD_VIEWER_ROOT/out/renderer"}"
TARGET_DIR="${MDV_RENDER_ARTIFACT_TARGET:-"$SERVICE_ROOT/renderers/dist/server-render"}"

if [ ! -f "$SOURCE_DIR/server-render.html" ]; then
  echo "server-render.html not found in $SOURCE_DIR" >&2
  echo "Run npm run build in md-viewer first, or set MDV_RENDER_ARTIFACT_SOURCE." >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/manifest.json" ]; then
  echo "manifest.json not found in $SOURCE_DIR" >&2
  exit 1
fi

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -R "$SOURCE_DIR"/. "$TARGET_DIR"/

echo "Synced renderer artifact to $TARGET_DIR"
