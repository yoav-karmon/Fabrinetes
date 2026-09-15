#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: open_container_shell.sh <Fabrinetes-devcontainer-json> [<command>]}"

if [ "$#" -gt 2 ] || { [ "$#" -eq 2 ] && [[ ! "$2" =~ [^[:space:]] ]]; }; then
  echo "error: expected at most one non-empty quoted command" >&2
  exit 1
fi

fabrinetes_config="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
fabrinetes_config_dir="$(dirname "$fabrinetes_config")"

if [ ! -f "$fabrinetes_config" ]; then
  echo "error: missing Fabrinetes devcontainer file: $fabrinetes_config" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to read devcontainer metadata" >&2
  exit 1
fi

devcontainer_path="$(jq -er '.devcontainerFile' "$fabrinetes_config")"
devcontainer_config="$(cd "$fabrinetes_config_dir/$(dirname "$devcontainer_path")" && pwd)/$(basename "$devcontainer_path")"

if [ ! -f "$devcontainer_config" ]; then
  echo "error: missing devcontainer file: $devcontainer_config" >&2
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

  case "$value" in
    "~") value="$HOME" ;;
    "~/"*) value="$HOME/${value#\~/}" ;;
  esac

  printf '%s\n' "$value"
}

container_name_template="$(jq -er '.customizations.Fabrinetes.runner.containerName' "$fabrinetes_config")"
home_template="$(jq -er '.customizations.Fabrinetes.runner.home' "$fabrinetes_config")"

export DEVCONTAINER_USER="$USER"
container="$(expand_local_env "$container_name_template")"
home_dir="$(expand_local_env "$home_template")"

if [[ "$home_dir" != /* ]]; then
  echo "error: runner.home must resolve to an absolute path: $home_dir" >&2
  exit 1
fi

docker_options=(-i)
shell_command=(bash -i)
if [ "$#" -eq 2 ]; then
  shell_command=(bash --noprofile --norc -c 'source "$HOME/.bashrc" >/dev/null || exit; eval "$1"' Fabrinetes-exec "$2")
else
  docker_options+=(-t)
fi

exec docker exec \
  -u "$USER" \
  -e HOME="$home_dir" \
  -w "$home_dir" \
  "${docker_options[@]}" "$container" \
  "${shell_command[@]}"
