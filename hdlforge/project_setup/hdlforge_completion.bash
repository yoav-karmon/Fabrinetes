# Bash completion script for hdlforge
# Source this file in your .bashrc: source /path/to/hdlforge_completion.bash
# Or install to /etc/bash_completion.d/hdlforge

_hdlforge_completions() {
    local cur prev words cword
    _init_completion || return

    local script_dir runtime
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    runtime="$script_dir/hdlforge_completion_runtime.bash"
    [[ -f "$runtime" ]] || return

    # Source the runtime on every completion call so edits there take effect
    # immediately in shells that already loaded this stable wrapper.
    # shellcheck source=/dev/null
    source "$runtime"
    _hdlforge_runtime_complete
}

complete -F _hdlforge_completions hdlforge
