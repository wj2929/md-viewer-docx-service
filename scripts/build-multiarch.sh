#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-0.1.0}"
IMAGE="${IMAGE:-mdviewer/docx-service}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"

docker buildx build \
  --platform "${PLATFORMS}" \
  -f Dockerfile.slim \
  -t "${IMAGE}:${VERSION}-slim" \
  -t "${IMAGE}:${VERSION}" \
  -t "${IMAGE}:latest" \
  --push \
  .

docker buildx build \
  --platform "${PLATFORMS}" \
  -f Dockerfile.full \
  -t "${IMAGE}:${VERSION}-full" \
  --push \
  .
