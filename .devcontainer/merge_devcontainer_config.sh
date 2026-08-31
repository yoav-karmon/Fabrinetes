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
    def valid_path:
      (type == "string") and
      (length > 0) and
      ((. == "~") or startswith("~/") or startswith("/")) and
      ((split("/") | index("..")) == null) and
      (test("[\u0000-\u001f,]") | not);

    def valid_environment_variable:
      (type == "string") and test("^[A-Za-z_][A-Za-z0-9_]*$");

    def validate_fabrinetes:
      (.customizations.Fabrinetes? // {}) as $fabrinetes |
      ($fabrinetes.requiredTools? // {}) as $tools |
      ($fabrinetes.additionalMounts? // []) as $mounts |
      if ($tools | type) != "object" then
        error("customizations.Fabrinetes.requiredTools must be an object")
      elif ((($tools | keys) - ["codex", "vscode", "cursor", "vivado"]) | length) > 0 then
        error("requiredTools contains an unsupported tool")
      elif any(["codex", "vscode", "cursor"][] as $name |
        select($tools | has($name)) |
        ($tools[$name] | type) != "object" or
        (($tools[$name].serverPath? // null) | valid_path | not)
      ) then
        error("codex, vscode, and cursor require a valid serverPath")
      elif ($tools | has("vivado")) and (
        (($tools.vivado | type) != "object") or
        (($tools.vivado.settingsScript? // null) | valid_path | not) or
        (($tools.vivado.settingsEnvironmentVariable? // null) | valid_environment_variable | not)
      ) then
        error("vivado requires valid settingsScript and settingsEnvironmentVariable values")
      elif ($mounts | type) != "array" then
        error("customizations.Fabrinetes.additionalMounts must be an array")
      elif any($mounts[];
        (type != "object") or
        ((.serverPath? // null) | valid_path | not) or
        ((.containerPath? // null) | valid_path | not)
      ) then
        error("additionalMounts entries require valid serverPath and containerPath values")
      elif ($fabrinetes.runner.home? != null) and (($fabrinetes.runner.home | valid_path) | not) then
        error("runner.home must be an absolute path or use ~")
      elif ($fabrinetes.runner.repoMountSource? != null) and (($fabrinetes.runner.repoMountSource | valid_path) | not) then
        error("runner.repoMountSource must be an absolute path or use ~")
      elif ($fabrinetes.runner.repoMountTarget? != null) and (($fabrinetes.runner.repoMountTarget | valid_path) | not) then
        error("runner.repoMountTarget must be an absolute path or use ~")
      elif ($fabrinetes.runner.fabrinetes? != null) and (($fabrinetes.runner.fabrinetes | valid_path) | not) then
        error("runner.fabrinetes must be an absolute path or use ~")
      else
        true
      end;

    if type != "object" then
      error("configuration root must be an object")
    elif ((.customizations // {}) | type) != "object" then
      error("customizations must be an object")
    elif ((.customizations.vscode.extensions? // []) | type) != "array" then
      error("customizations.vscode.extensions must be an array")
    elif any((.customizations.vscode.extensions? // [])[]; (type != "string") or (length == 0)) then
      error("customizations.vscode.extensions entries must be non-empty strings")
    else
      validate_fabrinetes
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
[ -n "${HOME:-}" ] || fail 2 "HOME is required to resolve ~ paths"
case "$HOME" in
  /*) ;;
  *) fail 2 "HOME must be an absolute path: $HOME" ;;
esac

validate_input 1 generic "$generic_config"
validate_input 2 specific "$specific_config"

echo "[config 3/4] merge customizations" >&2
output_dir="$(dirname "$output_config")"
[ -d "$output_dir" ] || fail 3 "output directory does not exist: ${output_dir}"
merge_tmp="$(mktemp "${output_dir}/.fabrinetes-devcontainer.XXXXXX.json")"
final_tmp="$(mktemp "${output_dir}/.fabrinetes-devcontainer.XXXXXX.json")"
trap 'rm -f "$merge_tmp" "$final_tmp"' EXIT

jq -n \
  --arg host_home "$HOME" \
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

    def resolve_path($path; $home):
      if $path == "~" then $home
      elif $path | startswith("~/") then $home + ($path[1:])
      else $path
      end;

    def is_within($path; $root):
      ($path == $root) or
      (if $root == "/" then $path | startswith("/") else $path | startswith($root + "/") end);

    def mount_string($mount):
      "source=\($mount.source),target=\($mount.target),type=bind";

    $generic[0] as $generic_config |
    $specific[0] as $specific_config |
    merge_values(
      ($generic_config.customizations // {});
      ($specific_config.customizations // {})
    ) as $customizations |
    ($customizations.Fabrinetes // {}) as $fabrinetes |
    ($fabrinetes.requiredTools // {}) as $tools |
    if ((["codex", "vscode", "cursor", "vivado"] - ($tools | keys)) | length) > 0 then
      error("requiredTools must define codex, vscode, cursor, and vivado")
    else
      .
    end |
    resolve_path(($fabrinetes.runner.home // "~"); $host_home) as $container_home |
    ([
      if $tools | has("codex") then {
        source: resolve_path($tools.codex.serverPath; $host_home),
        target: ($container_home + "/.codex")
      } else empty end,
      if $tools | has("vscode") then {
        source: resolve_path($tools.vscode.serverPath; $host_home),
        target: ($container_home + "/.vscode-server")
      } else empty end,
      if $tools | has("cursor") then {
        source: resolve_path($tools.cursor.serverPath; $host_home),
        target: ($container_home + "/.cursor-server")
      } else empty end
    ]) as $tool_mounts |
    ([($fabrinetes.additionalMounts // [])[] | {
      source: resolve_path(.serverPath; $host_home),
      target: resolve_path(.containerPath; $container_home)
    }]) as $additional_mounts |
    ($tool_mounts + $additional_mounts) as $generated_mounts |
    if (($generated_mounts | map(.target) | length) != ($generated_mounts | map(.target) | unique | length)) then
      error("generated mounts contain duplicate container targets")
    else
      .
    end |
    (if $tools | has("vivado") then
      resolve_path($tools.vivado.settingsScript; $container_home)
    else null end) as $settings_script |
    (if $settings_script == null then [] else
      [$additional_mounts[] | select(is_within($settings_script; .target))]
    end) as $settings_mounts |
    if ($settings_script != null) and (($settings_mounts | length) != 1) then
      error("vivado settingsScript must be covered by exactly one additional mount")
    else
      .
    end |
    (if $settings_script == null then [] else
      ($settings_mounts[0]) as $settings_mount |
      [($settings_mount.source + ($settings_script | ltrimstr($settings_mount.target)))]
    end) as $required_files |
    ($generic_config + {
      customizations: $customizations,
      mounts: (($generic_config.mounts // []) + ($generated_mounts | map(mount_string(.)))),
      containerEnv: (
        ($generic_config.containerEnv // {}) +
        (if $settings_script == null then {} else {
          ($tools.vivado.settingsEnvironmentVariable): $settings_script
        } end)
      ),
      __fabrinetesValidation: {
        mountSources: ($generated_mounts | map(.source)),
        requiredFiles: $required_files
      }
    })
  ' > "$merge_tmp" || fail 3 "could not merge and generate devcontainer configuration"

echo "[config 4/4] validate effective configuration" >&2
jq -e '
  (type == "object") and
  ((.build | type) == "object") and
  ((.mounts | type) == "array") and
  (all(.mounts[]; type == "string")) and
  ((.containerEnv | type) == "object") and
  ((.customizations | type) == "object") and
  (((.customizations.vscode.extensions? // []) | type) == "array") and
  (all((.customizations.vscode.extensions? // [])[]; (type == "string") and (length > 0)))
' "$merge_tmp" >/dev/null || fail 4 "invalid effective devcontainer configuration"

while IFS= read -r source_path; do
  [ -d "$source_path" ] || fail 4 "mount serverPath is not an existing directory: $source_path"
done < <(jq -r '.__fabrinetesValidation.mountSources[]' "$merge_tmp")

while IFS= read -r required_file; do
  [ -f "$required_file" ] || fail 4 "required tool file does not exist: $required_file"
done < <(jq -r '.__fabrinetesValidation.requiredFiles[]' "$merge_tmp")

jq 'del(.__fabrinetesValidation)' "$merge_tmp" > "$final_tmp" || fail 4 "could not finalize effective configuration"
mv "$final_tmp" "$output_config"
trap - EXIT
rm -f "$merge_tmp"
