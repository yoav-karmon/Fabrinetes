# Container Path Management System

## Overview

Fabrinetes implements a sophisticated **two-level path management system** that automatically configures environment variables based on context. This system ensures that tools work correctly across different repositories while maintaining global container-wide configurations.

## Architecture

### Two-Level System

1. **Global Container Level**: System-wide paths that work across all repositories
2. **Repository Level**: Dynamic paths that change based on the current Git repository

## Global Container Path Management

### Configuration File: `init_env.sh`

**Location**: `containers/my-project/init_env.sh`

This file sets **system-wide paths** for the entire container and works across **all repositories**.

### Key Components

#### 1. Global PATH Setup
```bash
# Global PATH setup for entire container (works across all repositories)
export PATH="/opt/vivado/bin:$HOME/repo/Fabrinetes/hdlforge/project_setup:$HOME/.local/bin:$PATH"
```

#### 2. License File Configuration
```bash
# License file path (adjust to your setup)
export XILINXD_LICENSE_FILE="$HOME/repos/phy_project/Xilinx.lic"
```

#### 3. Git Configuration for Cursor/VS Code
```bash
# Git configuration for Cursor/VS Code attachment
export GIT_CONFIG_GLOBAL="/home/yoav.karmon/.gitconfig"
export GIT_CONFIG_SYSTEM="/etc/gitconfig"
export GIT_AUTHOR_NAME="yoav.karmon"
export GIT_AUTHOR_EMAIL="yoav.karmon@363fpgadev-01.eh.local"
export GIT_COMMITTER_NAME="yoav.karmon"
export GIT_COMMITTER_EMAIL="yoav.karmon@363fpgadev-01.eh.local"

# Ensure gitconfig exists for Cursor/VS Code
if [ ! -f "$HOME/.gitconfig" ]; then
    git config --global user.name "yoav.karmon"
    git config --global user.email "yoav.karmon@363fpgadev-01.eh.local"
    git config --global init.defaultBranch main
    git config --global core.autocrlf false
    git config --global core.filemode false
fi
```

#### 4. Development Tools Configuration
```bash
# Additional environment variables for development tools
export EDITOR="nano"
export PAGER="less"

# Python path for development
export PYTHONPATH="$HOME/repo/Fabrinetes/source/project_setup:$PYTHONPATH"
```

### Adding Tools to Global PATH

To add tools to your container, you typically need to:

1. **Mount the tool** in your `config.toml`
2. **Add the mounted path** to `init_env.sh`

**Example - Adding Vivado:**
```toml
# In config.toml - mount Vivado installation
mounts = [
    "$HOME/AMD/Vivado/2021.2:/opt/vivado",  # Mount Vivado to /opt/vivado
    # ... other mounts
]
```

```bash
# In init_env.sh - add Vivado to PATH
export PATH="/opt/vivado/bin:$PATH"  # Add Vivado tools to system PATH
```

## Repository-Level Path Management

### Configuration File: Container bashrc

**Location**: Container's `~/.bashrc` (mounted from `bashrc-root`)

The bashrc includes the `update_repo_path()` function that provides **dynamic repository-aware path management**.

### Key Functions

#### 1. `update_repo_path()` Function

**Purpose**: Automatically detects and configures paths for the current Git repository.

**Features**:
- **Automatic Detection**: Uses `git rev-parse --show-toplevel` to detect current Git repository
- **Dynamic REPO_TOP**: Sets `REPO_TOP` environment variable to repository root
- **Repository-Specific Paths**: Sources repository-specific path files
- **Interactive Display**: Shows updated environment variables when run in interactive shells

