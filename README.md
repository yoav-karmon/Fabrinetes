# Fabrinetes

> Inspired by Kubernetes. Built for FPGA Devs.

## TLDR - Quick Start

```bash
# 1. Clone the project repository that owns .devcontainer/
git clone https://github.com/yoav-karmon/Fabrinetes.git
cd Fabrinetes

# 2. Install Dev Containers CLI if needed
npm install -g @devcontainers/cli

# 3. Launch using the repo's devcontainer config
devcontainer up \
  --workspace-folder "$PWD" \
  --config "$PWD/.devcontainer/<config-folder>/devcontainer.json"

# 4. Attach VS Code/Cursor
# Command Palette: "Dev Containers: Attach to Running Container"
```

Fabrinetes is an open-source orchestration toolkit for modern FPGA development, 
combining containers, Verilator, Vivado, Cocotb, and reproducible environments 
all configured as code.

## Key Features

- **Open-source tools integration**: Docker, Verilator, Cocotb, Vivado, GTKWave
- **HdlForge single source of truth**: Unified TOML configuration across all tools
- **Git-aware environment**: Full PATH and PYTHONPATH control across repositories
- **Multi-repository support**: Seamless development across multiple projects
- **Dual operation modes**: CLI automation and VS Code/Cursor Dev Containers
- **Silent output support**: Non-interactive automation with clean logging

## Prerequisites

| Tool      | Version | Purpose                           |
|-----------|---------|-----------------------------------|
| Docker    | Latest  | Container runtime                 |
| Python    | 3.10+   | Fabrinetes CLI                    |
| VS Code/Cursor | Latest | Dev Containers extension workflow |
| Dev Containers CLI | Latest | Host-side container launch |

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yoav-karmon/Fabrinetes.git
cd Fabrinetes
```

2. Install the Dev Containers CLI if it is not already available:
```bash
npm install -g @devcontainers/cli
# or use: npx @devcontainers/cli --help
```

3. Launch from the repository that owns `.devcontainer/`:
```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

4. Access your container:

**VS Code/Cursor Dev Containers (Recommended)**
1. Open VS Code or Cursor in the repository root
2. Install the Dev Containers extension
3. Use Command Palette: "Dev Containers: Attach to Running Container"
4. Select your running container
5. Start developing with full IDE integration

For details, including `docker exec` access to already-running containers, see
[Dev Containers CLI Launch](doc/container-doc/devcontainer-cli.md).

## Path Management System

Fabrinetes includes a sophisticated **two-level path management system** that automatically configures environment variables based on context. For comprehensive documentation, see [Container Path Management](doc/container-doc/container-path-management.md).

### Quick Overview

**Global Container Level**: System-wide paths that work across all repositories (configured in `init_env.sh`)
**Repository Level**: Dynamic paths that change based on the current Git repository (managed by `update_repo_path()` function)

### Key Features

- **Automatic Detection**: Uses `git rev-parse --show-toplevel` to detect current Git repository
- **Dynamic REPO_TOP**: Sets `REPO_TOP` environment variable to repository root
- **Repository-Specific Paths**: Sources repository-specific path files (`tools/update_paths.sh`, `tools/tool_box/tool_box.sh`)
- **Path Clearing**: Automatically clears old repository paths before adding new ones
- **Environment Display**: Shows updated environment variables with `print_key_env_vars()`
- **Manual Switching**: User runs `update_repo_path` when switching between different repositories

### Usage

```bash
# Update paths for current repository
update_repo_path

# Display current environment
print_key_env_vars

# Switch repositories and update paths
cd /path/to/other/repo
update_repo_path
```

For detailed information about configuration, troubleshooting, and advanced usage, see the [Container Path Management](doc/container-doc/container-path-management.md) documentation.

## Important: Container Configuration Requirements

**For proper container setup, you must:**

1. **Mount your repository** in `config.toml`:
   ```toml
   mounts = [
       "$HOME/repo:$HOME/repo",  # Mount your repo directory
       # ... other mounts
   ]
   ```

2. **Set unique container name** to avoid conflicts:
   ```toml
   [config.container]
   name = "my-project-run"  # Your unique container name
   ```

3. **Configure global environment** in `init_env.sh`:
   ```bash
   # Global PATH setup for entire container
   export PATH="/opt/vivado/bin:$HOME/repo/Fabrinetes/source/project_setup:$HOME/.local/bin:$PATH"
   ```

4. **Set license file path** (if using Vivado):
   ```bash
   export XILINXD_LICENSE_FILE="$HOME/repos/your_project/Xilinx.lic"
   ```

**Why this matters:**
- Mount points determine what directories are accessible inside container
- Container name must be unique to avoid Docker conflicts
- Global PATH setup enables system-wide tools (Vivado, Fabrinetes, local binaries)
- License file path enables Vivado tools to function properly

## Dev Containers Launch

For project work, launch the container from the repository that owns the
`.devcontainer/` configuration. Project startup goes through the Dev Containers
extension or CLI.

