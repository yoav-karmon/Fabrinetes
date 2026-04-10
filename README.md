# Fabrinetes

> Inspired by Kubernetes. Built for FPGA Devs.

## TLDR - Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/yoav-karmon/Fabrinetes.git
cd Fabrinetes

# 2. Create your container config
mkdir -p containers/my-project
cp containers/fabrinetes-dev-local/config.toml containers/my-project/
cp containers/fabrinetes-dev-local/init_env.sh containers/my-project/
# Edit init_env.sh and config.toml for your setup

# 3. Run container
./setup.sh -f containers/my-project/config.toml

# 4. Attach VS Code/Cursor
# Install "Remote - Containers" extension
# Command Palette: "Remote-Containers: Attach to Running Container"
```

Fabrinetes is an open-source orchestration toolkit for modern FPGA development, 
combining containers, Verilator, Vivado, Cocotb, and reproducible environments 
all configured as code.

## Key Features

- **Open-source tools integration**: Docker, Verilator, Cocotb, Vivado, GTKWave
- **HdlForge single source of truth**: Unified TOML configuration across all tools
- **Git-aware environment**: Full PATH and PYTHONPATH control across repositories
- **Multi-repository support**: Seamless development across multiple projects
- **Dual operation modes**: CLI automation and VS Code remote containers
- **Silent output support**: Non-interactive automation with clean logging

## Prerequisites

| Tool      | Version | Purpose                           |
|-----------|---------|-----------------------------------|
| Docker    | Latest  | Container runtime                 |
| Python    | 3.10+   | Fabrinetes CLI                    |
| VS Code   | Latest  | Remote container development      |

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yoav-karmon/Fabrinetes.git
cd Fabrinetes
```

2. Create your own container configuration:
```bash
# Create your container directory
mkdir -p containers/my-project

# Copy template files
cp containers/fabrinetes-dev-local/config.toml containers/my-project/
cp containers/fabrinetes-dev-local/init_env.sh containers/my-project/
```

3. Configure your container setup in `containers/my-project/config.toml`:
```toml
[config.image]
name = "ykarmon/fabrinetes"
tag = "latest"

[config.container]
name = "my-project-run"  # Set your own container run name

[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh",                    # SSH keys for Git access
    "$HOME/repo:$HOME/repo",                    # Mount your repo directory (recommended: put all repos under repo folder)
    "$HOME/.Xauthority:$HOME/.Xauthority:ro",   # X11 authentication (read-only)
    "init_env.sh:/etc/profile.d/init_env.sh"    # Global environment setup
]
```

4. Use the setup script with your configuration:
```bash
./setup.sh -f containers/my-project/config.toml
```

The setup script will:
- Show available Docker images from Docker Hub
- Let you select an image (or use the latest)
- Build and run the container automatically
- Display progress and completion status

5. Access your container:

**VS Code/Cursor Remote Container (Recommended)**
1. Open VS Code or Cursor in the repository root
2. Install "Remote - Containers" extension
3. Use Command Palette: "Remote-Containers: Attach to Running Container"
4. Select your running fabrinetes container
5. Start developing with full IDE integration

## Path Management System

Fabrinetes includes a sophisticated **two-level path management system** that automatically configures environment variables based on context. For comprehensive documentation, see [Container Path Management](doc/container-path-management.md).

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

For detailed information about configuration, troubleshooting, and advanced usage, see the [Container Path Management](doc/container-path-management.md) documentation.

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

## Setup Script

The `setup.sh` script is the recommended way to get started with Fabrinetes:

### Basic Usage
```bash
# Interactive setup (shows available images)
./setup.sh -f containers/fabrinetes-dev-local/config.toml

# Specify image directly
./setup.sh -f containers/fabrinetes-dev-local/config.toml -i ykarmon/fabrinetes:latest
```

