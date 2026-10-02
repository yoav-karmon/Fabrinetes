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
            --tool|--cmd|--eval_json|--env-python|--env-path|--env-var|--flags|--file|--lint-file|--vcdfilename)
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
            --cmd|--eval_json|--env-python|--env-path|--env-var|--flags|--tool)
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

    "$HDLFORGE_JQ" -c --arg host "$host_name" --arg user "$user_name" \
        '.settings.env[$host][$user] // empty' < "$project_json"
}

# Validate complete layers before applying any environment mutation.
hdlforge_validate_environment() {
    local environment_json="$1"
    "$HDLFORGE_JQ" -e '
        type == "object" and
        all((.path // []), (.pythonpath // []);
            type == "array" and all(.[]; type == "string" and length > 0
                and (contains(":") or contains("\n") | not)
                and (explode | index(0) == null))) and
        ((.variables // {}) | type == "object" and all(to_entries[];
            (.key | test("^[A-Za-z_][A-Za-z0-9_]*$")) and
            (.key | test("^(PATH|PYTHONPATH|REPO_TOP|ROOT_FOLDER|FABRINETES|HDLFORGE.*|BASH.*|UID|EUID|PPID|SHELLOPTS)$") | not) and
            (.value | type == "string" and (explode | index(0) == null)))) and
        ((.tools // {}) | type == "object" and all(.[]; type == "string"))
    ' <<< "$environment_json" >/dev/null || {
        echo "error: invalid environment layer (path arrays, literal variables, or tool paths)" >&2
        return 1
    }
}

# Export literal values and warn only when an existing value actually changes.
# Do not print values: configuration may contain credentials or license paths.
hdlforge_export_variable() {
    local environment_name="$1" environment_value="$2" environment_layer="$3"
    if [[ -v "$environment_name" ]] && [ "${!environment_name}" != "$environment_value" ]; then
        if [ "${HDLFORGE_NESTED_CALL:-0}" = 1 ] && [ "${HDLFORGE_ALLOW_ENV_OVERWRITE:-0}" != 1 ]; then
            printf 'warning: preserving inherited environment variable %s; use --allow-env-overwrite to replace it\n' "$environment_name" >&2
            return 0
        fi
        printf 'warning: %s overrides environment variable %s\n' "$environment_layer" "$environment_name" >&2
    fi
    declare -gx "$environment_name=$environment_value"
}

# Layer paths are relative to the file that owns them. Existing helpers prepend
# in declaration order, then remove duplicate entries while keeping precedence.
hdlforge_apply_json_environment() {
    local env_json="$1" jq_bin="$2" base_dir="$3" layer="$4"
    local entry tool_path variable_name variable_value
    while IFS= read -r -d '' entry; do
        entry="$(resolve_working_path "$entry" "$base_dir")" || return 1
        add_to_path "$entry"
    done < <("$jq_bin" -j '.path[]? | ., "\u0000"' <<< "$env_json")
    while IFS= read -r -d '' entry; do
        entry="$(resolve_working_path "$entry" "$base_dir")" || return 1
        add_to_pythonpath "$entry"
    done < <("$jq_bin" -j '.pythonpath[]? | ., "\u0000"' <<< "$env_json")

    tool_path="$("$jq_bin" -r '.tools.vivado // empty' <<< "$env_json")"
    if [ -n "$tool_path" ]; then
        tool_path="$(resolve_working_path "$tool_path" "$base_dir")" || return 1
        if [ "${HDLFORGE_NESTED_CALL:-0}" = 1 ] && [ "${HDLFORGE_ALLOW_ENV_OVERWRITE:-0}" != 1 ] \
            && [ -n "${VIVADO_SETTINGS:-}" ] && [ "$VIVADO_SETTINGS" != "$tool_path" ]; then
            printf 'warning: preserving inherited Vivado environment; use --allow-env-overwrite to replace it\n' >&2
            tool_path="$VIVADO_SETTINGS"
        fi
        [ -f "$tool_path" ] || { echo "error: Vivado settings not found: $tool_path" >&2; return 1; }
        # Source each settings file once in a nested command chain.
        if [ "${HDLFORGE_VIVADO_SETTINGS_LOADED:-}" != "$tool_path" ]; then
            source "$tool_path" >&2 || return 1
            export HDLFORGE_VIVADO_SETTINGS_LOADED="$tool_path"
        fi
        export VIVADO_SETTINGS="$tool_path"
    fi
    tool_path="$("$jq_bin" -r '.tools.verilator // empty' <<< "$env_json")"
    if [ -n "$tool_path" ]; then
        tool_path="$(resolve_working_path "$tool_path" "$base_dir")" || return 1
        [ -x "$tool_path" ] || { echo "error: Verilator is unavailable at $tool_path" >&2; return 1; }
        if ! "$jq_bin" -e '.variables // {} | has("VERILATOR_BIN")' <<< "$env_json" >/dev/null; then
            hdlforge_export_variable VERILATOR_BIN "$tool_path" "$layer tools"
        fi
        add_to_path "${tool_path%/*}"
    fi
    while IFS= read -r -d '' variable_name && IFS= read -r -d '' variable_value; do
        hdlforge_export_variable "$variable_name" "$variable_value" "$layer"
    done < <("$jq_bin" -j '.variables // {} | to_entries[] | .key, "\u0000", .value, "\u0000"' <<< "$env_json")
    clean_path
    clean_pythonpath
}

# Clear caller exports in this process only. Preserve explicit runtime access
# and the launcher metadata computed before bootstrap; reconstruct all tooling.
hdlforge_clear_environment() {
    local environment_name
    while IFS= read -r environment_name; do
        case "$environment_name" in
            HOME|USER|LOGNAME|SHELL|TERM|COLORTERM|DISPLAY|WAYLAND_DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR|LANG|LANGUAGE|LC_*|TZ|TMPDIR|TMP|TEMP|SSH_AUTH_SOCK|SSH_AGENT_PID)
                ;;
            PWD|OLDPWD|SHLVL|_|BASHOPTS|SHELLOPTS|UID|EUID|PPID)
                ;;
            FABRINETES|HDLFORGE|HDLFORGE_INSTALL_DIR|ROOT_FOLDER|HDLFORGE_PROJECT_FILE|HDLFORGE_ORIG_DIR|HDLFORGE_NOPRINT|HDLFORGE_DRY_RUN)
                ;;
            *) unset -v "$environment_name" 2>/dev/null || export -n "$environment_name" ;;
        esac
    done < <(compgen -e)
}

