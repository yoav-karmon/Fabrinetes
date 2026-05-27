#!/usr/bin/env bash
set -euo pipefail

container="${USER}_fabrinetes_dev.run"
home_dir="/home/${USER}"

docker exec \
  -u "$USER" \
  -e HOME="$home_dir" \
  -w "$home_dir" \
  -it "$container" \
  bash -i
