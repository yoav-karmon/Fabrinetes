# must source bashrc-func here - it used in entry point
# Functions will be available from the parent shell context

# Global PATH setup for entire container (works across all repositories)
source /etc/bashrc-func
export HOSTNAME_server="363fpgadev-01"
export HDLFORGE="$HOME/repo/Fabrinetes/hdlforge/project_setup"
# License file path (adjust to your setup)
# export XILINXD_LICENSE_FILE="/DATA/repos/phy_project/Xilinx.lic"
# Git configuration for Cursor/VS Code attachment

# Clean duplicates from PATH/PYTHONPATH after Vivado settings (which modifies PATH directly)
# This ensures no duplicates even if Vivado adds paths that already exist
source /DATA/amd/2025.1/Vivado/settings64.sh 
export PATH=$(remove_duplicates_from_path "$PATH")
export PYTHONPATH=$(remove_duplicates_from_path "$PYTHONPATH")

# Python path for development
add_to_path "$HDLFORGE"
add_to_path "$HOME/.local/bin"
