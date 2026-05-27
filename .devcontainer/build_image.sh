#!/usr/bin/env bash
set -euo pipefail

repo_top="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker build \
  -t fabrinetes-dev:local \
  -f "$repo_top/.devcontainer/fabrinetes-build/Dockerfile" \
  "$repo_top"
