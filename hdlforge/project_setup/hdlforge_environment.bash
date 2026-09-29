# Environment bootstrap owned by the HDLForge launcher.
hdlforge_find_environment_project() {
    local search_dir
    local -a candidates
    if [ -n "${HDLFORGE_PROJECT_FILE:-}" ] && [ -f "$HDLFORGE_PROJECT_FILE" ]; then
        realpath "$HDLFORGE_PROJECT_FILE"
        return 0
    fi
    search_dir="$(pwd -P)"
    while :; do
        shopt -s nullglob
        candidates=("$search_dir"/*.hdlforge.json)
        shopt -u nullglob
        if [ "${#candidates[@]}" -eq 1 ]; then
            realpath "${candidates[0]}"
            return 0
        fi
        [ "$search_dir" = "${REPO_TOP:-}" ] && break
        [ "$search_dir" = "/" ] && break
        search_dir="$(dirname "$search_dir")"
    done
    return 1
}

hdlforge_find_repo_environment_project() {
    local -a candidates
    shopt -s nullglob
    candidates=("$REPO_TOP"/*.hdlforge.json)
    shopt -u nullglob
    if [ "${#candidates[@]}" -ne 1 ]; then
        echo "error: repository top must contain exactly one .hdlforge.json: $REPO_TOP" >&2
        return 1
    fi
    realpath "${candidates[0]}"
}

hdlforge_list_host_and_users() {
    local project_json="$1"
    jq -r '.settings.env // {} | to_entries[] | .key as $host | .value | to_entries[] | "\($host):\(.key)"' "$project_json"
}

hdlforge_read_json_environment() {
    local project_json="$1"
    local host_name="$2"
    local user_name="$3"

    jq -c --arg host "$host_name" --arg user "$user_name" \
        '.settings.env[$host][$user] // empty' "$project_json"
}

hdlforge_apply_json_environment() {
    local env_json="$1"
    local jq_bin="$2"
    local path_entry pythonpath_entry vivado_settings variable_name variable_value

    [ -n "$env_json" ] || return 0

    while IFS= read -r path_entry; do
        [ -n "$path_entry" ] && add_to_path "$path_entry"
    done < <(printf '%s' "$env_json" | "$jq_bin" -r '.path[]?')
    while IFS= read -r pythonpath_entry; do
        [ -n "$pythonpath_entry" ] && add_to_pythonpath "$pythonpath_entry"
    done < <(printf '%s' "$env_json" | "$jq_bin" -r '.pythonpath[]?')

    vivado_settings="$(printf '%s' "$env_json" | "$jq_bin" -r '.tools.vivado // empty')"
    if [ -n "$vivado_settings" ]; then
        [ -f "$vivado_settings" ] || { echo "error: Vivado settings not found: $vivado_settings" >&2; return 1; }
        export VIVADO_SETTINGS="$vivado_settings"
        source "$VIVADO_SETTINGS"
    fi
    export VERILATOR_BIN="$(printf '%s' "$env_json" | "$jq_bin" -r '.tools.verilator // empty')"
    if [ -n "$VERILATOR_BIN" ]; then
        [ -x "$VERILATOR_BIN" ] || { echo "error: Verilator is unavailable at $VERILATOR_BIN" >&2; return 1; }
        add_to_path "$(dirname "$VERILATOR_BIN")"
    fi
    # Literal exported values; project-layer variables override repo defaults.
    if ! printf '%s' "$env_json" | "$jq_bin" -e '
        (.variables // {}) | type == "object" and
        all(to_entries[]; (.key | test("^[A-Za-z_][A-Za-z0-9_]*$")) and (.value | type == "string"))
    ' >/dev/null; then
        echo "error: environment variables must be an object of valid names and string values" >&2
        return 1
    fi
    while IFS= read -r variable_name; do
        variable_value="$(printf '%s' "$env_json" | "$jq_bin" -r --arg key "$variable_name" '.variables[$key]')"
        export "$variable_name=$variable_value"
    done < <(printf '%s' "$env_json" | "$jq_bin" -r '.variables // {} | keys[]')
    clean_path
    clean_pythonpath
}

hdlforge_prepare_environment() {
    local installation_dir="$HDLFORGE_INSTALL_DIR"
    local installation_root="$FABRINETES"

    source "$installation_dir/bashrc-func" || return 1

    if [ "${HDLFORGE_CALLED:-0}" = "1" ]; then
        export HDLFORGE_NESTED_CALL=1
        return 0
    fi
    export HDLFORGE_CALLED=1
    export HDLFORGE_NESTED_CALL=0

    # Read both JSON layers while the caller's tools are still on PATH.
    local repo_json project_json repo_environment project_environment jq_bin
    jq_bin="$(type -P jq)" || { echo "error: jq is required on the incoming PATH" >&2; return 1; }
    jq_bin="$(realpath -s "$jq_bin")" || return 1
    export REPO_TOP="$(git rev-parse --show-toplevel 2>/dev/null)"
    [ -n "$REPO_TOP" ] || { echo "error: HDLForge must run inside a Git repository" >&2; return 1; }
    export HDLFORGE_SELECTED_HOST="${HOST_MACHINE:-$(hostname -s)}"
    export HDLFORGE_SELECTED_USER="${HDLFORGE_HOST_USER:-$(id -un)}"
    export HDLFORGE_SELECTED_HOST_AND_USER="${HDLFORGE_SELECTED_HOST}:${HDLFORGE_SELECTED_USER}"
    repo_json="$(hdlforge_find_repo_environment_project)" || return 1
    project_json="$(hdlforge_find_environment_project || true)"
    export HDLFORGE_ENV_REPO_JSON="$repo_json"
    export HDLFORGE_ENV_PROJECT_JSON="${project_json:-$repo_json}"
    repo_environment="$(hdlforge_read_json_environment "$repo_json" "$HDLFORGE_SELECTED_HOST" "$HDLFORGE_SELECTED_USER")" || return 1
    if [ -n "$project_json" ] && [ "$project_json" != "$repo_json" ]; then
        project_environment="$(hdlforge_read_json_environment "$project_json" "$HDLFORGE_SELECTED_HOST" "$HDLFORGE_SELECTED_USER")" || return 1
    fi

    set_base_path "${HDLFORGE_BASE_PATH:-/usr/bin:/bin}"
    set_base_pythonpath "${HDLFORGE_BASE_PYTHONPATH:-}"
    export HDLFORGE_INHERITED_PATH="$PATH"
    export HDLFORGE_INHERITED_PYTHONPATH="$PYTHONPATH"

    # Machine configuration may name a different checkout; use the invoked one.
    export FABRINETES="$installation_root"
    export HDLFORGE="$installation_dir"
    add_to_path "$installation_dir"
    [ ! -d "$HOME/.local/bin" ] || add_to_path "$HOME/.local/bin"
    clean_path
    clean_pythonpath
    export INIT_PATH="$PATH"
    export INIT_PYTHONPATH="$PYTHONPATH"
    export HDLFORGE_BOOTSTRAP_PATH="$INIT_PATH"
    export HDLFORGE_BOOTSTRAP_PYTHONPATH="$INIT_PYTHONPATH"
    update_repo_path

    hdlforge_apply_json_environment "$repo_environment" "$jq_bin" || return 1
    if [ -n "$project_json" ] && [ "$project_json" != "$repo_json" ]; then
        hdlforge_apply_json_environment "$project_environment" "$jq_bin" || return 1
    fi
}