# Bootstrap once per command chain, then apply the selected project's overlay
# on every invocation. HDLFORGE_CALLED is published only after success.
hdlforge_prepare_environment() {
    local installation_dir="$HDLFORGE_INSTALL_DIR" installation_root="$FABRINETES"
    local repo_json="${HDLFORGE_ENV_REPO_JSON:-}" project_json="${PROJECT_FILE_PATH:-}"
    local repo_environment="{}" project_environment="{}" repo_root="${REPO_TOP:-}"
    local selected_host="${HDLFORGE_SELECTED_HOST:-${HOST_MACHINE:-}}"
    local selected_user="${HDLFORGE_SELECTED_USER:-${HDLFORGE_HOST_USER:-}}"
    local jq_bin first_launch=false
    local parent_name parent_path="${PATH:-}" parent_pythonpath="${PYTHONPATH:-}"
    local -A parent_values=()
    # Vendor setup scripts can export or unset variables too. Preserve the
    # complete incoming nested environment, not only JSON-assigned keys.
    if [ "${HDLFORGE_CALLED:-0}" = 1 ] && [ "${HDLFORGE_ALLOW_ENV_OVERWRITE:-0}" != 1 ]; then
        while IFS= read -r parent_name; do
            case "$parent_name" in
                HDLFORGE*|REPO_TOP|ROOT_FOLDER|FABRINETES|PATH|PYTHONPATH|PWD|OLDPWD|SHLVL|_|BASHOPTS|SHELLOPTS) ;;
                *) parent_values["$parent_name"]="${!parent_name}" ;;
            esac
        done < <(compgen -e)
    fi
    source "$installation_dir/bashrc-func" || return 1
    jq_bin="${HDLFORGE_JQ:-$(type -P jq)}"
    [ -x "$jq_bin" ] || { echo "error: jq is required on the incoming PATH" >&2; return 1; }
    jq_bin="$(realpath -s "$jq_bin")" || return 1
    export HDLFORGE_JQ="$jq_bin"
    [[ "$project_json" == *.json ]] || project_json=""

    if [ "${HDLFORGE_CALLED:-0}" != "1" ]; then
        first_launch=true
        repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
            echo "error: HDLForge must run inside a Git repository" >&2; return 1;
        }
        selected_host="${HOST_MACHINE:-$(hostname -s)}"
        selected_user="${HDLFORGE_HOST_USER:-$(id -un)}"
        export REPO_TOP="$repo_root"
        repo_json="$(hdlforge_find_repo_environment_project)" || return 1
        repo_environment="$(hdlforge_read_json_environment "$repo_json" "$selected_host" "$selected_user")" || return 1
        [ -n "$repo_environment" ] || repo_environment='{}'
        hdlforge_validate_environment "$repo_environment" || return 1
    fi
    if [ -n "$project_json" ] && [ "$project_json" != "$repo_json" ]; then
        project_environment="$(hdlforge_read_json_environment "$project_json" "$selected_host" "$selected_user")" || return 1
        [ -n "$project_environment" ] || project_environment='{}'
        hdlforge_validate_environment "$project_environment" || return 1
    fi

    if [ "$first_launch" = true ]; then
        hdlforge_clear_environment
        export REPO_TOP="$repo_root" HDLFORGE_JQ="$jq_bin"
        export FABRINETES="$installation_root" HDLFORGE="$installation_dir"
        set_base_path "/usr/bin:/bin"
        set_base_pythonpath ""
        add_to_path "$installation_dir"
        export HDLFORGE_INHERITED_PATH="$PATH" HDLFORGE_INHERITED_PYTHONPATH=""
        export HDLFORGE_BOOTSTRAP_PATH="$PATH" HDLFORGE_BOOTSTRAP_PYTHONPATH=""
        hdlforge_apply_json_environment "$repo_environment" "$jq_bin" "$repo_root" "repository" || return 1
        export HDLFORGE_NESTED_CALL=0
    else
        export HDLFORGE_NESTED_CALL=1
    fi

    export HDLFORGE_SELECTED_HOST="$selected_host" HDLFORGE_SELECTED_USER="$selected_user"
    export HDLFORGE_SELECTED_HOST_AND_USER="$selected_host:$selected_user"
    export HDLFORGE_ENV_REPO_JSON="$repo_json" HDLFORGE_ENV_PROJECT_JSON="${project_json:-$repo_json}"
    if [ -n "$project_json" ] && [ "$project_json" != "$repo_json" ]; then
        hdlforge_apply_json_environment "$project_environment" "$jq_bin" "$PROJECT_DIR" "project" || return 1
    fi
    if [ "$first_launch" != true ] && [ "${HDLFORGE_ALLOW_ENV_OVERWRITE:-0}" != 1 ]; then
        for parent_name in "${!parent_values[@]}"; do
            if [[ ! -v "$parent_name" ]] || [ "${!parent_name}" != "${parent_values[$parent_name]}" ]; then
                printf 'warning: preserving inherited environment variable %s after tool setup\n' "$parent_name" >&2
                declare -gx "$parent_name=${parent_values[$parent_name]}"
            fi
        done
        PATH="$(remove_duplicates_from_path "$PATH:$parent_path")"
        PYTHONPATH="$(remove_duplicates_from_path "${PYTHONPATH:-}:$parent_pythonpath")"
        export PATH PYTHONPATH
    fi
    export HDLFORGE_CALLED=1
}

