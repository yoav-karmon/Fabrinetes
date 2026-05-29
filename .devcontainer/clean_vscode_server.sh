#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: clean_vscode_server.sh <Fabrinetes-devcontainer-json>}"

fabrinetes_config="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"

if [ ! -f "$fabrinetes_config" ]; then
  echo "error: missing Fabrinetes devcontainer file: $fabrinetes_config" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to read devcontainer metadata" >&2
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
home_template="$(jq -er '.customizations.Fabrinetes.runner.home' "$fabrinetes_config")"

container="$(expand_local_env "$container_name_template")"
home_dir="$(expand_local_env "$home_template")"
host_vscode_server_bin="$HOME/vscode-server-container/.vscode-server/bin"
container_vscode_server_bin="$home_dir/.vscode-server/bin"

rm -rf "$host_vscode_server_bin"

if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' | grep -Fxq "$container"; then
  docker exec -u root "$container" rm -rf "$container_vscode_server_bin"
fi
