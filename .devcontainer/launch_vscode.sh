#!/usr/bin/env bash
set -euo pipefail

: "${1:?usage: launch_vscode.sh <Fabrinetes-devcontainer-json>}"

fabrinetes_config_dir="$(cd "$(dirname "$1")" && pwd)"
fabrinetes_config="$fabrinetes_config_dir/$(basename "$1")"

if [ ! -f "$fabrinetes_config" ]; then
  echo "error: missing Fabrinetes devcontainer file: $fabrinetes_config" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to read devcontainer metadata" >&2
  exit 1
fi

if ! command -v code >/dev/null 2>&1; then
  echo "error: code is required to launch VS Code" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "error: node is required to build the VS Code dev-container URI" >&2
  exit 1
fi

require_file() {
  if [ ! -f "$1" ]; then
    echo "error: missing file: $1" >&2
    exit 1
  fi
}

require_env() {
  local env_var="$1"
  if [ -z "${!env_var:-}" ]; then
    echo "error: missing required environment variable: $env_var" >&2
    exit 1
  fi
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

if ! devcontainer_path="$(jq -er '.devcontainerFile | select(type == "string" and length > 0)' "$fabrinetes_config")"; then
  echo "error: [config 2/4] invalid specific configuration or devcontainerFile: $fabrinetes_config" >&2
  exit 1
fi
run_config_path="$fabrinetes_config_dir/$(dirname "$devcontainer_path")"
[ -d "$run_config_path" ] || {
  echo "error: [config 1/4] generic configuration directory does not exist: $run_config_path" >&2
  exit 1
}
run_config="$(cd "$run_config_path" && pwd)/$(basename "$devcontainer_path")"
run_config_dir="$(dirname "$run_config")"
merge_script="$run_config_dir/merge_devcontainer_config.sh"
require_file "$run_config"
require_file "$merge_script"
[ -x "$merge_script" ] || {
  echo "error: config merger is not executable: $merge_script" >&2
  exit 1
}

config_id="$(printf '%s' "$fabrinetes_config" | sha256sum | cut -c1-16)"
effective_vscode_config_dir="$fabrinetes_config_dir/../.generated/${config_id}"
mkdir -p "$effective_vscode_config_dir"
effective_vscode_config_dir="$(cd "$effective_vscode_config_dir" && pwd)"
merged_vscode_config="$effective_vscode_config_dir/.merged-vscode-devcontainer.json"
effective_vscode_config="$effective_vscode_config_dir/devcontainer.json"
"$merge_script" "$run_config" "$fabrinetes_config" "$merged_vscode_config"

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
build_context="$(resolve_build_dir "$build_dir_path")"

export DEVCONTAINER_USER="$USER"
export DEVCONTAINER_UID="$(id -u)"
export DEVCONTAINER_GID="$(id -g)"
export FABRINETES_BUILD_CONTEXT="$build_context"
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

LOCAL_WORKSPACE_FOLDER="$build_context" RESOLVED_CONFIG_IN="$merged_vscode_config" RESOLVED_CONFIG_OUT="$effective_vscode_config" node - <<'NODE'
const fs = require('fs');
const path = require('path');

function resolveEnv(value) {
  if (typeof value === 'string') {
    return value.replace(/\$\{localWorkspaceFolderBasename\}/g, path.basename(process.env.LOCAL_WORKSPACE_FOLDER))
      .replace(/\$\{localWorkspaceFolder\}/g, process.env.LOCAL_WORKSPACE_FOLDER)
      .replace(/\$\{localEnv:([A-Za-z_][A-Za-z0-9_]*)\}/g, (_, name) => {
      if (!process.env[name]) {
        throw new Error(`missing required environment variable: ${name}`);
      }
      return process.env[name];
    });
  }
  if (Array.isArray(value)) {
    return value.map(resolveEnv);
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, resolveEnv(item)]));
  }
  return value;
}

const input = JSON.parse(fs.readFileSync(process.env.RESOLVED_CONFIG_IN, 'utf8'));
fs.writeFileSync(process.env.RESOLVED_CONFIG_OUT, `${JSON.stringify(resolveEnv(input), null, 2)}\n`);
NODE

container_name="$CONTAINER_NAME"
repo_mount_target="$REPO_MOUNT_TARGET"
workspace_folder="$(git -C "$fabrinetes_config_dir" rev-parse --show-toplevel)"
remote_authority="${FABRINETES_VSCODE_REMOTE_AUTHORITY:-${VSCODE_CLI_AUTHORITY:-ssh-remote+$(hostname -s)}}"

dev_container_config_hex="$(
  HOST_PATH="$workspace_folder" CONFIG_FILE="$effective_vscode_config" node - <<'NODE'
const hostPath = process.env.HOST_PATH;
const configFilePath = process.env.CONFIG_FILE;
const configFile = {
  scheme: 'file',
  path: configFilePath,
  fsPath: configFilePath
};
const payload = { hostPath, configFile };
process.stdout.write(Buffer.from(JSON.stringify(payload), 'utf8').toString('hex'));
NODE
)"
dev_container_uri="vscode-remote://dev-container+${dev_container_config_hex}@${remote_authority}${repo_mount_target}"

echo "container: $container_name"
echo "host workspace: $workspace_folder"
echo "container workspace: $repo_mount_target"
echo "remote authority: $remote_authority"

if [ "${FABRINETES_VSCODE_PRINT_ONLY:-0}" = "1" ]; then
  exit 0
fi

code --new-window --folder-uri "$dev_container_uri"
