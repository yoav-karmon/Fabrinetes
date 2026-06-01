#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: build_image.sh <Fabrinetes-devcontainer-json>}"
fabrinetes_config="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
fabrinetes_config_dir="$(dirname "$fabrinetes_config")"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to read devcontainer build metadata" >&2
  exit 1
fi

devcontainer_path="$(jq -er '.devcontainerFile' "$fabrinetes_config")"
devcontainer_config="$(cd "$fabrinetes_config_dir/$(dirname "$devcontainer_path")" && pwd)/$(basename "$devcontainer_path")"
run_config_dir="$(dirname "$devcontainer_config")"
dockerfile="$run_config_dir/Dockerfile"

builder_value() {
  jq -er ".customizations.Fabrinetes.builder.$1" "$fabrinetes_config"
}

mount_value() {
  jq -er ".customizations.Fabrinetes.mount.$1" "$fabrinetes_config"
}

resolve_build_dir() {
  local path="$1"

  case "$path" in
    "")
      printf '%s\n' "$run_config_dir"
      ;;
    /*)
      cd "$path" && pwd
      ;;
    ./*|../*)
      cd "$fabrinetes_config_dir/$path" && pwd
      ;;
    *)
      cd "$(dirname "$fabrinetes_config_dir")/$path" && pwd
      ;;
  esac
}

expand_builder_value() {
  local value="$1"
  local env_var

  value="${value//\$\{buildContext\}/$build_context}"

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

export DEVCONTAINER_USER="$USER"
export DEVCONTAINER_UID="$(id -u)"
export DEVCONTAINER_GID="$(id -g)"
build_dir_path="$(jq -er '.customizations.Fabrinetes.builder.buildDir // ""' "$fabrinetes_config")"
workspace_folder="$(resolve_build_dir "$build_dir_path")"
build_context="$workspace_folder"
export FABRINETES_BUILD_CONTEXT="$build_context"
export FABRINETES_DOCKERFILE="$dockerfile"
image_name="$(expand_builder_value "$(builder_value image)")"

export CONTAINER_NAME="${DEVCONTAINER_USER}_fabrinetes-build.run"
export CONTAINER_HOSTNAME="fabrinetes-build"
export CONTAINER_WORKSPACE_FOLDER="/home/$DEVCONTAINER_USER"
export CODEX_FOLDER_HOST="$(expand_builder_value "$(jq -er '.customizations.Fabrinetes.runner.codexFolderHost // "${localEnv:HOME}/.codex"' "$fabrinetes_config")")"
export VSCODE_FOLDER_HOST="$(expand_builder_value "$(jq -er '.customizations.Fabrinetes.runner.vscodeFolderHost // "${localEnv:HOME}/vscode-server-container/.vscode-server"' "$fabrinetes_config")")"
export AMD_ROOT="$(expand_builder_value "$(mount_value amdRoot)")"
export AMD_TARGET="$(expand_builder_value "$(mount_value amdTarget)")"
export REPO_MOUNT_SOURCE="$build_context"
export REPO_MOUNT_TARGET="/home/$DEVCONTAINER_USER/workspace"
export FABRINETES="/home/$DEVCONTAINER_USER/workspace"
export VIVADO_SETTINGS="$(expand_builder_value "$(mount_value vivadoSettings)")"

packages_file="$(jq -er '.build.args.PACKAGES_FILE' "$devcontainer_config")"
python_packages_file="$(jq -er '.build.args.PYTHON_PACKAGES_FILE' "$devcontainer_config")"

for build_file in "$packages_file" "$python_packages_file"; do
  case "$build_file" in
    /*|../*|*/../*)
      echo "error: build file must be relative to build context: $build_file" >&2
      exit 1
      ;;
  esac
done

for required_file in "$devcontainer_config" "$fabrinetes_config" "$dockerfile" "$build_context/$packages_file" "$build_context/$python_packages_file"; do
  if [ ! -f "$required_file" ]; then
    echo "error: missing required build file: $required_file" >&2
    exit 1
  fi
done

devcontainer build \
  --workspace-folder "$workspace_folder" \
  --config "$devcontainer_config" \
  --image-name "$image_name"
