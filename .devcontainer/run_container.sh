#!/usr/bin/env bash
set -euo pipefail

repo_top="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

devcontainer up \
  --workspace-folder "$repo_top" \
  --config "$repo_top/.devcontainer/fabrinetes-run/devcontainer.json"
