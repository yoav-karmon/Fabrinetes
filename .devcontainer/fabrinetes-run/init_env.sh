source /etc/bashrc-func

unset FABRINETES_ROOT
export FABRINETES="${FABRINETES:-$HOME/repo/fpga/git-sub-module/Fabrinetes}"
export HDLFORGE="$FABRINETES/hdlforge/project_setup"
export HOSTNAME_server="${HOSTNAME_server:-${HOSTNAME:-Fabrinetes}}"
export VIVADO_SETTINGS="${VIVADO_SETTINGS:-}"

if [ -n "$VIVADO_SETTINGS" ] && [ -f "$VIVADO_SETTINGS" ]; then
    # shellcheck disable=SC1091
    source "$VIVADO_SETTINGS"
fi

export PATH=$(remove_duplicates_from_path "$PATH")
export PYTHONPATH=$(remove_duplicates_from_path "${PYTHONPATH:-}")

add_to_path "$HDLFORGE"
add_to_path "$HOME/.local/bin"
