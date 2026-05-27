source /etc/bashrc-func

export FABRINETES="${FABRINETES:-$HOME/repo/fpga/git-sub-module/Fabrinetes}"
export FABRINETES_ROOT="${FABRINETES_ROOT:-$FABRINETES}"
export HDLFORGE="$FABRINETES/hdlforge/project_setup"

if [ -f /DATA/amd/2025.1/Vivado/settings64.sh ]; then
    # shellcheck disable=SC1091
    source /DATA/amd/2025.1/Vivado/settings64.sh
fi

export PATH=$(remove_duplicates_from_path "$PATH")
export PYTHONPATH=$(remove_duplicates_from_path "${PYTHONPATH:-}")

add_to_path "$HDLFORGE"
add_to_path "$HOME/.local/bin"
