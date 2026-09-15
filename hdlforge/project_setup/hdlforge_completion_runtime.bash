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
    [[ "${COMP_TYPE:-9}" == 63 ]] && display_args=(--describe)
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

    local idx description_record candidate description
    local -A descriptions=()
    for ((idx=start_index; idx < ${#lines[@]}; idx++)); do
        if [[ "${lines[idx]}" == __DESC__$'\t'* ]]; then
            description_record="${lines[idx]#*$'\t'}"
            candidate="${description_record%%$'\t'*}"
            descriptions["$candidate"]="${description_record#*$'\t'}"
        else
            COMPREPLY+=("${lines[idx]}")
        fi
    done

    if [[ "${COMP_TYPE:-9}" == 63 && ${#COMPREPLY[@]} -gt 1 && "$filenames" == 0 ]]; then
        local columns="${COLUMNS:-80}" longest=0 available label display_width
        for candidate in "${COMPREPLY[@]}"; do
            (( ${#candidate} > longest )) && longest=${#candidate}
        done
        (( longest > columns * 2 / 3 )) && longest=$((columns * 2 / 3))
        # Padding beyond half the terminal width makes Readline use one
        # column, without changing the user's global completion settings.
        display_width=$((columns / 2 + 1))
        for idx in "${!COMPREPLY[@]}"; do
            candidate="${COMPREPLY[idx]}"
            description="${descriptions[$candidate]:-}"
            label="$candidate"
            if (( ${#label} > longest )); then
                label="...${label: -$((longest - 3))}"
            fi
            if [[ -n "$description" ]]; then
                available=$((columns - longest - 4))
                if (( available > 4 )); then
                    if (( ${#description} > available )); then
                        description="${description:0:available-3}..."
                    fi
                    printf -v label '%-*s  %s' "$longest" "$label" "$description"
                fi
            fi
            printf -v 'COMPREPLY[idx]' '%-*s' "$display_width" "$label"
        done
        compopt -o nosort 2>/dev/null
    fi

    [[ "$filenames" == "1" ]] && compopt -o filenames 2>/dev/null
    [[ "$nospace" == "1" ]] && compopt -o nospace 2>/dev/null
}
