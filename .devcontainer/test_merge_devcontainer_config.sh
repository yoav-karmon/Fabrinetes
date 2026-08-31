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

mkdir -p \
  "$test_dir/codex" \
  "$test_dir/vscode" \
  "$test_dir/cursor" \
  "$test_dir/amd/Vivado" \
  "$test_dir/container-home"
touch "$test_dir/amd/Vivado/settings64.sh"

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

cat > "$specific_config" <<JSON
{
  "devcontainerFile": "generic.json",
  "customizations": {
    "vscode": {"extensions": ["shared.one", "specific.one"]},
    "tool": {"mode": "specific", "nested": {"specific": true}},
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/codex"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"},
        "vivado": {
          "settingsScript": "/toolchain/Vivado/settings64.sh",
          "settingsEnvironmentVariable": "VIVADO_SETTINGS"
        }
      },
      "additionalMounts": [
        {"serverPath": "$test_dir/amd", "containerPath": "/toolchain"}
      ],
      "builder": {"image": "specific-image"},
      "runner": {"home": "$test_dir/container-home"}
    }
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

cat > "$specific_config" <<JSON
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/codex"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"},
        "vivado": {
          "settingsScript": "/toolchain/Vivado/settings64.sh",
          "settingsEnvironmentVariable": "VIVADO_SETTINGS"
        }
      },
      "additionalMounts": [
        {"serverPath": "$test_dir/amd", "containerPath": "/toolchain"}
      ],
      "runner": {
        "home": "$test_dir/container-home"
      }
    }
  }
}
JSON

"$merge_script" "$generic_config" "$specific_config" "$effective_config" >/dev/null
jq -e \
  --arg codex "source=$test_dir/codex,target=$test_dir/container-home/.codex,type=bind" \
  --arg vscode "source=$test_dir/vscode,target=$test_dir/container-home/.vscode-server,type=bind" \
  --arg cursor "source=$test_dir/cursor,target=$test_dir/container-home/.cursor-server,type=bind" \
  --arg amd "source=$test_dir/amd,target=/toolchain,type=bind" '
  (.mounts | index($codex)) != null and
  (.mounts | index($vscode)) != null and
  (.mounts | index($cursor)) != null and
  (.mounts | index($amd)) != null and
  .containerEnv.VIVADO_SETTINGS == "/toolchain/Vivado/settings64.sh" and
  (has("__fabrinetesValidation") | not)
' "$effective_config" >/dev/null

cat > "$specific_config" <<JSON
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/missing"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"},
        "vivado": {
          "settingsScript": "/toolchain/Vivado/settings64.sh",
          "settingsEnvironmentVariable": "VIVADO_SETTINGS"
        }
      },
      "additionalMounts": [
        {"serverPath": "$test_dir/amd", "containerPath": "/toolchain"}
      ],
      "runner": {"home": "$test_dir/container-home"}
    }
  }
}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: missing tool serverPath unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 4/4]' "$error_log" >/dev/null

cat > "$specific_config" <<JSON
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/codex"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"},
        "vivado": {
          "settingsScript": "/outside/Vivado/settings64.sh",
          "settingsEnvironmentVariable": "VIVADO_SETTINGS"
        }
      },
      "additionalMounts": [
        {"serverPath": "$test_dir/amd", "containerPath": "/toolchain"}
      ],
      "runner": {"home": "$test_dir/container-home"}
    }
  }
}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: uncovered Vivado settings script unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 3/4]' "$error_log" >/dev/null

cat > "$specific_config" <<JSON
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/codex"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"},
        "vivado": {
          "settingsScript": "/toolchain/Vivado/settings64.sh",
          "settingsEnvironmentVariable": "VIVADO_SETTINGS"
        }
      },
      "additionalMounts": [
        {"serverPath": "$test_dir/amd", "containerPath": "/toolchain"},
        {"serverPath": "$test_dir/amd", "containerPath": "$test_dir/container-home/.codex"}
      ],
      "runner": {"home": "$test_dir/container-home"}
    }
  }
}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: duplicate container target unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 3/4]' "$error_log" >/dev/null

cat > "$specific_config" <<'JSON'
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {"codex": {"serverPath": "relative/path"}}
    }
  }
}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: relative tool path unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 2/4]' "$error_log" >/dev/null

cat > "$specific_config" <<JSON
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/codex"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"}
      },
      "runner": {"home": "$test_dir/container-home"}
    }
  }
}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: missing mandatory tool unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 3/4]' "$error_log" >/dev/null

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
cat > "$specific_config" <<JSON
{
  "customizations": {
    "Fabrinetes": {
      "requiredTools": {
        "codex": {"serverPath": "$test_dir/codex"},
        "vscode": {"serverPath": "$test_dir/vscode"},
        "cursor": {"serverPath": "$test_dir/cursor"},
        "vivado": {
          "settingsScript": "/toolchain/Vivado/settings64.sh",
          "settingsEnvironmentVariable": "VIVADO_SETTINGS"
        }
      },
      "additionalMounts": [
        {"serverPath": "$test_dir/amd", "containerPath": "/toolchain"}
      ],
      "runner": {"home": "$test_dir/container-home"}
    }
  }
}
JSON
if "$merge_script" "$generic_config" "$specific_config" "$effective_config" 2> "$error_log"; then
  echo "error: invalid effective config unexpectedly succeeded" >&2
  exit 1
fi
grep -F '[config 4/4]' "$error_log" >/dev/null

echo "merge_devcontainer_config tests passed"