### Basic Usage
```bash
# Start the project devcontainer
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json

# If the CLI is not installed globally
npx @devcontainers/cli up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

### What Dev Containers Launch Does
1. **Reads project configuration** from `<repo_top>/.devcontainer/.../devcontainer.json`
2. **Creates or starts the Docker container** from the configured image
3. **Applies mounts, environment, user, and runtime options** from the project
4. **Enables VS Code/Cursor attachment** through the Dev Containers extension
5. **Supports CLI execution** through `devcontainer exec`

Install the CLI with:

```bash
npm install -g @devcontainers/cli
```

For a fuller host setup and launch guide, see
[Dev Containers CLI Launch](doc/container-doc/devcontainer-cli.md).

## Tools & Integration

Fabrinetes orchestrates these open-source tools through a unified interface:

- **Docker**: Containerized development environments
- **Verilator**: SystemVerilog simulation engine
- **Cocotb**: Python-based testbench framework
- **Vivado**: Synthesis, implementation, and bitstream generation
- **GTKWave**: VCD waveform viewer
- **HdlForge**: Project-as-code engine with TOML configuration

All tools work together through HdlForge's single configuration file, eliminating 
tool-specific setup and ensuring reproducible builds.

## Usage Examples

### Getting Started (Recommended)
```bash
# Launch the repo-owned devcontainer
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

**Then attach VS Code/Cursor to the running container:**
1. Open VS Code/Cursor in repository root
2. Command Palette: "Dev Containers: Attach to Running Container"
3. Select your running container
4. Full IDE integration with debugging, IntelliSense, and extensions

### Dev Containers CLI Mode
```bash
# Start the configured devcontainer
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json

# Execute commands
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic "hdlforge test"
```

### Interactive VS Code/Cursor Mode
**Attach to Running Container (Recommended)**
1. Start the devcontainer with `devcontainer up`
2. Open VS Code/Cursor in the repository root
3. Install the Dev Containers extension
4. Command Palette: "Dev Containers: Attach to Running Container"
5. Select your running container
6. Enjoy full IDE integration with debugging, IntelliSense, and extensions

**Benefits of VS Code/Cursor Attachment:**
- Full IDE integration with debugging support
- IntelliSense and code completion
- Integrated terminal with proper environment
- Extension support (Python, Verilog, etc.)
- Git integration within container
- File explorer with container filesystem

### HdlForge Simulation
```bash
# Build simulation
hdlforge Verilator --project router.hdlforge.toml --step build --SimTargetName main

# Run simulation
hdlforge Verilator --project router.hdlforge.toml --step sim --SimTargetName main

# View waveforms
gtkwave dump.vcd
```

### HdlForge Vivado Flow
```bash
# Create project
hdlforge vivado --project router.hdlforge.toml --step new --clean

# Synthesis
hdlforge vivado --project router.hdlforge.toml --step syn --run-flow main

# Implementation
hdlforge vivado --project router.hdlforge.toml --step impl --run-flow main

# Generate bitstream
hdlforge vivado --project router.hdlforge.toml --step bit --run-flow main
```

## HdlForge Integration

HdlForge provides the single source of truth for FPGA projects:

- **TOML-based configuration**: All project settings in one file
- **Path management**: Automatic resolution across repositories
- **Git-aware environment**: REPO_TOP and PYTHONPATH variables
- **Tool abstraction**: Unified interface for Verilator and Vivado
- **Reproducible builds**: Consistent environment across machines

Example configuration:
```toml
[settings]
project_name = "router"
# Working root is the directory containing this project file (no project_path).

[verilator_settings]
[[verilator_settings.sim_targets]]
name = "main"
top_module = "top_module"
test_name = "test_case"

[vivado_settings]
top_module = "top_module"
part = "xc7a200tfbg484-1"
```

## Container Access

### Basic Commands
```bash
# Start the configured devcontainer
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json

# Execute in container
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'whoami; pwd'

# Check status
docker ps
```

### Docker Commit Reference
```bash
# Commit container changes
docker commit -m "Added new features" container_name image_name:tag

# Example
docker commit -m "Updated simulation" fabrinetes-local-run.run ykarmon/fabrinetes:v1.1
```

### Configuration
Configure project containers in the consuming repository's
`.devcontainer/<config-folder>/devcontainer.json`.

## Documentation

- [Documentation Index](doc/DOCUMENTATION_INDEX.md) - Complete index of all documentation files
- [Container Path Management](doc/container-doc/container-path-management.md) - Comprehensive guide to the two-level path management system
- [Testing Guide](doc/container-doc/testing_guide.md) - Devcontainer verification procedures
- [Repository Structure](doc/repository_explanation.md) - Project organization
- [HDLForge API Reference](doc/hdlforge-doc/HDLForge.md) - Single HDLForge source of truth for CLI, schema, and internals
- [Command Reference](command/README.md) - Complete command documentation

## Contributing

We welcome contributions from the FPGA and open-source communities.

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

## License

Fabrinetes is licensed under the [MIT License](LICENSE)

## Contact

Questions or feedback? Open a GitHub issue or email: 
[yoav@karmon.biz](mailto:yoav@karmon.biz)

---

Bring the power of Fabrinetes to your FPGAs one container at a time.