**Function Implementation**:
```bash
update_repo_path() {
    # Require Bash
    if [ -z "$BASH_VERSION" ]; then
        echo "[X] This function requires Bash." >&2
        return 1
    fi

    # Detect if shell is interactive
    [[ $- == *i* ]] && is_interactive_shell=1 || is_interactive_shell=0

    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    
    if [[ -z "$repo_root" ]]; then
        [[ $is_interactive_shell -eq 1 ]] && echo "[!]  Not inside a Git repository."
        return 1
    fi
    export REPO_TOP="$repo_root"
    
    # Source repository-specific path files
    if [[ -f "$REPO_TOP/tools/update_paths.sh" ]]; then
        source "$REPO_TOP/tools/update_paths.sh"
        [[ $is_interactive_shell -eq 1 ]] && echo "[i] sourcing $REPO_TOP/tools/update_paths.sh"
    elif [[ $is_interactive_shell -eq 1 ]]; then
        echo "[i]  Missing $REPO_TOP/tools/update_paths.sh"
    fi

    # Source tool_box.sh if it exists
    if [[ -f "$REPO_TOP/tools/tool_box/tool_box.sh" ]]; then
        source "$REPO_TOP/tools/tool_box/tool_box.sh"
    elif [[ $is_interactive_shell -eq 1 ]]; then
        echo "[!]  Missing $REPO_TOP/tools/tool_box/tool_box.sh"
    fi

    [[ $is_interactive_shell -eq 1 ]] && echo "[v] REPO_TOP set to $REPO_TOP"
    
    # Print updated environment variables nicely
    if [[ $is_interactive_shell -eq 1 ]]; then
        echo ""
        print_key_env_vars
    fi
}
```

#### 2. Environment Variable Print Functions

**Purpose**: Display current environment variables for debugging and verification.

**Functions**:
- `print_env_vars()`: Prints ALL environment variables
- `print_key_env_vars()`: Prints only key environment variables

**Implementation**:
```bash
print_env_vars() {
    # Print ALL environment variables
    echo "=== All Environment Variables ==="
    env | sort | while IFS='=' read -r name value; do
        echo "$name: $value"
    done
    echo "=================================="
}

print_key_env_vars() {
    # Print only key environment variables (for quick reference)
    echo "=== Key Environment Variables ==="
    echo "PATH: $PATH"
    echo "PYTHONPATH: $PYTHONPATH"
    echo "REPO_TOP: $REPO_TOP"
    echo "GIT_CONFIG_GLOBAL: $GIT_CONFIG_GLOBAL"
    echo "GIT_AUTHOR_NAME: $GIT_AUTHOR_NAME"
    echo "GIT_AUTHOR_EMAIL: $GIT_AUTHOR_EMAIL"
    echo "GIT_COMMITTER_NAME: $GIT_COMMITTER_NAME"
    echo "GIT_COMMITTER_EMAIL: $GIT_COMMITTER_EMAIL"
    echo "EDITOR: $EDITOR"
    echo "PAGER: $PAGER"
    echo "BROWSER: $BROWSER"
    echo "XILINXD_LICENSE_FILE: $XILINXD_LICENSE_FILE"
    echo "=================================="
}
```

### Repository-Specific Path Files

Each repository can define its own path configuration through optional files:

#### 1. `tools/update_paths.sh` (Optional)

**Purpose**: Repository-specific PATH and PYTHONPATH configuration with **path clearing and restoration**.

**Key Features**:
- **Path Clearing**: Restores original paths before applying repository-specific changes
- **Duplicate Prevention**: Checks for existing paths to avoid duplicates
- **Original Path Preservation**: Saves original paths for restoration
- **Interactive Feedback**: Shows which paths were added (in interactive shells)

**Implementation Details**:
```bash
# Save original PYTHONPATH before any modification
if [ -z "${__ORIGINAL_PYTHONPATH+x}" ]; then
    __ORIGINAL_PYTHONPATH="$PYTHONPATH"
fi

# Save original PATH before any modification
if [ -z "${__ORIGINAL_PATH+x}" ]; then
    __ORIGINAL_PATH="$PATH"
fi

# Restore original paths before applying changes
export PYTHONPATH="$__ORIGINAL_PYTHONPATH"
export PATH="$__ORIGINAL_PATH"

# Add repository-specific paths (with duplicate checking)
add_to_pythonpath "$REPO_TOP/tests"
add_to_pythonpath "$REPO_TOP/tests/cocotb"
add_to_pythonpath "$REPO_TOP/fpga_projects/phy10gbaser/sources/PY/PACKET_BUILDER"
add_to_pythonpath "$REPO_TOP/fpga_projects/phy10gbaser/sources/PY"

add_to_path "$REPO_TOP/tools/tool_box"
```