### What the Setup Script Does
1. **Fetches available images** from Docker Hub
2. **Displays numbered list** of available images with sizes and dates
3. **Interactive selection** or accepts pre-specified image
4. **Runs fabrinetes automatically** to build and start container
5. **Shows progress** with clear success/error messages

### Setup Script Options
- `-f <config_file>`: Required config file path
- `-i <image_id>`: Optional image ID (skips interactive selection)
- `-h, --help`: Show usage information

### Example Output
```
Docker Image Setup

Available images:
  1. ykarmon/fabrinetes:latest - 2025-10-20T10:53:22.123456Z - 1400MB
  2. ykarmon/fabrinetes:v1.0 - 2025-10-19T15:30:45.789012Z - 1350MB

Select image number or 'q' to quit: 1
Selected image: ykarmon/fabrinetes:latest

Fabrinetes Container Runner
Config file: containers/fabrinetes-dev-local/config.toml
Running: ./fabrinetes.py --config-file containers/fabrinetes-dev-local/config.toml --cmd run | bash

==========================================
START OF FABRINETES OUTPUT
==========================================
[SUCCESS] Container started successfully
==========================================
END OF FABRINETES OUTPUT
==========================================
[SUCCESS] Fabrinetes command completed!
[SUCCESS] Done!
```

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
# Use setup script for easy container setup
./setup.sh -f containers/fabrinetes-dev-local/config.toml
```

**Then attach VS Code/Cursor to the running container:**
1. Open VS Code/Cursor in repository root
2. Command Palette: "Remote-Containers: Attach to Running Container"
3. Select your fabrinetes container
4. Full IDE integration with debugging, IntelliSense, and extensions

### Manual CLI Mode (Advanced)
```bash
# Build container
./fabrinetes.py --cmd build --config-file containers.toml | bash

# Run container
./fabrinetes.py --cmd run --config-file containers.toml | bash

# Execute commands
./fabrinetes.py --cmd exec --config-file containers.toml --exec-cmd "hdlforge test" | bash
```

### Interactive VS Code/Cursor Mode
**Attach to Running Container (Recommended)**
1. Run setup script: `./setup.sh -f containers/fabrinetes-dev-local/config.toml`
2. Open VS Code/Cursor in the repository root
3. Install "Remote - Containers" extension
4. Command Palette: "Remote-Containers: Attach to Running Container"
5. Select your running fabrinetes container
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
project_path = "$REPO_TOP/projects/router"

[verilator_settings]
[[verilator_settings.sim_targets]]
name = "main"
top_module = "top_module"
test_name = "test_case"

[vivado_settings]
top_module = "top_module"
part = "xc7a200tfbg484-1"
```

## Container Management

### Basic Commands
```bash
# Show help
./fabrinetes.py --cmd help

# Build image
./fabrinetes.py --cmd build --config-file containers.toml

# Run container
./fabrinetes.py --cmd run --config-file containers.toml

# Execute in container
./fabrinetes.py --cmd exec --config-file containers.toml

# Check status
./fabrinetes.py --cmd status --config-file containers.toml
```

### Docker Commit Reference
```bash
# Commit container changes
docker commit -m "Added new features" container_name image_name:tag

# Example
docker commit -m "Updated simulation" fabrinetes-local-run.run ykarmon/fabrinetes:v1.1
```

### Configuration
Configure containers via `config.toml`:
```toml
[config.image]
name = "ykarmon/fabrinetes"
tag = "latest"

[config.container]
name = "fabrinetes-local-run"

[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh",
    "$HOME/repo:$HOME/repo",
    "$HOME/.Xauthority:$HOME/.Xauthority:ro"
]
```

## Documentation

- [Documentation Index](doc/DOCUMENTATION_INDEX.md) - Complete index of all documentation files
- [Container Path Management](doc/container-path-management.md) - Comprehensive guide to the two-level path management system
- [Testing Guide](doc/testing_guide.md) - Comprehensive testing procedures
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