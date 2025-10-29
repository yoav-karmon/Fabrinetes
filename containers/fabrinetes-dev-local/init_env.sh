



# Add to PYTHONPATH (prepends REPO_TOP if path is relative)
add_to_pythonpath() {
    local path_to_add="$1"
    
    # Prepend REPO_TOP if path doesn't start with /
    if [ -n "$REPO_TOP" ] && [ "${path_to_add#/}" = "$path_to_add" ]; then
        path_to_add="$REPO_TOP/$path_to_add"
    fi
    
    export PYTHONPATH="${path_to_add}${PYTHONPATH:+:${PYTHONPATH}}"
}

# Add to PATH (prepends REPO_TOP if path is relative)
add_to_path() {
    local path_to_add="$1"
    
    # Prepend REPO_TOP if path doesn't start with /
    if [ -n "$REPO_TOP" ] && [ "${path_to_add#/}" = "$path_to_add" ]; then
        path_to_add="$REPO_TOP/$path_to_add"
    fi
    
    export PATH="${path_to_add}${PATH:+:${PATH}}"
}


#



# Global PATH setup for entire container (works across all repositories)
source /DATA/amd/2025.1/Vivado/settings64.sh 
export HDLFORGE="/DATA/repo/Fabrinetes/hdlforge/project_setup"
# License file path (adjust to your setup)
export XILINXD_LICENSE_FILE="/DATA/repos/phy_project/Xilinx.lic"
# Git configuration for Cursor/VS Code attachment
export GIT_CONFIG_GLOBAL="/home/yoav.karmon/.gitconfig"
export GIT_CONFIG_SYSTEM="/etc/gitconfig"
export GIT_AUTHOR_NAME="yoav.karmon"
export GIT_AUTHOR_EMAIL="yoav.karmon@363fpgadev-01.eh.local"
export GIT_COMMITTER_NAME="yoav.karmon"
export GIT_COMMITTER_EMAIL="yoav.karmon@363fpgadev-01.eh.local"
# Additional environment variables for development tools
export EDITOR="nano"
export PAGER="less"
# Ensure gitconfig exists for Cursor/VS Code
if [ ! -f "$HOME/.gitconfig" ]; then
    git config --global user.name "yoav.karmon"
    git config --global user.email "yoav.karmon@363fpgadev-01.eh.local"
    git config --global init.defaultBranch main
    git config --global core.autocrlf false
    git config --global core.filemode false
fi


# Python path for development
add_to_path "$HDLFORGE"
add_to_path "$HOME/.local/bin"