**Path Clearing Logic**:
1. **Save Original**: Stores original `PYTHONPATH` and `PATH` on first run
2. **Restore Clean State**: Resets paths to original values before adding new ones
3. **Add Repository Paths**: Adds repository-specific paths with duplicate checking
4. **Prevent Duplicates**: Uses pattern matching to avoid adding existing paths
5. **Interactive Feedback**: Shows which paths were actually added

**Example**:
```bash
# First run - saves original paths
__ORIGINAL_PYTHONPATH="/home/user/repo/Fabrinetes/source/project_setup:"
__ORIGINAL_PATH="/opt/vivado/bin:/home/user/.local/bin:/usr/bin:/bin"

# Subsequent runs - restores original, then adds repository-specific
export PYTHONPATH="$__ORIGINAL_PYTHONPATH"  # Clear previous repository paths
export PATH="$__ORIGINAL_PATH"              # Clear previous repository paths

# Add new repository-specific paths
add_to_pythonpath "$REPO_TOP/tests"         # Adds if not already present
add_to_pythonpath "$REPO_TOP/tests/cocotb"  # Adds if not already present
add_to_path "$REPO_TOP/tools/tool_box"      # Adds if not already present
```

#### 2. `tools/tool_box/tool_box.sh` (Optional)

**Purpose**: Additional repository tools and configurations.

**Example**:
```bash
# Additional repository tools and configurations
source "$REPO_TOP/tools/tool_box/setup.sh"

# Repository-specific aliases
alias build="hdlforge Verilator --project $REPO_TOP/project.hdlforge.toml --step build"
alias sim="hdlforge Verilator --project $REPO_TOP/project.hdlforge.toml --step sim"
```

## How the System Works

### 1. Container Startup Sequence

1. **Container starts** → `init_env.sh` sets global paths
2. **User opens shell** → bashrc runs `update_repo_path()`
3. **Function detects** current Git repository
4. **Sets REPO_TOP** and sources repository-specific path files
5. **Displays environment** variables (in interactive shells)

### 2. Repository Switching

When switching between repositories:

1. **User changes directory** to different repository
2. **User runs** `update_repo_path`
3. **Function detects** new repository
4. **Updates REPO_TOP** and sources new repository-specific files
5. **Path Clearing**: Repository-specific files restore original paths before adding new ones
6. **Displays updated** environment variables

### 3. Interactive vs Non-Interactive Shells

- **Interactive shells**: Display status messages and environment variables
- **Non-interactive shells**: Silent operation for automation scripts

## Usage Examples

### Basic Usage

```bash
# Check current environment
print_key_env_vars

# Update paths for current repository
update_repo_path

# Switch to different repository and update paths
cd /path/to/other/repo
update_repo_path
```

### Example Output

**From FPGA Project Repository**:
```bash
$ update_repo_path
[+] Added to PYTHONPATH: /home/yoav.karmon/repo/fpga/tests
[+] Added to PYTHONPATH: /home/yoav.karmon/repo/fpga/tests/cocotb
[+] Added to PYTHONPATH: /home/yoav.karmon/repo/fpga/fpga_projects/phy10gbaser/sources/PY/PACKET_BUILDER
[+] Added to PYTHONPATH: /home/yoav.karmon/repo/fpga/fpga_projects/phy10gbaser/sources/PY
[+] Added to PATH: /home/yoav.karmon/repo/fpga/tools/tool_box
[i] sourcing /home/yoav.karmon/repo/fpga/tools/update_paths.sh
[v] REPO_TOP set to /home/yoav.karmon/repo/fpga

=== Key Environment Variables ===
PATH: /home/yoav.karmon/repo/fpga/tools/tool_box:/opt/vivado/bin:/home/yoav.karmon/repo/Fabrinetes/hdlforge/project_setup:/home/yoav.karmon/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PYTHONPATH: /home/yoav.karmon/repo/fpga/fpga_projects/phy10gbaser/sources/PY:/home/yoav.karmon/repo/fpga/fpga_projects/phy10gbaser/sources/PY/PACKET_BUILDER:/home/yoav.karmon/repo/fpga/tests/cocotb:/home/yoav.karmon/repo/fpga/tests:/home/yoav.karmon/repo/Fabrinetes/source/project_setup:
REPO_TOP: /home/yoav.karmon/repo/fpga
GIT_CONFIG_GLOBAL: /home/yoav.karmon/.gitconfig
GIT_AUTHOR_NAME: yoav.karmon
GIT_AUTHOR_EMAIL: yoav.karmon@363fpgadev-01.eh.local
GIT_COMMITTER_NAME: yoav.karmon
GIT_COMMITTER_EMAIL: yoav.karmon@363fpgadev-01.eh.local
EDITOR: nano
PAGER: less
BROWSER: /opt/firefox/firefox
XILINXD_LICENSE_FILE: /home/yoav.karmon/repos/phy_project/Xilinx.lic
==================================
```

