# Global PATH setup for entire container (works across all repositories)
export PATH="/opt/vivado/bin:$HOME/repo/Fabrinetes/source/project_setup:$HOME/.local/bin:$PATH"

# License file path (adjust to your setup)
export XILINXD_LICENSE_FILE="$HOME/repos/phy_project/Xilinx.lic"

# Git configuration for Cursor/VS Code attachment
export GIT_CONFIG_GLOBAL="/home/$USER/.gitconfig"
export GIT_CONFIG_SYSTEM="/etc/gitconfig"
export GIT_AUTHOR_NAME="$USER"
export GIT_AUTHOR_EMAIL="$USER@$(hostname)"
export GIT_COMMITTER_NAME="$USER"
export GIT_COMMITTER_EMAIL="$USER@$(hostname)"

# Ensure gitconfig exists for Cursor/VS Code
if [ ! -f "$HOME/.gitconfig" ]; then
    git config --global user.name "$USER"
    git config --global user.email "$USER@$(hostname)"
    git config --global init.defaultBranch main
    git config --global core.autocrlf false
    git config --global core.filemode false
fi

# Additional environment variables for development tools
export EDITOR="nano"
export PAGER="less"

# Python path for development
export PYTHONPATH="$HOME/repo/Fabrinetes/source/project_setup:$PYTHONPATH"
