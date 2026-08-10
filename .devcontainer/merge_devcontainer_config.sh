#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: merge_devcontainer_config.sh <generic-json> <specific-json> <output-json>" >&2
}

fail() {
  local stage="$1"
  shift
  echo "error: [config ${stage}/4] $*" >&2
  exit 1
}

validate_input() {
  local stage="$1"
  local label="$2"
  local config="$3"

  echo "[config ${stage}/4] validate ${label} configuration: ${config}" >&2
  [ -f "$config" ] || fail "$stage" "missing ${label} configuration: ${config}"
  jq -e '
    if type != "object" then
      error("configuration root must be an object")
    elif ((.customizations // {}) | type) != "object" then
      error("customizations must be an object")
    elif ((.customizations.vscode.extensions? // []) | type) != "array" then
      error("customizations.vscode.extensions must be an array")
    elif any((.customizations.vscode.extensions? // [])[]; (type != "string") or (length == 0)) then
      error("customizations.vscode.extensions entries must be non-empty strings")
    else
      true
    end
  ' "$config" >/dev/null || fail "$stage" "invalid ${label} configuration: ${config}"
}

if [ "$#" -ne 3 ]; then
  usage
  exit 1
fi

generic_config="$1"
specific_config="$2"
output_config="$3"

command -v jq >/dev/null 2>&1 || fail 1 "jq is required"

validate_input 1 generic "$generic_config"
validate_input 2 specific "$specific_config"

echo "[config 3/4] merge customizations" >&2
output_dir="$(dirname "$output_config")"
[ -d "$output_dir" ] || fail 3 "output directory does not exist: ${output_dir}"
merge_tmp="$(mktemp "${output_dir}/.fabrinetes-devcontainer.XXXXXX.json")"
trap 'rm -f "$merge_tmp"' EXIT

jq -n \
  --slurpfile generic "$generic_config" \
  --slurpfile specific "$specific_config" '
    def merge_values($generic_value; $specific_value):
      if (($generic_value | type) == "object") and (($specific_value | type) == "object") then
        reduce ($specific_value | keys_unsorted[]) as $key ($generic_value;
          .[$key] = if ($generic_value | has($key)) then
            merge_values($generic_value[$key]; $specific_value[$key])
          else
            $specific_value[$key]
          end
        )
      elif (($generic_value | type) == "array") and (($specific_value | type) == "array") then
        reduce ($generic_value + $specific_value)[] as $item ([];
          if any(.[]; . == $item) then . else . + [$item] end
        )
      else
        $specific_value
      end;

    $generic[0] as $generic_config |
    $specific[0] as $specific_config |
    $generic_config + {
      customizations: merge_values(
        ($generic_config.customizations // {});
        ($specific_config.customizations // {})
      )
    }
  ' > "$merge_tmp" || fail 3 "could not merge customizations"

echo "[config 4/4] validate effective configuration" >&2
jq -e '
  (type == "object") and
  ((.build | type) == "object") and
  ((.customizations | type) == "object") and
  (((.customizations.vscode.extensions? // []) | type) == "array") and
  (all((.customizations.vscode.extensions? // [])[]; (type == "string") and (length > 0)))
' "$merge_tmp" >/dev/null || fail 4 "invalid effective devcontainer configuration"

mv "$merge_tmp" "$output_config"
trap - EXIT