**From Fabrinetes Repository**:
```bash
$ update_repo_path
[i]  Missing /home/yoav.karmon/repo/Fabrinetes/tools/update_paths.sh
[!]  Missing /home/yoav.karmon/repo/Fabrinetes/tools/tool_box/tool_box.sh
[v] REPO_TOP set to /home/yoav.karmon/repo/Fabrinetes

=== Key Environment Variables ===
PATH: /opt/vivado/bin:/home/yoav.karmon/repo/Fabrinetes/hdlforge/project_setup:/home/yoav.karmon/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PYTHONPATH: /home/yoav.karmon/repo/Fabrinetes/source/project_setup:
REPO_TOP: /home/yoav.karmon/repo/Fabrinetes
GIT_CONFIG_GLOBAL: /home/yoav.karmon/.gitconfig
GIT_AUTHOR_NAME: yoav.karmon
GIT_AUTHOR_EMAIL: yoav.karmon@363fpgadev-01.eh.local
GIT_COMMITTER_NAME: yoav.karmon
GIT_COMMITTER_EMAIL: yoav.karmon@363fpgadev-01.eh.local
EDITOR: nano
PAGER: less
BROWSER: /opt/firefox/firefox
XILINXD_LICENSE_FILE: /home/yoav.karmon/repos/phy_project/Xilinx.lic
==================================
```

## Integration with Tools

### HdlForge Integration

HdlForge uses `REPO_TOP` to:
- Verify it's running in a Git repository
- Set project-specific paths and configurations
- Ensure tools work with the correct project structure
- Provide clear error messages when repository context is wrong

**Example HdlForge Usage**:
```bash
# HdlForge automatically detects REPO_TOP
$ hdlforge Verilator --project phy10gbaser.hdlforge.toml --step sim --SimTargetName basic_test

# If REPO_TOP is not set, HdlForge provides clear error:
❌ REPO_TOP is not set. Please export REPO_TOP first.
```

### Custom Tool Integration

You can use the `REPO_TOP` environment variable in your own functions and tools:

**Example - Custom Tool Verification**:
```bash
#!/bin/bash
# Custom tool that requires specific repository

if [ -z "$REPO_TOP" ]; then
    echo "❌ REPO_TOP not set. Run 'update_repo_path' first."
    exit 1
fi

# Verify we're in the expected repository
expected_repo="my-project"
current_repo=$(basename "$REPO_TOP")

if [ "$current_repo" != "$expected_repo" ]; then
    echo "❌ Wrong repository. Expected: $expected_repo, Current: $current_repo"
    echo "   Please run: cd /path/to/$expected_repo && update_repo_path"
    exit 1
fi

echo "✅ Running in correct repository: $current_repo"
# Your tool logic here...
```

## Container Configuration Requirements

### Essential Mount Points

**For proper container setup, you must mount**:

1. **Repository Directory**:
   ```toml
   mounts = [
       "/DATA/repo:$HOME/repo",  # Mount your repo directory
       # ... other mounts
   ]
   ```

2. **Environment Files**:
   ```toml
   mounts = [
       "init_env.sh:/etc/profile.d/init_env.sh",    # Global environment setup
       "bashrc-root:$HOME/.bashrc",                # Repository-aware bashrc
       "entrypoint.sh:/usr/local/bin/entrypoint.sh" # Custom entrypoint
   ]
   ```

3. **SSH Keys** (for Git access):
   ```toml
   mounts = [
       "$HOME/.ssh:$HOME/.ssh",  # SSH keys for Git access
   ]
   ```

### Container Name Configuration

**Set unique container name** to avoid conflicts:
```toml
[config.container]
name = "my-project-run"  # Your unique container name
```

