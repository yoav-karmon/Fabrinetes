#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: Fabrinetes.sh <Fabrinetes-devcontainer-json> --build|--run|--shell|--stop|--remove-image|--vscode|--clean-vscode" >&2
}

die() {
  echo "error: $*" >&2
  exit 1
}

run_script() {
  local script="$1"

  [ -x "$script" ] || die "missing executable script: $script"
  "$script" "$fabrinetes_config"
}

if [ "$#" -ne 2 ]; then
  usage
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fabrinetes_config="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
action="$2"

[ -f "$fabrinetes_config" ] || die "missing Fabrinetes devcontainer file: $fabrinetes_config"

case "$action" in
  --build)
    run_script "$script_dir/build_image.sh"
    ;;
  --run)
    run_script "$script_dir/run_container.sh"
    ;;
  --shell)
    run_script "$script_dir/open_container_shell.sh"
    ;;
  --stop)
    run_script "$script_dir/stop_container.sh"
    ;;
  --remove-image)
    run_script "$script_dir/remove_image.sh"
    ;;
  --vscode)
    run_script "$script_dir/launch_vscode.sh"
    ;;
  --clean-vscode)
    run_script "$script_dir/clean_vscode_server.sh"
    ;;
  -h|--help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
