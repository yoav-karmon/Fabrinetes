# Bash completion script for hdlforge
# Source this file in your .bashrc: source /path/to/hdlforge_completion.bash
# Or install to /etc/bash_completion.d/hdlforge

_HDLFORGE_COMPLETION_SOURCE="${BASH_SOURCE[0]}"
if [[ "$_HDLFORGE_COMPLETION_SOURCE" != /* ]]; then
    _HDLFORGE_COMPLETION_SOURCE="$PWD/$_HDLFORGE_COMPLETION_SOURCE"
fi
_HDLFORGE_COMPLETION_DIR="$(cd "$(dirname "$_HDLFORGE_COMPLETION_SOURCE")" && pwd)"
unset _HDLFORGE_COMPLETION_SOURCE

_hdlforge_completions() {
    local cur prev words cword
    _init_completion || return

    local runtime
    runtime="$_HDLFORGE_COMPLETION_DIR/hdlforge_completion_runtime.bash"
    [[ -f "$runtime" ]] || return

    # Source the runtime on every completion call so edits there take effect
    # immediately in shells that already loaded this stable wrapper.
    # shellcheck source=/dev/null
    source "$runtime"
    _hdlforge_runtime_complete
}

complete -F _hdlforge_completions hdlforge