# Command-line overlays and environment inspection share the startup helpers.
hdlforge_append_unique() {
    local array_name="$1"
    local value="$2"
    local label="${3:-HDLForge env path}"
    local -n target_array="$array_name"
    local existing

    [ -n "$value" ] || return 0
    for existing in "${target_array[@]}"; do
        if [ "$existing" = "$value" ]; then
            return 0
        fi
    done
    target_array+=("$value")
    return 0
}

hdlforge_join_colon() {
    local joined=""
    local value
    for value in "$@"; do
        [ -n "$value" ] || continue
        if [ -z "$joined" ]; then
            joined="$value"
        else
            joined="${joined}:$value"
        fi
    done
    printf '%s' "$joined"
}

hdlforge_resolve_project_path() {
    resolve_working_path "$1" "$ROOT_FOLDER"
}

hdlforge_path_contains() {
    local path_list="$1"
    local path_to_find="$2"
    local path_value
    local old_ifs="$IFS"

    IFS=':'
    for path_value in $path_list; do
        if [ "$path_value" = "$path_to_find" ]; then
            IFS="$old_ifs"
            return 0
        fi
    done
    IFS="$old_ifs"
    return 1
}

hdlforge_print_environment_list() {
    local name="$1"
    local value="$2"
    local inherited="$3"
    local bootstrap="$4"
    local injected="$5"
    local entry
    local index=0
    local source

    printf '%s (lookup order):\n' "$name"
    if [ -z "$value" ]; then
        printf '  (empty)\n'
        return 0
    fi
    local IFS=':'
    for entry in $value; do
        [ -n "$entry" ] || continue
        index=$((index + 1))
        source="repository initializer"
        if hdlforge_path_contains "$injected" "$entry"; then
            if [ "$name" = PATH ]; then
                source="HDLForge --env-path"
            else
                source="HDLForge --env-python"
            fi
        elif [ "$entry" = "$HDLFORGE_INSTALL_DIR" ]; then
            source="HDLForge launcher"
        elif [ -n "${REPO_TOP:-}" ] && [ "$entry" = "$REPO_TOP/tools/tool_box" ]; then
            source="repository tools"
        elif [[ "$entry" == /DATA/amd/*/Vivado/* || "$entry" == /DATA/amd/*/Vitis/* ]]; then
            source="project JSON: tools.vivado"
        elif hdlforge_path_contains "$inherited" "$entry"; then
            source="HDLForge base environment"
        elif hdlforge_path_contains "$bootstrap" "$entry"; then
            source="HDLForge bootstrap"
        fi
        printf '  %2d. %-70s [%s]\n' "$index" "$entry" "$source"
    done
}

hdlforge_print_tool_location() {
    local tool_name="$1"
    local tool_path tool_source

    tool_path="$(command -v "$tool_name" 2>/dev/null || true)"
    if [ -z "$tool_path" ]; then
        printf '  %-10s unavailable\n' "$tool_name"
        return 0
    fi

    tool_source="PATH"
    case "$tool_path" in
        /usr/bin/verilator)
            if [ "${VERILATOR_BIN:-}" = "$tool_path" ]; then
                tool_source="project JSON: tools.verilator"
            else
                tool_source="HDLForge base environment"
            fi
            ;;
        /DATA/amd/*/Vivado/*)
            tool_source="project JSON: tools.vivado"
            ;;
    esac
    printf '  --tool %-9s uses %-62s [%s]\n' "$tool_name" "$tool_path" "$tool_source"
}

hdlforge_print_environment() {
    printf 'HDLForge selected environment\n'
    printf '  Repository top: %s\n' "${REPO_TOP:-n/a}"
    printf '  Project folder: %s\n' "${ROOT_FOLDER:-n/a}"
    printf '  Repository JSON: %s\n' "${HDLFORGE_ENV_REPO_JSON:-n/a}"
    printf '  Project JSON: %s\n' "${HDLFORGE_ENV_PROJECT_JSON:-n/a}"
    printf '  Active host/user: %s\n\n' "${HDLFORGE_SELECTED_HOST_AND_USER:-unknown}"
    if [ "${HDLFORGE_NESTED_CALL:-0}" = "1" ]; then
        printf '  WARNING: nested HDLForge call; this report reuses the parent environment.\n\n'
    fi
    printf 'Tool commands:\n'
    hdlforge_print_tool_location vivado
    hdlforge_print_tool_location verilator
    printf '\n'
    hdlforge_print_environment_list PATH "$PATH" "${HDLFORGE_INHERITED_PATH:-}" \
        "${HDLFORGE_BOOTSTRAP_PATH:-}" "${HDLFORGE_ADD_PATH:-}"
    printf '\n'
    hdlforge_print_environment_list PYTHONPATH "${PYTHONPATH:-}" "${HDLFORGE_INHERITED_PYTHONPATH:-}" \
        "${HDLFORGE_BOOTSTRAP_PYTHONPATH:-}" "${HDLFORGE_ADD_PYTHONPATH:-}"
}

hdlforge_print_all_host_and_user_environments() {
    local host_and_user host_name user_name index
    local -a host_and_users

    if [ -z "${HDLFORGE_ENV_PROJECT_JSON:-}" ]; then
        echo "error: select a project .hdlforge.json to list host/user environments" >&2
        return 1
    fi

    mapfile -t host_and_users < <({
        hdlforge_list_host_and_users "$HDLFORGE_ENV_REPO_JSON"
        if [ "$HDLFORGE_ENV_PROJECT_JSON" != "$HDLFORGE_ENV_REPO_JSON" ]; then
            hdlforge_list_host_and_users "$HDLFORGE_ENV_PROJECT_JSON"
        fi
    } | sort -u)
    if [ "${#host_and_users[@]}" -eq 0 ]; then
        echo "error: this repository does not define any HDLForge host/user environments" >&2
        return 1
    fi

    printf 'Configured HDLForge host/user environments (%d):\n' "${#host_and_users[@]}"
    for index in "${!host_and_users[@]}"; do
        if [ "${host_and_users[index]}" = "${HDLFORGE_SELECTED_HOST_AND_USER:-}" ]; then
            printf '  %d. %s  [ACTIVE]\n' "$((index + 1))" "${host_and_users[index]}"
        else
            printf '  %d. %s\n' "$((index + 1))" "${host_and_users[index]}"
        fi
    done

    for index in "${!host_and_users[@]}"; do
        host_and_user="${host_and_users[index]}"
        [ -n "$host_and_user" ] || continue
        host_name="${host_and_user%%:*}"
        user_name="${host_and_user#*:}"
        if [ "$host_and_user" = "${HDLFORGE_SELECTED_HOST_AND_USER:-}" ]; then
            printf '\n===== HDLForge environment %d/%d: %s [ACTIVE] =====\n' \
                "$((index + 1))" "${#host_and_users[@]}" "$host_and_user"
        else
            printf '\n===== HDLForge environment %d/%d: %s =====\n' \
                "$((index + 1))" "${#host_and_users[@]}" "$host_and_user"
        fi
        env -u HDLFORGE_CALLED -u HDLFORGE_NESTED_CALL \
            HOST_MACHINE="$host_name" HDLFORGE_HOST_USER="$user_name" \
            "$0" --tool path_manager show || return $?
    done
}

hdlforge_find_project_json() {
    if [[ "${PROJECT_FILE_PATH:-}" == *.json ]] && [ -f "$PROJECT_FILE_PATH" ]; then
        printf '%s\n' "$PROJECT_FILE_PATH"
        return 0
    fi
    echo "error: no selected project JSON; use --project <file>" >&2
    return 1
}

hdlforge_resolve_env_json_arg() {
    local json_text="$1"
    local expected_type="$2"
    local source_label="${3:-HDLForge env JSON}"
    local clean_json
    local project_json
    local json_path
    local leaf_json
    local raw_json_was_valid=false

    json_path="${json_text#.}"
    project_json="$(hdlforge_find_project_json 2>/dev/null || true)"
    if [ -n "$json_path" ] && [ -n "$project_json" ]; then
        leaf_json="$("$HDLFORGE_JQ" -c --arg json_path "$json_path" 'getpath($json_path | split("."))' < "$project_json" 2>/dev/null || true)"
        if [ -n "$leaf_json" ] && [ "$leaf_json" != "null" ]; then
            if printf '%s' "$leaf_json" | jq -e --arg expected_type "$expected_type" 'type == $expected_type' >/dev/null 2>&1; then
                printf '%s' "$leaf_json"
                return 0
            fi
            echo "[!x!] $source_label project leaf validation failed: $json_path" >&2
            echo "[i] Expected JSON type: $expected_type" >&2
            return 1
        fi
    fi

    if clean_json="$(printf '%s' "$json_text" | jq -c '.' 2>/dev/null)"; then
        raw_json_was_valid=true
        if printf '%s' "$clean_json" | jq -e --arg expected_type "$expected_type" 'type == $expected_type' >/dev/null 2>&1; then
            printf '%s' "$clean_json"
            return 0
        fi
    fi

    if [ "$raw_json_was_valid" = true ]; then
        echo "[!x!] $source_label validation failed" >&2
        echo "[i] Raw JSON was valid, but expected JSON type: $expected_type" >&2
        return 1
    fi

    echo "[!x!] $source_label is neither raw JSON nor a project JSON leaf: $json_text" >&2
    echo "[i] Use a project leaf like verilator.config.sim_targets.full_sim.env.pythonpath" >&2
    echo "[i] Or pass raw JSON such as [\"sources/tests\"]" >&2
    return 1
}

hdlforge_validate_env_key() {
    local key="$1"
    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "[!x!] Invalid HDLForge env key: $key" >&2
        echo "[i] Env keys must match [A-Za-z_][A-Za-z0-9_]*" >&2
        return 1
    fi
    case "$key" in
        PATH|PYTHONPATH|REPO_TOP|ROOT_FOLDER|FABRINETES|HDLFORGE*|BASH*|UID|EUID|PPID|SHELLOPTS)
            printf 'error: reserved environment variable: %s\n' "$key" >&2
            return 1
            ;;
    esac
    return 0
}

hdlforge_collect_env_pair() {
    local key="$1"
    local value="$2"
    local index

    hdlforge_validate_env_key "$key" || return 1

    for index in "${!HDLFORGE_COLLECTED_ENV_KEYS[@]}"; do
        if [ "${HDLFORGE_COLLECTED_ENV_KEYS[$index]}" = "$key" ]; then
            if [ "${HDLFORGE_COLLECTED_ENV_VALUES[$index]}" = "$value" ]; then
                return 0
            fi
            printf 'warning: command line overrides environment variable %s\n' "$key" >&2
            HDLFORGE_COLLECTED_ENV_VALUES[$index]="$value"
            return 0
        fi
    done

    HDLFORGE_COLLECTED_ENV_KEYS+=("$key")
    HDLFORGE_COLLECTED_ENV_VALUES+=("$value")
}

hdlforge_collect_env_var_json() {
    local json_text="$1"
    local source_label="${2:-HDLForge env var JSON array}"
    local clean_json
    local entry
    local key
    local value

    [ -n "$json_text" ] || return 0
    clean_json="$(hdlforge_resolve_env_json_arg "$json_text" "array" "$source_label")" || return 1

    if ! printf '%s' "$clean_json" | jq -e '
        type == "array"
        and all(.[]; type == "object" and length == 1
            and all(.[]; type == "string" and (explode | index(0) == null)))
    ' >/dev/null 2>&1; then
        echo "[!x!] $source_label validation failed" >&2
        echo "[i] Expected a JSON array of single-key objects, e.g. [{\"FOO\":\"bar\"}]" >&2
        return 1
    fi

    while IFS= read -r -d '' key && IFS= read -r -d '' value; do
        hdlforge_collect_env_pair "$key" "$value" || return 1
    done < <(printf '%s' "$clean_json" | jq -j '.[] | to_entries[] | .key, "\u0000", .value, "\u0000"')
}

hdlforge_collect_path_array_json() {
    local json_text="$1"
    local array_name="$2"
    local label="$3"
    local source_label="${4:-HDLForge env path JSON array}"
    local clean_json
    local path_value
    local resolved_path

    [ -n "$json_text" ] || return 0
    clean_json="$(hdlforge_resolve_env_json_arg "$json_text" "array" "$source_label")" || return 1

    if ! printf '%s' "$clean_json" | jq -e '
        type == "array"
        and all(.[]; type == "string")
    ' >/dev/null 2>&1; then
        echo "[!x!] $source_label validation failed" >&2
        echo "[i] Expected a JSON array of strings, e.g. [\"sources/tests\"]" >&2
        return 1
    fi

    while IFS= read -r path_value; do
        [ -n "$path_value" ] || continue
        resolved_path="$(hdlforge_resolve_project_path "$path_value")"
        if [ ! -e "$resolved_path" ]; then
            echo "[!x!] HDLForge $label path does not exist: $resolved_path" >&2
            echo "[i] Relative $label paths are resolved from project folder: $ROOT_FOLDER" >&2
            return 1
        fi
        hdlforge_append_unique "$array_name" "$resolved_path" "$label"
    done < <(printf '%s' "$clean_json" | jq -r '.[]')
}

hdlforge_parse_env_args() {
    local args_filtered=()
    local arg
    local expect_value=""
    local seen_dd=false

    for arg in "$@"; do
        if [ "$seen_dd" = true ]; then
            args_filtered+=("$arg")
            continue
        fi

        if [ -n "$expect_value" ]; then
            case "$expect_value" in
                --env-python) HDLFORGE_ENV_PYTHON_JSONS+=("$arg") ;;
                --env-path) HDLFORGE_ENV_PATH_JSONS+=("$arg") ;;
                --env-var) HDLFORGE_ENV_VAR_JSONS+=("$arg") ;;
            esac
            expect_value=""
            continue
        fi

        case "$arg" in
            --)
                seen_dd=true
                args_filtered+=("$arg")
                ;;
            --env-python|--env-path|--env-var)
                expect_value="$arg"
                ;;
            *)
                args_filtered+=("$arg")
                ;;
        esac
    done

    if [ -n "$expect_value" ]; then
        echo "[!x!] $expect_value requires a value"
        exit 1
    fi

    set -- "${args_filtered[@]}"
    HDLFORGE_FILTERED_ARGS=("$@")
}

hdlforge_apply_env_state() {
    local json_arg
    local path_arg
    local env_key
    local env_value
    local index
    local carry_env_var_json
    local has_env_state=false

    hdlforge_parse_env_args "$@"

    if [ ${#HDLFORGE_ENV_PYTHON_JSONS[@]} -gt 0 ] \
        || [ ${#HDLFORGE_ENV_PATH_JSONS[@]} -gt 0 ] \
        || [ ${#HDLFORGE_ENV_VAR_JSONS[@]} -gt 0 ] \
        || [ -n "${HDLFORGE_ADD_ENV_VAR_JSON:-}" ]; then
        if ! command -v jq >/dev/null 2>&1; then
            echo "[!x!] jq is required for HDLForge env handling"
            exit 1
        fi
    fi

    # Inherited additions are already present in this process. Replaying their
    # old JSON values here would undo an explicitly permitted project overlay.

    for json_arg in "${HDLFORGE_ENV_PYTHON_JSONS[@]}"; do
        hdlforge_collect_path_array_json \
            "$json_arg" \
            HDLFORGE_COLLECTED_PYTHONPATHS \
            "PYTHONPATH" \
            "HDLForge --env-python array" || exit 1
    done

    for json_arg in "${HDLFORGE_ENV_PATH_JSONS[@]}"; do
        hdlforge_collect_path_array_json \
            "$json_arg" \
            HDLFORGE_COLLECTED_PATHS \
            "PATH" \
            "HDLForge --env-path array" || exit 1
    done

    for json_arg in "${HDLFORGE_ENV_VAR_JSONS[@]}"; do
        hdlforge_collect_env_var_json "$json_arg" "HDLForge --env-var array" || exit 1
    done

    for path_arg in "${HDLFORGE_COLLECTED_PYTHONPATHS[@]}"; do
        if hdlforge_path_contains "${PYTHONPATH:-}" "$path_arg"; then
            hdlforge_warn "[!] HDLForge env duplicate PYTHONPATH already present: $path_arg"
        fi
        add_to_pythonpath "$path_arg"
        has_env_state=true
    done

    for path_arg in "${HDLFORGE_COLLECTED_PATHS[@]}"; do
        if hdlforge_path_contains "$PATH" "$path_arg"; then
            hdlforge_warn "[!] HDLForge env duplicate PATH already present: $path_arg"
        fi
        add_to_path "$path_arg"
        has_env_state=true
    done

    for index in "${!HDLFORGE_COLLECTED_ENV_KEYS[@]}"; do
        env_key="${HDLFORGE_COLLECTED_ENV_KEYS[$index]}"
        env_value="${HDLFORGE_COLLECTED_ENV_VALUES[$index]}"
        hdlforge_export_variable "$env_key" "$env_value" "command line"
        HDLFORGE_COLLECTED_ENV_VALUES[$index]="${!env_key}"
        has_env_state=true
    done

    if command -v remove_duplicates_from_path >/dev/null 2>&1; then
        if [ -n "$PATH" ]; then
            export PATH="$(remove_duplicates_from_path "$PATH")"
        fi
        if [ -n "$PYTHONPATH" ]; then
            export PYTHONPATH="$(remove_duplicates_from_path "$PYTHONPATH")"
        fi
    fi

    if [ "$has_env_state" = true ]; then
        export HDLFORGE_ENV_STATE_ACTIVE=1
        export HDLFORGE_ADD_PYTHONPATH="$(hdlforge_join_colon "${HDLFORGE_COLLECTED_PYTHONPATHS[@]}")"
        export HDLFORGE_ADD_PATH="$(hdlforge_join_colon "${HDLFORGE_COLLECTED_PATHS[@]}")"
        if [ ${#HDLFORGE_COLLECTED_ENV_KEYS[@]} -gt 0 ]; then
            carry_env_var_json="$(jq -cn '[]')"
            for index in "${!HDLFORGE_COLLECTED_ENV_KEYS[@]}"; do
                env_key="${HDLFORGE_COLLECTED_ENV_KEYS[$index]}"
                env_value="${HDLFORGE_COLLECTED_ENV_VALUES[$index]}"
                carry_env_var_json="$(
                    jq -cn \
                        --argjson base "$carry_env_var_json" \
                        --arg key "$env_key" \
                        --arg value "$env_value" \
                        '$base + [{($key): $value}]'
                )"
            done
            export HDLFORGE_ADD_ENV_VAR_JSON="$carry_env_var_json"
        else
            unset HDLFORGE_ADD_ENV_VAR_JSON
        fi
        unset HDLFORGE_ADD_ENV_JSON
    else
        unset HDLFORGE_ENV_STATE_ACTIVE
        unset HDLFORGE_ADD_PYTHONPATH
        unset HDLFORGE_ADD_PATH
        unset HDLFORGE_ADD_ENV_JSON
        unset HDLFORGE_ADD_ENV_VAR_JSON
    fi

    set -- "${HDLFORGE_FILTERED_ARGS[@]}"
    HDLFORGE_FILTERED_ARGS=("$@")
}