## Troubleshooting

### Common Issues

#### 1. REPO_TOP Not Set
**Problem**: `REPO_TOP` environment variable is not set.

**Solution**:
```bash
# Run update_repo_path to set REPO_TOP
update_repo_path

# Or manually set if not in a Git repository
export REPO_TOP="/path/to/your/repository"
```

#### 2. Wrong Repository Context
**Problem**: Tools expecting specific repository but running in different one.

**Solution**:
```bash
# Check current repository
echo "Current REPO_TOP: $REPO_TOP"

# Switch to correct repository
cd /path/to/correct/repository
update_repo_path
```

#### 3. Missing Repository-Specific Files
**Problem**: Repository-specific path files are missing.

**Solution**:
```bash
# Create missing files
mkdir -p tools/tool_box
touch tools/update_paths.sh
touch tools/tool_box/tool_box.sh

# Add content to files as needed
```

#### 4. Environment Variables Not Updated
**Problem**: Environment variables not reflecting current repository.

**Solution**:
```bash
# Force update of environment
update_repo_path

# Check current environment
print_key_env_vars
```

#### 5. Path Accumulation Issues
**Problem**: Paths accumulating from multiple repository switches.

**Solution**:
The `tools/update_paths.sh` file automatically handles this by:
- **Saving original paths** on first run
- **Restoring original paths** before adding repository-specific ones
- **Preventing duplicates** with pattern matching

```bash
# Check if path clearing is working
echo "Original PYTHONPATH: $__ORIGINAL_PYTHONPATH"
echo "Current PYTHONPATH: $PYTHONPATH"

# Force re-run to clear and re-add paths
update_repo_path
```

### Debugging Commands

```bash
# Check current environment
print_env_vars

# Check key variables only
print_key_env_vars

# Check current repository
echo "REPO_TOP: $REPO_TOP"
git rev-parse --show-toplevel

# Check if repository-specific files exist
ls -la tools/update_paths.sh
ls -la tools/tool_box/tool_box.sh

# Debug path clearing mechanism
echo "Original PYTHONPATH: $__ORIGINAL_PYTHONPATH"
echo "Original PATH: $__ORIGINAL_PATH"
echo "Current PYTHONPATH: $PYTHONPATH"
echo "Current PATH: $PATH"

# Check path clearing variables
echo "PYTHONPATH added flag: $__PYTHONPATH_ADDED"
echo "PATH added flag: $__PATH_ADDED"
```

## Best Practices

### 1. Repository Structure
- **Consistent Structure**: Use consistent directory structure across repositories
- **Standard Files**: Include `tools/update_paths.sh` and `tools/tool_box/tool_box.sh` in repositories
- **Documentation**: Document repository-specific environment requirements

### 2. Environment Management
- **Global First**: Set global environment variables in `init_env.sh`
- **Repository Specific**: Use repository-specific files for project-specific configurations
- **Path Clearing**: Implement path clearing in `tools/update_paths.sh` to prevent accumulation
- **Validation**: Always validate environment variables before running tools

### 3. Tool Integration
- **REPO_TOP Usage**: Use `REPO_TOP` in custom tools for repository context
- **Error Handling**: Provide clear error messages when repository context is wrong
- **Path Validation**: Validate paths before using them in tools

### 4. Development Workflow
- **Always Update**: Run `update_repo_path` when switching repositories
- **Check Environment**: Use `print_key_env_vars` to verify environment setup
- **Test Tools**: Test tools in different repository contexts

## Future Enhancements

### 1. Automatic Repository Detection
- **Auto-switching**: Automatically detect repository changes and update paths
- **Background Monitoring**: Monitor directory changes and update environment accordingly

### 2. Enhanced Path Management
- **Path Caching**: Cache repository-specific paths for faster switching
- **Path Validation**: Enhanced validation of repository-specific paths
- **Path Templates**: Pre-built path templates for common repository structures

### 3. Integration Improvements
- **IDE Integration**: Better integration with VS Code/Cursor for automatic path updates
- **Tool Integration**: Enhanced integration with more development tools
- **Configuration Management**: Centralized configuration management for path settings

This path management system provides a robust foundation for multi-repository development environments, ensuring that tools work correctly regardless of the current repository context while maintaining global container-wide configurations.
