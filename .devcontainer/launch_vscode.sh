#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: launch_vscode.sh <Fabrinetes-devcontainer-json>}"

fabrinetes_config="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"

if [ ! -f "$fabrinetes_config" ]; then
  echo "error: missing Fabrinetes devcontainer file: $fabrinetes_config" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to read devcontainer metadata" >&2
  exit 1
fi

if ! command -v xxd >/dev/null 2>&1; then
  echo "error: xxd is required to encode the VS Code container URI" >&2
  exit 1
fi

if ! command -v code >/dev/null 2>&1; then
  echo "error: code is required to launch VS Code" >&2
  exit 1
fi

expand_local_env() {
  local value="$1"
  local env_var

  while [[ "$value" =~ \$\{localEnv:([A-Za-z_][A-Za-z0-9_]*)\} ]]; do
    env_var="${BASH_REMATCH[1]}"
    if [ -z "${!env_var:-}" ]; then
      echo "error: missing required environment variable: $env_var" >&2
      exit 1
    fi
    value="${value//\$\{localEnv:$env_var\}/${!env_var}}"
  done

  printf '%s\n' "$value"
}

container_name_template="$(jq -er '.customizations.Fabrinetes.runner.containerName' "$fabrinetes_config")"
repo_mount_target_template="$(jq -er '.customizations.Fabrinetes.runner.repoMountTarget' "$fabrinetes_config")"

container_name="$(expand_local_env "$container_name_template")"
repo_mount_target="$(expand_local_env "$repo_mount_target_template")"
encoded_container_name="$(printf '%s' "$container_name" | xxd -p -c 256)"

code --folder-uri "vscode-remote://attached-container+${encoded_container_name}${repo_mount_target}"
