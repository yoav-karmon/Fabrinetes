# Runtime logic for hdlforge bash completion.
# This file is sourced on every completion call so edits here are picked up
# immediately by shells that already loaded hdlforge_completion.bash.

_hdlforge_runtime_complete() {
    local script_dir backend
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    backend="$script_dir/hdlforge_completion_backend.py"
    [[ -f "$backend" ]] || return

    local -a lines
    if [[ -n "${HDLFORGE_COMPLETION_DEBUG:-}" ]]; then
        printf '[hdlforge completion] runtime cwd=%s cword=%s\n' "$PWD" "$COMP_CWORD" >&2
        if ! mapfile -t lines < <(python3 "$backend" --cwd "$PWD" --comp-cword "$COMP_CWORD" -- "${COMP_WORDS[@]}"); then
            COMPREPLY=()
            return
        fi
    elif ! mapfile -t lines < <(python3 "$backend" --cwd "$PWD" --comp-cword "$COMP_CWORD" -- "${COMP_WORDS[@]}" 2>/dev/null); then
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
    for ((idx=start_index; idx < ${#lines[@]}; idx++)); do
        COMPREPLY+=("${lines[idx]}")
    done

    [[ "$filenames" == "1" ]] && compopt -o filenames 2>/dev/null
    [[ "$nospace" == "1" ]] && compopt -o nospace 2>/dev/null
}
