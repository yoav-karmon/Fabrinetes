unset FABRINETES_ROOT
export FABRINETES="${FABRINETES:-$HOME/repo/fpga/git-sub-module/Fabrinetes}"
export HDLFORGE="$FABRINETES/hdlforge/project_setup"
source "$HDLFORGE/bashrc-func"
add_to_path "$HDLFORGE"
