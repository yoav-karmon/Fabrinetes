# Resolve paths against an explicit base before changing the working directory.
resolve_working_path() {
    local raw_path="$1"
    local base_dir="$2"
    raw_path="${raw_path/#\~/$HOME}"
    if [[ "$raw_path" != /* ]]; then
        raw_path="$base_dir/$raw_path"
    fi
    realpath -m -- "$raw_path"
}

# Find the nearest unambiguous project without crossing a Git checkout boundary.
# A recursive command can retain an explicit choice in that same directory.
hdlforge_discover_project() {
    local search_dir="$1"
    local inherited_project="${HDLFORGE_PROJECT_FILE:-}"
    local -a candidates
    while :; do
        if [ "${HDLFORGE_CALLED:-0}" = "1" ] && [ -f "$inherited_project" ] \
            && [ "${inherited_project%/*}" = "$search_dir" ]; then
            resolve_working_path "$inherited_project" "$search_dir"
            return
        fi
        candidates=()
        local candidate
        for candidate in "$search_dir"/*.hdlforge.json "$search_dir"/*.hdlforge.toml; do
            [ ! -f "$candidate" ] || candidates+=("$candidate")
        done
        if [ "${#candidates[@]}" -eq 1 ]; then
            resolve_working_path "${candidates[0]}" "$search_dir"
            return 0
        fi
        if [ "${#candidates[@]}" -gt 1 ]; then
            echo "error: multiple HDLForge project files in $search_dir; use --project <file>" >&2
            return 2
        fi
        [ ! -e "$search_dir/.git" ] || break
        [ "$search_dir" = "/" ] && break
        search_dir="$(dirname "$search_dir")"
    done
    return 1
}

# Select once, from the launch directory, before bootstrap or command dispatch.
# Strip --project from the forwarded arguments; native dispatch receives the
# absolute selection explicitly and raw commands use the exported metadata.
hdlforge_select_project() {
    local explicit_project=""
    local has_explicit_project=false
    local status
    HDLFORGE_LAUNCH_DIR="$(pwd -P)"
    PROJECT_FILE_PATH=""
    PROJECT_DIR="$HDLFORGE_LAUNCH_DIR"
    TOOL_NAME=""
    HDLFORGE_PROJECT_ARGS=()

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --)
                HDLFORGE_PROJECT_ARGS+=("$@")
                break
                ;;
            --project)
                if [ "$#" -lt 2 ] || [ -z "$2" ] || [[ "$2" == -* ]]; then
                    echo "error: --project requires a file" >&2
                    return 1
                fi
                explicit_project="$2"
                has_explicit_project=true
                shift 2
                ;;
            --project=*)
                explicit_project="${1#*=}"
                has_explicit_project=true
                shift
                ;;
            --tool=*)
                TOOL_NAME="${1#*=}"
                HDLFORGE_PROJECT_ARGS+=(--tool "$TOOL_NAME")
                shift
                ;;
            --tool|--cmd|--append|--eval_json|--env-python|--env-path|--env-var|--flags|--file|--lint-file|--vcdfilename)
                # Opaque argument values must not be interpreted as --project.
                HDLFORGE_PROJECT_ARGS+=("$1")
                if [ "$#" -ge 2 ]; then
                    [ "$1" != --tool ] || TOOL_NAME="$2"
                    HDLFORGE_PROJECT_ARGS+=("$2")
                    shift
                fi
                shift
                ;;
            *)
                HDLFORGE_PROJECT_ARGS+=("$1")
                shift
                ;;
        esac
    done

    if [ "$has_explicit_project" = true ]; then
        if [ -z "$explicit_project" ]; then
            echo "error: --project requires a file" >&2
            return 1
        fi
        PROJECT_FILE_PATH="$(resolve_working_path "$explicit_project" "$HDLFORGE_LAUNCH_DIR")" || return 1
        if [ ! -f "$PROJECT_FILE_PATH" ]; then
            echo "error: project file not found: $PROJECT_FILE_PATH" >&2
            return 1
        fi
    elif PROJECT_FILE_PATH="$(hdlforge_discover_project "$HDLFORGE_LAUNCH_DIR")"; then
        :
    else
        status=$?
        [ "$status" -eq 1 ] || return "$status"
    fi

    if [ -n "$PROJECT_FILE_PATH" ]; then
        PROJECT_DIR="$(dirname "$PROJECT_FILE_PATH")"
    fi
    export HDLFORGE_PROJECT_FILE="$PROJECT_FILE_PATH"
    export ROOT_FOLDER="$PROJECT_DIR"
    export HDLFORGE_ORIG_DIR="$HDLFORGE_LAUNCH_DIR"
    hdlforge_normalize_file_arguments "${HDLFORGE_PROJECT_ARGS[@]}"
}

# Preserve invocation-relative source lists and captures when selecting another
# project directory. Resolve each source independently, without shell globbing.
hdlforge_resolve_source_list() {
    local value="$1"
    local item resolved=""
    local -a items
    IFS=',' read -r -a items <<< "$value"
    for item in "${items[@]}"; do
        item="${item#"${item%%[![:space:]]*}"}"
        item="${item%"${item##*[![:space:]]}"}"
        [ -n "$item" ] || continue
        item="$(resolve_working_path "$item" "$HDLFORGE_LAUNCH_DIR")" || return 1
        resolved="${resolved:+$resolved,}$item"
    done
    printf '%s' "$resolved"
}

hdlforge_normalize_file_arguments() {
    local flag value
    HDLFORGE_PROJECT_ARGS=()
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --)
                HDLFORGE_PROJECT_ARGS+=("$@")
                break
                ;;
            --vcdfilename|--vcdfilename=*|--lint-file|--lint-file=*|--file|--file=*)
                flag="${1%%=*}"
                if [[ "$1" == *=* ]]; then
                    value="${1#*=}"
                elif [ "$#" -ge 2 ]; then
                    value="$2"
                    shift
                else
                    HDLFORGE_PROJECT_ARGS+=("$1")
                    break
                fi
                if [ "$flag" = --vcdfilename ]; then
                    value="$(resolve_working_path "$value" "$HDLFORGE_LAUNCH_DIR")" || return 1
                elif [ "$TOOL_NAME" = Verilator ] && [ "$PROJECT_DIR" != "$HDLFORGE_LAUNCH_DIR" ]; then
                    value="$(hdlforge_resolve_source_list "$value")" || return 1
                fi
                HDLFORGE_PROJECT_ARGS+=("$flag" "$value")
                ;;
            --cmd|--append|--eval_json|--env-python|--env-path|--env-var|--flags|--tool)
                HDLFORGE_PROJECT_ARGS+=("$1")
                if [ "$#" -ge 2 ]; then
                    HDLFORGE_PROJECT_ARGS+=("$2")
                    shift
                fi
                ;;
            *) HDLFORGE_PROJECT_ARGS+=("$1") ;;
        esac
        shift
    done
}

# Environment bootstrap consumes the selection above; it never discovers a
# second project with different precedence from the command being executed.
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
    project_json="${PROJECT_FILE_PATH:-}"
    [[ "$project_json" == *.json ]] || project_json=""
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
