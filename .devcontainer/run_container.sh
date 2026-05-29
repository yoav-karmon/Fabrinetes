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

devcontainer_path="$(jq -er '.devcontainerFile' "$fabrinetes_config")"
run_config="$(cd "$fabrinetes_config_dir/$(dirname "$devcontainer_path")" && pwd)/$(basename "$devcontainer_path")"
run_config_dir="$(dirname "$run_config")"
require_file "$run_config"

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
vivado_settings_template="$(jq -er '.customizations.Fabrinetes.mount.vivadoSettings' "$fabrinetes_config")"

# The run devcontainer uses ${localEnv:...} placeholders. Export concrete values
# here before invoking devcontainer up so the CLI can substitute them.
export DEVCONTAINER_USER="$USER"
export DEVCONTAINER_UID="$(id -u)"
export DEVCONTAINER_GID="$(id -g)"
export HOST_MACHINE="$(hostname -s)"
export CONTAINER_NAME="$(expand_local_env "$container_name_template")"
export CONTAINER_HOSTNAME="$(expand_local_env "$hostname_template")"
export CONTAINER_WORKSPACE_FOLDER="$(expand_local_env "$home_template")"
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
  HOST_MACHINE
  CONTAINER_NAME
  CONTAINER_HOSTNAME
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

# Make ${localWorkspaceFolder} in the run config point at the run config folder.
workspace_folder="$run_config_dir"

devcontainer up \
  --workspace-folder "$workspace_folder" \
  --config "$run_config"
