# Runtime logic for hdlforge bash completion.
# This file is sourced on every completion call so edits here are picked up
# immediately by shells that already loaded hdlforge_completion.bash.

_hdlforge_runtime_complete() {
    local script_dir backend
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    backend="$script_dir/hdlforge_completion_backend.py"
    [[ -f "$backend" ]] || return

    local -a lines display_args=()
    # COMP_TYPE '?' lists choices after successive tabs. Only that display
    # path receives labels; normal and menu completion insert plain tokens.
    [[ "${COMP_TYPE:-9}" == 63 ]] && display_args=(--display-table --columns "${COLUMNS:-80}")
    if [[ -n "${HDLFORGE_COMPLETION_DEBUG:-}" ]]; then
        printf '[hdlforge completion] runtime cwd=%s cword=%s\n' "$PWD" "$COMP_CWORD" >&2
        if ! mapfile -t lines < <(python3 "$backend" --cwd "$PWD" --comp-cword "$COMP_CWORD" "${display_args[@]}" -- "${COMP_WORDS[@]}"); then
            COMPREPLY=()
            return
        fi
    elif ! mapfile -t lines < <(python3 "$backend" --cwd "$PWD" --comp-cword "$COMP_CWORD" "${display_args[@]}" -- "${COMP_WORDS[@]}" 2>/dev/null); then
        COMPREPLY=()
        return
    fi

    COMPREPLY=()
    local meta filenames nospace start_index
    meta="${lines[0]}"
    filenames=0
    nospace=0
    start_index=0

    if [[ "$meta" == __META__* ]]; then
        filenames="${meta#*filenames=}"
        filenames="${filenames%% *}"
        nospace="${meta#*nospace=}"
        nospace="${nospace%% *}"
        start_index=1
    fi

    local idx
    local -a display_lines=()
    for ((idx=start_index; idx < ${#lines[@]}; idx++)); do
        if [[ "${lines[idx]}" == __TABLE__$'\t'* ]]; then
            display_lines+=("${lines[idx]#*$'\t'}")
        else
            COMPREPLY+=("${lines[idx]}")
        fi
    done

    if [[ "${COMP_TYPE:-9}" == 63 && ${#COMPREPLY[@]} -gt 1 && ${#display_lines[@]} -gt 0 ]]; then
        COMPREPLY=("${display_lines[@]}")
        compopt -o nosort 2>/dev/null
    fi

    [[ "$filenames" == "1" ]] && compopt -o filenames 2>/dev/null
    [[ "$nospace" == "1" ]] && compopt -o nospace 2>/dev/null
}
