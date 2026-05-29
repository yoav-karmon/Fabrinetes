#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: restart_container.sh <Fabrinetes-devcontainer-json>}"

fabrinetes_config="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"

if [ ! -f "$fabrinetes_config" ]; then
  echo "error: missing Fabrinetes devcontainer file: $fabrinetes_config" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to read devcontainer metadata" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required to restart the container" >&2
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
container="$(expand_local_env "$container_name_template")"

if docker ps -a --format '{{.Names}}' | grep -Fxq "$container"; then
  docker restart "$container"
else
  echo "container not found: $container"
  exit 1
fi
