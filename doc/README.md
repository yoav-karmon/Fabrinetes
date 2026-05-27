# Fabrinetes Repository

## Overview
Fabrinetes is a Docker container management system designed for FPGA development environments.
It provides automated container building, running, and configuration management with support for multiple development setups.

### PATH Management System
Fabrinetes includes a sophisticated PATH management system that automatically configures environment variables based on the current Git repository context:

- **Global PATH Management**: The container's bashrc contains an `update_repo_path()` function that detects Git repositories and manages PATH/PYTHONPATH
- **Per-Repository Switching**: When switching between different Git repositories, the system automatically cleans and reconfigures PATH and PYTHONPATH
- **Repository-Specific Configuration**: Each repository can define its own `tools/update_paths.sh` script for custom PATH configurations
- **Automatic Detection**: The system works seamlessly when `cd`ing into different repositories or sourcing bashrc
- **Clean Environment**: Each repository gets a fresh, isolated environment preventing conflicts between different projects

## Repository Structure

```
Fabrinetes/
├── containers/                           # Docker container definitions
│   ├── fabrinetes-dev/                  # Full FPGA development environment
│   │   ├── Dockerfile                   # Complete FPGA toolchain
│   │   ├── Fabrinetes_init_env.sh       # Environment initialization
│   │   └── config/
│   │       └── fabrinetes.config        # Container-specific config
│   ├── fabrinetes-dev-testing/          # Lightweight testing environment
│   │   ├── Dockerfile                   # Minimal testing setup
│   │   ├── Fabrinetes_init_env.sh       # Environment initialization
│   │   └── config/
│   │       └── fabrinetes.config        # Container-specific config
│   └── fabrinetes-fpga-full/           # Full FPGA development with GUI
│       ├── Fabrinetes_init_env.sh       # Environment initialization
│       └── config/
│           └── fabrinetes.config        # Container-specific config
├── source/                              # Container configuration files
│   ├── bashrc-root                      # Root user bash configuration
│   └── project_setup/                   # HDL development tools and scripts
├── _log/                               # Log files directory
├── fabrinetes                          # Main wrapper script
├── fabrinetes.config                   # Master container configuration (TOML)
├── tasks.py                            # Python invoke tasks
├── repository_explanation.md           # Repository documentation
└── README.md                           # Project documentation
```

## Key Components

### 1. Container Management (`fabrinetes` script)
- **Wrapper script** for invoke tasks
- **Interactive help** when run without arguments
- **Dynamic container listing** from config file
- **Logging** to `_log/` directory
- **Parameter handling** for build/run commands

### 2. Dev Containers Launch
- **Recommended launch path** for repositories that provide `.devcontainer/`
  configurations
- **VS Code/Cursor integration** through the Dev Containers extension
- **Host-side CLI support** with `devcontainer up` and `devcontainer exec`
- **Per-project configuration** owned by the consuming repository
- **See**: [Dev Containers CLI Launch](container-doc/devcontainer-cli.md)
  for installation and launch commands

### 3. Configuration System (`fabrinetes.config`)
- **TOML format** for easy editing
- **Master configuration** with all container definitions
- **Individual container configs** in `containers/*/config/` directories
- **Mount specifications** using `$HOME` variables
- **Environment variables** support
- **Self-contained containers** with local `Fabrinetes_init_env.sh` files

### 4. Task Automation (`tasks.py`)
- **Invoke-based** task runner
- **Docker and project automation** helpers
- **Path resolution** for mounts and configs
- **Unique container naming** with timestamps
- **X11/USB support** for GUI and hardware access

### 5. Container Definitions
- **fabrinetes-dev**: Full FPGA development with Vivado, tools
- **fabrinetes-dev-testing**: Lightweight testing environment
- **fabrinetes-fpga-full**: Complete FPGA development with GUI support
- **Self-contained**: Each container has its own config and init files
- **User mapping**: Host user matches container user
- **Volume mounts**: Repository and tool access

## Configuration Format

### Master Configuration (`fabrinetes.config`)
```toml
[container.fabrinetes-dev]
TAG = "latest"
mounts = ["$HOME/AMD/Vivado/2021.2:/opt/vivado", "$HOME/repo:/root/repos"]
init_env = "Fabrinetes_init_env.sh:/etc/profile.d/init_env.sh"

[container.fabrinetes-dev-testing]
TAG = "latest"
mounts = ["$HOME/repo:/root/repos", "/tmp:/tmp"]
init_env = "Fabrinetes_init_env.sh:/etc/profile.d/init_env.sh"

[container.fabrinetes-fpga-full]
TAG = "firefox_cocotb_verilator_working"
X11_path = "/mnt/wslg/.X11-unix"
mounts = [
    "vscode/.vscode-server/:$HOME/.vscode-server",
    "Fabrinetes_init_env.sh:/etc/profile.d/init_env.sh",
    "$HOME/.ssh:$HOME/.ssh",
    # ... additional mounts
]
```

### Individual Container Configs
Each container has its own configuration file in `containers/*/config/fabrinetes.config`:
- **Self-contained**: No external dependencies
- **Local init files**: `Fabrinetes_init_env.sh` in each container directory
- **Portable**: Uses relative paths and `$HOME` variables

## Usage Examples

### Basic Commands (fabrinetes)
```bash
# Show help and list containers
./fabrinetes

# Build specific container
./fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml

# List running containers
./fabrinetes list
```

### Dev Containers Launch
```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

Use VS Code/Cursor `Dev Containers: Attach to Running Container`, or run one
command inside the container:

```bash
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'whoami; pwd'
```

## PATH Management System

The repository includes a sophisticated PATH management system:

### Bashrc Integration
- **`update_repo_path()`** function in container bashrc
- **Git repository detection** for automatic configuration
- **Repository-specific scripts** via `tools/update_paths.sh`
- **Clean PATH/PYTHONPATH** on repository switches

### Environment Variables
- **REPO_TOP**: Current repository root
- **FABRINETES_ROOT**: Fabrinetes installation path
- **HDLFORGE_ROOT**: HDL development tools path

## Development Workflow

1. **Configure**: Edit `fabrinetes.config` for your setup
2. **Generate**: Create container images with `./fabrinetes gen-image`
3. **Launch**: Start project devcontainers with `devcontainer up`
4. **Develop**: Work in isolated, configured environments
5. **Switch**: Change repositories for different PATH configurations

## Features

- **Multi-container support**: Different environments for different needs
- **Self-contained containers**: Each container has its own config and init files
- **Automatic path resolution**: Environment variables and relative paths
- **Unique naming**: Timestamp-based container names prevent conflicts
- **Logging**: All operations logged to `_log/` directory
- **Portable configuration**: Uses `$HOME` variables for cross-system compatibility
- **Interactive help**: Built-in usage examples and container listing
- **Modular structure**: Individual container directories for easy maintenance

## Integration Points

- **Docker**: Container runtime and management
- **Invoke**: Python task automation
- **TOML**: Configuration file format
- **Git**: Repository detection for PATH management
- **X11**: GUI application support
- **USB**: Hardware device access

This repository provides a complete solution for managing FPGA development environments with Docker containers, offering flexibility, isolation, and ease of use.

---

## Document History

**Last Updated:** Commit `b1dfa6d6a9b4f65bba02265a196e9590650b6585` - Update documentation index to reflect new structure (2025-11-11)
