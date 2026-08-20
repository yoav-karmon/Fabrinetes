#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: run_container.sh <Fabrinetes-devcontainer-json>" >&2
}

die() {
  echo "error: $*" >&2
  exit 1
}

require_file() {
  [ -f "$1" ] || die "missing file: $1"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}

require_env() {
  local env_var="$1"
  [ -n "${!env_var:-}" ] || die "missing required environment variable: $env_var"
}

expand_local_env() {
  local value="$1"
  local env_var

  while [[ "$value" =~ \$\{localEnv:([A-Za-z_][A-Za-z0-9_]*)\} ]]; do
    env_var="${BASH_REMATCH[1]}"
    require_env "$env_var"
    value="${value//\$\{localEnv:$env_var\}/${!env_var}}"
  done

  printf '%s\n' "$value"
}

resolve_from_run_config_dir() {
  local path="$1"

  case "$path" in
    /*)
      printf '%s\n' "$path"
      ;;
    *)
      cd "$run_config_dir/$path" && pwd
      ;;
  esac
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

# Handle help before enforcing the required positional argument.
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

# Require exactly one Fabrinetes devcontainer file argument.
if [ "$#" -ne 1 ]; then
  usage
  exit 1
fi

# Normalize the Fabrinetes devcontainer path.
fabrinetes_config_arg="$1"
fabrinetes_config_dir="$(cd "$(dirname "$fabrinetes_config_arg")" && pwd)"
fabrinetes_config="$fabrinetes_config_dir/$(basename "$fabrinetes_config_arg")"

require_file "$fabrinetes_config"
require_command jq
require_command docker

if ! devcontainer_path="$(jq -er '.devcontainerFile | select(type == "string" and length > 0)' "$fabrinetes_config")"; then
  die "[config 2/4] invalid specific configuration or devcontainerFile: $fabrinetes_config"
fi
run_config_path="$fabrinetes_config_dir/$(dirname "$devcontainer_path")"
[ -d "$run_config_path" ] || die "[config 1/4] generic configuration directory does not exist: $run_config_path"
run_config="$(cd "$run_config_path" && pwd)/$(basename "$devcontainer_path")"
run_config_dir="$(dirname "$run_config")"
require_file "$run_config"
merge_script="$run_config_dir/merge_devcontainer_config.sh"
require_file "$merge_script"
[ -x "$merge_script" ] || die "config merger is not executable: $merge_script"
config_id="$(printf '%s' "$fabrinetes_config" | sha256sum | cut -c1-16)"
effective_run_config_dir="$fabrinetes_config_dir/../.generated/${config_id}"
effective_run_config="$effective_run_config_dir/devcontainer.json"
mkdir -p "$effective_run_config_dir"
"$merge_script" "$run_config" "$fabrinetes_config" "$effective_run_config"

# Runner metadata is custom project metadata. The devcontainer CLI ignores it,
# but these wrapper scripts use it as their source of truth.
container_name_template="$(jq -er '.customizations.Fabrinetes.runner.containerName' "$fabrinetes_config")"
hostname_template="$(jq -er '.customizations.Fabrinetes.runner.hostname' "$fabrinetes_config")"
home_template="$(jq -er '.customizations.Fabrinetes.runner.home' "$fabrinetes_config")"
amd_root_template="$(jq -er '.customizations.Fabrinetes.mount.amdRoot' "$fabrinetes_config")"
amd_target_template="$(jq -er '.customizations.Fabrinetes.mount.amdTarget' "$fabrinetes_config")"
repo_mount_source_template="$(jq -er '.customizations.Fabrinetes.runner.repoMountSource' "$fabrinetes_config")"
repo_mount_target_template="$(jq -er '.customizations.Fabrinetes.runner.repoMountTarget' "$fabrinetes_config")"
fabrinetes_template="$(jq -er '.customizations.Fabrinetes.runner.fabrinetes' "$fabrinetes_config")"
codex_folder_host_template="$(jq -er '.customizations.Fabrinetes.runner.codexFolderHost // "${localEnv:HOME}/.codex"' "$fabrinetes_config")"
vscode_folder_host_template="$(jq -er '.customizations.Fabrinetes.runner.vscodeFolderHost // "${localEnv:HOME}/vscode-server-container/.vscode-server"' "$fabrinetes_config")"
vivado_settings_template="$(jq -er '.customizations.Fabrinetes.mount.vivadoSettings' "$fabrinetes_config")"
build_dir_path="$(jq -er '.customizations.Fabrinetes.builder.buildDir // ""' "$fabrinetes_config")"
workspace_folder="$(resolve_build_dir "$build_dir_path")"

# The run devcontainer uses ${localEnv:...} placeholders. Export concrete values
# here before invoking devcontainer up so the CLI can substitute them.
export DEVCONTAINER_USER="$USER"
export DEVCONTAINER_UID="$(id -u)"
export DEVCONTAINER_GID="$(id -g)"
export FABRINETES_BUILD_CONTEXT="$workspace_folder"
export FABRINETES_DOCKERFILE="$run_config_dir/Dockerfile"
export HOST_MACHINE="$(hostname -s)"
export CONTAINER_NAME="$(expand_local_env "$container_name_template")"
export CONTAINER_HOSTNAME="$(expand_local_env "$hostname_template")"
export CONTAINER_WORKSPACE_FOLDER="$(expand_local_env "$home_template")"
export CODEX_FOLDER_HOST="$(expand_local_env "$codex_folder_host_template")"
export VSCODE_FOLDER_HOST="$(expand_local_env "$vscode_folder_host_template")"
export AMD_ROOT="$(expand_local_env "$amd_root_template")"
export AMD_TARGET="$(expand_local_env "$amd_target_template")"
export REPO_MOUNT_SOURCE="$(resolve_from_run_config_dir "$(expand_local_env "$repo_mount_source_template")")"
export REPO_MOUNT_TARGET="$(expand_local_env "$repo_mount_target_template")"
export FABRINETES="$(expand_local_env "$fabrinetes_template")"
export VIVADO_SETTINGS="$(expand_local_env "$vivado_settings_template")"

required_env_vars=(
  DEVCONTAINER_USER
  DEVCONTAINER_UID
  DEVCONTAINER_GID
  FABRINETES_BUILD_CONTEXT
  FABRINETES_DOCKERFILE
  HOST_MACHINE
  CONTAINER_NAME
  CONTAINER_HOSTNAME
  CODEX_FOLDER_HOST
  VSCODE_FOLDER_HOST
  AMD_ROOT
  AMD_TARGET
  REPO_MOUNT_SOURCE
  REPO_MOUNT_TARGET
  CONTAINER_WORKSPACE_FOLDER
  FABRINETES
  VIVADO_SETTINGS
)

for env_var in "${required_env_vars[@]}"; do
  require_env "$env_var"
done

if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  label_config="$(docker inspect -f '{{ index .Config.Labels "devcontainer.config_file" }}' "$CONTAINER_NAME")"
  if [ -n "$label_config" ] && [ ! -f "$label_config" ]; then
    mkdir -p "$(dirname "$label_config")"
    cp "$effective_run_config" "$label_config"
  fi

  container_status="$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME")"
  case "$container_status" in
    running)
      echo "container: $CONTAINER_NAME"
      echo "status: running"
      exit 0
      ;;
    *)
      echo "container: $CONTAINER_NAME"
      echo "status: $container_status -> starting"
      docker start "$CONTAINER_NAME" >/dev/null
      echo "status: running"
      exit 0
      ;;
  esac
fi

# Make ${localWorkspaceFolder} in the run config point at the selected support folder.
require_file "$FABRINETES_DOCKERFILE"
require_file "$FABRINETES_BUILD_CONTEXT/packages.txt"
require_file "$FABRINETES_BUILD_CONTEXT/python-packages.txt"

devcontainer up \
  --workspace-folder "$workspace_folder" \
  --config "$effective_run_config"
