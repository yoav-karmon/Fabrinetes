#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
merge_script="$script_dir/merge_devcontainer_config.sh"
test_dir="$(mktemp -d)"
trap 'rm -rf "$test_dir"' EXIT

generic_config="$test_dir/generic.json"
specific_config="$test_dir/specific.json"
effective_config="$test_dir/effective.json"
error_log="$test_dir/error.log"

cat > "$generic_config" <<'JSON'
{
  "name": "generic",
  "build": {},
  "customizations": {
    "vscode": {"extensions": ["generic.one", "shared.one"]},
    "tool": {"mode": "generic", "nested": {"generic": true}}
  }
}
JSON

cat > "$specific_config" <<'JSON'
{
  "devcontainerFile": "generic.json",
  "customizations": {
    "vscode": {"extensions": ["shared.one", "specific.one"]},
    "tool": {"mode": "specific", "nested": {"specific": true}},
    "Fabrinetes": {"builder": {"image": "specific-image"}}
  }
}
JSON

"$merge_script" "$generic_config" "$specific_config" "$effective_config" >/dev/null
jq -e '
  .name == "generic" and
  .customizations.vscode.extensions == ["generic.one", "shared.one", "specific.one"] and
  .customizations.tool.mode == "specific" and
  .customizations.tool.nested == {"generic": true, "specific": true} and
  .customizations.Fabrinetes.builder.image == "specific-image" and
  (has("devcontainerFile") | not)
' "$effective_config" >/dev/null

printf '{invalid json\n' > "$specific_config"
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: malformed specific JSON unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 2/4]' "$error_log" >/dev/null

cat > "$specific_config" <<'JSON'
{"customizations": {"vscode": {"extensions": "not-an-array"}}}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: invalid extension type unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 2/4]' "$error_log" >/dev/null

cat > "$generic_config" <<'JSON'
{"name": "missing-build", "customizations": {}}
JSON
cat > "$specific_config" <<'JSON'
{"customizations": {}}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: invalid effective config unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 4/4]' "$error_log" >/dev/null

echo "merge_devcontainer_config tests passed"
