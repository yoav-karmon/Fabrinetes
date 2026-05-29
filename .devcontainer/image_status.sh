#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: image_status.sh <Fabrinetes-devcontainer-json>}"

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
  echo "error: docker is required to inspect the image" >&2
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

image_template="$(jq -er '.customizations.Fabrinetes.builder.image' "$fabrinetes_config")"
image="$(expand_local_env "$image_template")"

echo "image: $image"
if docker image inspect "$image" >/dev/null 2>&1; then
  docker image ls --digests --no-trunc "$image"
else
  echo "status: missing"
fi
