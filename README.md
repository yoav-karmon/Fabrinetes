
---

````markdown
# Fabrinetes

> **Inspired by Kubernetes. Built for FPGA Devs.**

**Fabrinetes** is an open-source orchestration toolkit for **modern FPGA development**, combining containers, Verilator, Vivado, Cocotb, and reproducible environments — all configured as code.

We focus on:

- **Single source of truth** project declarations (via `HdlForge`)
- **Environment as Code** using Docker
- **GitOps-driven** reproducibility and workflows
- **CLI simplicity**: simulate, synthesize, and test with one command
- **Multi-container support** via TOML launcher files

---
## prerequisite:

| Tool         | Purpose                                      | Installation |
|--------------|----------------------------------------------|--------------|
| `python`     | 3.10                                         | System package manager |
| `docker`     | Out-of-the-box simulation engine             | [Docker Installation Guide](docs/docker-installation.md) |
| `VScode`     | Python-based testbench framework             | [VS Code Download](https://code.visualstudio.com/) |
| `MobaXterm`  | X11 GUI support from Windows hosts           | [MobaXterm Download](https://mobaxterm.mobatek.net/) |

**Note**: Docker installation requires user to be added to docker group for non-root access. See the [Docker Installation Guide](docs/docker-installation.md) for detailed setup instructions.

## Tools & Technologies

| Tool         | Purpose                                      |
|--------------|----------------------------------------------|
| `Docker`     | Shared container image with user separation  |
| `Verilator`  | Out-of-the-box simulation engine             |
| `Cocotb`     | Python-based testbench framework             |
| `Vivado`     | Synthesis, implementation, bitstream         |
| `GTKWave`    | VCD viewer (works inside container)          |
| `Argparse`   | Command-line argument parsing (replaced Invoke) |
| `HdlForge`   | Project-as-code engine (TOML config)         |
| `MobaXterm`  | X11 GUI support from Windows hosts           |

---
## How to:

## Key Features

✅ Designed for **VS Code** remote containers  
✅ Run **Verilator + Cocotb** simulation with one command  
✅ Out-of-the-box **GTKWave** GUI support  
✅ Full **Vivado flow** from structured project description  
✅ Supports **X11 GUIs** via native Linux or **MobaXterm**  
✅ Built-in tool: **`HdlForge`** — declarative, TOML-based FPGA project manager  
✅ **Mounts only what matters**: `.ssh`, Vivado, `.vscode-server/extensions`

---

## 🖥️ VS Code Integration

Fabrinetes is optimized for **Visual Studio Code Remote - Containers**:

- Mounts only `.vscode-server/extensions` → **fast startup**
- Keeps extension list **Git-tracked** and reproducible
- Avoids syncing volatile VSCode session/cache data

By doing this, the developer environment becomes a **Git versioned asset**, just like the code itself.

---

## 🧪 Simulation in One Line

```bash
hdlforge Verilator --project router.hdlforge.toml --step sim --SimTargetName main
````

* Generates VCD (`dump.vcd`)
* Uses Cocotb Python testbench
* GTKWave is preinstalled and usable inside container

---

## 🏗️ Vivado Flow

```bash
hdlforge vivado --project router.hdlforge.toml --step new --clean
hdlforge vivado --project router.hdlforge.toml --step syn --run-flow main
hdlforge vivado --project router.hdlforge.toml --step bit --run-flow main
```

* Generates and configures Vivado project
* Adds RTL files, constraints, generics, defines
* Runs synthesis, implementation, and bitstream generation

---

## 📦 Sample `container.toml` (Launcher Config)

```toml
[Containers.fabrinetes-vscode]
REPOSITORY = "fabrinetes-dev"
TAG        = "latest"

mounts = [
  "vscode/.vscode-server/:$HOME/.vscode-server",                  # <== critical: fast + stable VSCode
  "Fabrinetes_init_env.sh:/etc/profile.d/init_env.sh",           # <== critical: environment injection
  "$HOME/.ssh:$HOME/.ssh",                                       # <== critical: Git/SSH access
  "$HOME/repos:$HOME/repos",                                     # Shared codebase
  "$HOME/AMD/Vivado/2021.2:/opt/vivado"                          # Local Vivado tools
]
```

> ✅ Shared `Dockerfile`, built per-user using `UID/GID/USERNAME` as build args
> ✅ Environment initialization included
> ✅ TOML files enable **multiple container setups per repo**

---

## 🧩 HdlForge — Project as Code

Use `.hdlforge` TOML files to define the full project scope:

```toml
[settings]
project_name   = "router"
project_path   = "projects/router"
repo_path_env  = "REPO_TOP"

[vivado_settings]
top_module     = "top"
part           = "xc7a200tfbg484-1"
build_dir      = "vivado_build"
defines        = ["DEBUG"]
generics       = ["G_APP_ID=123"]
```

This becomes your **single source of truth**:
→ All tools (Vivado, Verilator) pull configuration, source lists, and build logic from it.

---

## 🏗️ ContainerInfo Dataclass - Centralized Naming System

Fabrinetes uses a **centralized naming system** via the `ContainerInfo` dataclass to ensure consistency across all modules:

### Usage Pattern
```python
from helper_functions.name_generator import get_container_info

# Get comprehensive container information
container_info = get_container_info(config_file)

# Access all naming information
image_name = container_info.image_docker          # "fabrinetes-dev-testing:latest"
base_image = container_info.base_image_docker    # "fabrinetes-skeleton:latest"
container_name = container_info.run_name         # "fabrinetes-dev-testing-latest.run"
tarball_path = container_info.tarball_path       # "containers/fabrinetes-dev-testing/fabrinetes-dev-testing-latest.tar.gz"
```

### ContainerInfo Properties
- **Image**: `image_docker`, `image_full`, `image_tarball`
- **Base Image**: `base_image_docker`, `base_image_full`, `base_image_tarball`
- **Container**: `run_name`, `container_name`
- **Paths**: `tarball_path`, `tarball_directory`
- **Config**: `mounts`, `x11_path`, `config_file`

### Path Validation and Dual Display
The `ContainerInfo` dataclass includes comprehensive path validation and dual path display:

#### Path Validation
```python
# Validate all paths before command execution
validation_errors = container_info.validate_paths()
if validation_errors:
    print("error: " + "; ".join(validation_errors))
    return
```

**Validated Paths:**
- Tarball paths (base and main images)
- Dockerfile paths
- Package list paths
- Config file paths
- Working directory paths

#### Dual Path Display
All commands now show **original TOML values** in comments and **resolved absolute paths** in executable commands:

**Example Output:**
```bash
# Comments show original TOML values:
#     -v cursor/.config:$HOME/.config                    # Mount from config.mounts array (relative to config file)

# Executable command shows resolved paths:
docker run -dit -v /home/ykarmon/repo/Fabrinetes/containers/fabrinetes-dev-testing/cursor/.config:/home/ykarmon/.config ...
```

### Benefits
✅ **Single source of truth** for all naming  
✅ **Type safety** with dataclass structure  
✅ **Consistent naming** across all modules  
✅ **Easy maintenance** - change naming logic in one place  
✅ **Automatic validation** of config file structure  
✅ **Path validation** - ensures all required files exist  
✅ **Dual path display** - original values in comments, resolved paths in commands  
✅ **Error handling** - clear "error: ..." messages when validation fails  

**Always use `get_container_info(config_file)` instead of manual TOML parsing!**

---

## 🚀 Fabrinetes Usage

### Basic Commands
```bash
# Show usage information only (no arguments)
./fabrinetes.py

# Show help and usage information
./fabrinetes.py --cmd help

# Build base image from Dockerfile
./fabrinetes.py --cmd build --config-file containers.toml

# Generate Docker run command
./fabrinetes.py --cmd run --config-file containers.toml

# Generate Docker exec command (interactive shell)
./fabrinetes.py --cmd exec --config-file containers.toml | bash

# Generate Docker exec command with specific command
./fabrinetes.py --cmd exec --config-file containers.toml --exec-cmd "hdlforge test" | bash

# Generate Docker commit command
./fabrinetes.py --cmd commit --config-file containers.toml

# Generate Docker restore command
./fabrinetes.py --config-file containers.toml --cmd restore --base-image

# Clean up Docker images
./fabrinetes.py --cmd clean-images --config-file containers.toml

# Show config file status
./fabrinetes.py --cmd status --config-file containers.toml
```

### Container Lifecycle Management

Fabrinetes provides a complete container lifecycle management system using only Fabrinetes commands:

#### Complete Workflow Example
```bash
# 1. Clean up existing images and tarballs
python3 fabrinetes.py --cmd clean-images --config-file containers/fabrinetes-dev-testing/config.toml | bash
rm -f containers/fabrinetes-dev-testing/*.tar.gz

# 2. Build new image from Dockerfile
python3 fabrinetes.py --cmd build --config-file containers/fabrinetes-dev-testing/config.toml | bash

# 3. Check status of all components
python3 fabrinetes.py --cmd status --config-file containers/fabrinetes-dev-testing/config.toml

# 4. Run container (when needed)
python3 fabrinetes.py --cmd run --config-file containers/fabrinetes-dev-testing/config.toml | bash

# 5. Execute commands in running container
python3 fabrinetes.py --cmd exec --config-file containers/fabrinetes-dev-testing/config.toml --exec-cmd "hdlforge test" | bash

# 6. Commit changes (when needed)
python3 fabrinetes.py --cmd commit --config-file containers/fabrinetes-dev-testing/config.toml | bash
```

#### Key Benefits
- ✅ **Single Command Interface**: All Docker operations through Fabrinetes API
- ✅ **Consistent Naming**: Automatic container/image naming from config
- ✅ **Status Monitoring**: Comprehensive status checking for all components
- ✅ **Clean Workflow**: Easy cleanup and rebuild process
- ✅ **Documentation**: All commands documented with examples
- ✅ **Persistent Containers**: Run command keeps containers running with `sleep infinity`
- ✅ **Proper Mount Resolution**: Automatic path resolution for relative and environment variable paths

### Unified Command Building System

Fabrinetes now uses a **unified command building system** that eliminates code duplication and ensures consistent behavior across all Docker commands.

#### Architecture Overview
The system is built around two main components:

1. **ContainerInfo Dataclass** (`helper_functions/config/name_generator.py` - 403 lines)
   - Single source of truth for all container configuration
   - Path validation and resolution
   - Centralized naming system

2. **CommandBuilder System** (`helper_functions/command_builder.py` - 415 lines)
   - Unified command building logic using `CmdPart` class hierarchy
   - Consistent error handling with `echo` statements for piped execution
   - Dual path display (original TOML values in comments, resolved paths in executable commands)

#### Key Features

**✅ Single Source of Truth**
- All command building logic centralized in `CommandBuilder` class
- No more duplicated code across command files
- Consistent behavior across all commands

**✅ Unified Error Handling**
- All commands use `echo 'error: ...'` for piped execution compatibility
- Consistent validation error display
- Commands show full structure even on validation failure

**✅ Dual Path Display**
- Comments show original TOML values (e.g., `cursor/.config:$HOME/.config`)
- Executable commands show resolved absolute paths
- Clear separation between configuration and execution

**✅ Optimized File Sizes**
- Command files reduced to 36-69 lines each (from 80-300+ lines)
- Main logic files kept under 500 lines
- Better maintainability and readability

#### CmdPart Class Hierarchy
The system uses a hierarchy of `CmdPart` classes for different command components:

- **`CmdPartFlag`**: Boolean flags like `--rm`, `--x11`
- **`CmdPartArg`**: Arguments with values like `-t image_name`
- **`CmdPartFile`**: File paths with validation like `-f Dockerfile`
- **`CmdPartMount`**: Volume mounts like `-v host:container`
- **`CmdPartMounts`**: Multiple volume mounts from config
- **`CmdPartEnv`**: Environment variables like `-e WORKDIR=path`
- **`CmdPartX11`**: X11 support with socket validation
- **`CmdPartName`**: Container/image names
- **`CmdPartHardcoded`**: Fixed values without resolution

#### Command File Structure
All command files now follow the same simple pattern:
```python
#!/usr/bin/env python3

from helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartArg

def build(args, container_info):
    """Generate Docker build command for image"""
    # Create command builder
    builder = CommandBuilder("Build (Image)")
    builder.set_base_command(["env", "docker", "build"])
    
    # Add parts
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory"))
    builder.add_part("image_name", CmdPartArg("-t", "image_docker"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    print(commented_str)
    print(execution_str)
```

#### Error Handling Example
```bash
# When validation fails, commands show:
# Docker Error Command:
# ==================================================
# Validation failed - showing command structure for reference
# ==================================================
# 
# Executable command:
echo 'error: Tarball path does not exist: fabrinetes-image:latest.tar.gz'
```

This approach ensures that scripts using `| bash` piping will see clear error messages instead of broken commands.

### Dynamic User Setup

Fabrinetes containers now support **dynamic user creation** at runtime instead of static build-time user setup. This makes containers reusable for any user without hardcoded paths.

#### How It Works
- **Entrypoint Script**: Creates user dynamically when container starts
- **Environment Variables**: Configure user details at runtime
- **Passwordless Sudo**: Automatically set up for the created user
- **Dynamic Paths**: All paths use `$HOME` instead of hardcoded user directories

#### Environment Variables
```bash
# Optional - defaults to current user if not specified
CONTAINER_USER=username    # Username to create
CONTAINER_UID=1000         # User ID
CONTAINER_GID=1000         # Group ID  
CONTAINER_HOME=/home/user  # Home directory
```

#### Example Usage
```bash
# Run with default user (current user)
docker run -it fabrinetes-testing-dynamic

# Run with custom user
docker run -it \
  -e CONTAINER_USER=developer \
  -e CONTAINER_UID=1001 \
  -e CONTAINER_GID=1001 \
  fabrinetes-testing-dynamic

# Test dynamic user setup
./containers/fabrinetes-dev-testing/test-dynamic-user.sh
```

#### Benefits
- ✅ **Reusable**: Same container works for any user
- ✅ **No Hardcoded Paths**: All paths use environment variables
- ✅ **Passwordless Sudo**: Automatically configured
- ✅ **Runtime Flexibility**: User creation happens at container start
- ✅ **Security**: Proper user isolation and permissions

### Status Command
The status command provides comprehensive information about all container components:

```bash
./fabrinetes.py --cmd status --config-file containers.toml
```

**Status Information Includes:**
- **Config Status**: File existence, size, modification date
- **Image Status**: Base image and main image existence, size, creation date
- **Tarball Status**: Base and main tarball existence, size, modification date (resolved relative to config file)
- **Container Status**: Container existence and running state
- **Directory Status**: Working directory permissions (where config file is located)
- **Clear Error Messages**: User-friendly Docker error messages with actionable solutions

**Example Output:**
```
Config Status:
  Config File (config): ✅ (exists)
    Size: 996.0B
    Modified: 2025-01-15 13:49:22

Image Status:
  Base Image (config.base_image): ❌ (Docker daemon not running - start Docker service)
  Main Image (config.image): ❌ (Docker daemon not running - start Docker service)

Tarball Status:
  Base Tarball (config.base_image.tarball_path): ✅ (exists)
    Size: 800MB
    Modified: 2025-01-14 10:30:25
  Main Tarball (config.image.tarball_path): ❌ (not found)

Container Status:
  Container (config.container.name): ❌ (Docker daemon not running - start Docker service)

Directory Status:
  Working Directory: ✅ (exists, writable)
```

**TOML Key Mapping:**
- `config` - The configuration file itself
- `config.base_image` - Base image name and tag
- `config.image` - Main image name and tag
- `config.base_image.tarball_path` - Base image tarball path (supports env vars, absolute/relative paths)
- `config.image.tarball_path` - Main image tarball path (supports env vars, absolute/relative paths)
- `config.container.name` - Container name

**Directory Logic:**
- **Working Directory**: Where the config file is located (project directory)
- **Tarball Paths**: Resolved relative to config file path (from config file settings)
- **Single Source of Truth**: All paths come from config file, no redundant directory concepts

**Tarball Path Configuration:**
The `tarball_path` configuration supports flexible path resolution:
- **Environment Variables**: `$HOME/tarballs/image.tar.gz` → `/home/user/tarballs/image.tar.gz`
- **Absolute Paths**: `/absolute/path/to/image.tar.gz` → `/absolute/path/to/image.tar.gz`
- **Relative Paths**: `relative/path/to/image.tar.gz` → resolved relative to config file location
- **Simple Filenames**: `image.tar.gz` → resolved relative to config file location

**Error Handling:**
The status command provides clear, actionable error messages for common Docker issues:
- `Docker daemon not running - start Docker service` - When Docker service is not running
- `Permission denied - add user to docker group` - When user lacks Docker permissions
- `Image not found - build or pull image first` - When Docker image doesn't exist
- `Container not found - run container first` - When Docker container doesn't exist
- `Network error - check Docker connectivity` - When Docker network issues occur

### Help Commands
- `./fabrinetes.py` (no arguments) → Shows only usage line
- `./fabrinetes.py --cmd help` → Shows full help with examples and descriptions
- `./fabrinetes.py -h` → Shows full help (standard argparse behavior)

---

## 🖼️ X11 GUI Support

Supports running GUI apps like Vivado or GTKWave through:

* Native Linux X11 forwarding
* Or **MobaXterm** on Windows with `DISPLAY` exported

No extra steps needed. Containers include all necessary packages.

---

## 🐳 Dockerfile Summary

The provided base image installs:

* Ubuntu 24.04
* Python + pip packages (`invoke`, `cocotb`, `scapy`, etc.)
* Verilator, GTKWave, network tools, CLI tools
* UID/GID configurable at build-time
* VSCode compatibility
* Lightweight + license-friendly (Vivado mounted, not bundled)

---

## 💡 Example Workflow

```bash
hdlforge vivado --project router.hdlforge.toml --step new --clean
hdlforge vivado --project router.hdlforge.toml --step syn --run-flow main
hdlforge Verilator --project router.hdlforge.toml --step sim --SimTargetName main
gtkwave dump.vcd
```

Everything is automated — nothing hidden in shell scripts.

---

## 📎 License

Fabrinetes is licensed under the [MIT License](./LICENSE)

---

## 📚 Documentation

This repository contains comprehensive documentation:

### Core Documentation
- **[Testing Guide](./testing_guide.md)** - Comprehensive guide for testing Fabrinetes functionality, including cleanup, build, run, exec, shell, and automated testing procedures
- **[Repository Explanation](./repository_explanation.md)** - Detailed explanation of the repository structure, container organization, and configuration management
- **[HDLForge v2.0 Migration Guide](./HDLForge_v2_Migration_Guide.md)** - Complete migration guide for HDLForge v2.0, including command structure changes and examples

### Technical Documentation
- **[Command Tasks](./command/README.md)** - Complete documentation of all Fabrinetes tasks, including architecture, usage, and development guidelines
- **[Test Framework](./command/test/README.md)** - Detailed documentation of the automated testing system, test scenarios, and framework architecture

### Development Guidelines
- **ContainerInfo Dataclass** - Centralized naming system using `ContainerInfo` dataclass for all container, image, and tarball naming. Always use `get_container_info(config_file)` to get consistent naming across all modules.

---

## 📘 HDLForge Reference Guide

> **Python-based build system that wraps Verilator and Vivado tools**

HDLForge is a comprehensive build system that provides a unified interface for FPGA development workflows, combining Verilator simulation and Vivado synthesis/implementation in a single, consistent command-line tool.

### Quick Reference (TLDR)

```bash
# Working directory: <project_directory_path>
# Project file: <project_name>.hdlforge.toml

# Verilator Commands
hdlforge Verilator --project <project_file.hdlforge.toml> --step <build/sim> --SimTargetName <target_name> [--clean] [--extra-env DEBUG=1] [--flags <flags>]

# Vivado Commands  
hdlforge vivado --project <project_file.hdlforge.toml> --step <new/syn/impl/bit/list_runs/reset_run> [--run-flow <flow_name>] [--clean]

# Project Management
hdlforge projects
hdlforge help
```

> **⚠️ Important**: All commands now require the `--project <project_file.hdlforge.toml>` parameter. The old format `hdlforge <project_file> <command>` is no longer supported.

### Recent Changes (v2.0)

**Major Update**: HDLForge has been updated to use `argparse` instead of `invoke` for better command-line interface:

- ✅ **Simplified CLI**: Cleaner command structure with explicit `--project` parameter
- ✅ **Better Error Messages**: Clear usage instructions and error reporting
- ✅ **Consistent Interface**: All commands follow the same pattern
- ✅ **Removed Dependencies**: No longer requires `invoke` package
- ✅ **Backward Compatibility**: Old format no longer supported for cleaner interface

**Migration Guide**:
```bash
# Old format (no longer supported):
hdlforge <project_file> <command> [options]

# New format (required):
hdlforge <command> --project <project_file> [options]
```

### Command Reference

#### HDLForge Main Command
```bash
hdlforge <main_tool> --project <project_file.hdlforge.toml> <--command_flags_of_tool>
```

**Required Pattern**: All commands must include `--project <project_file.hdlforge.toml>` parameter and be run from the project directory.

#### Verilator Commands

##### Build (Compile SystemVerilog to C++)
```bash
cd <project_directory> && hdlforge Verilator --project <project_file.hdlforge.toml> --step build --SimTargetName <target_name> [--clean] [--extra-env DEBUG=1] [--flags <flags>]
```

##### Simulation (Run simulation - requires successful build)
```bash
cd <project_directory> && hdlforge Verilator --project <project_file.hdlforge.toml> --step sim --SimTargetName <target_name>
```

#### Vivado Commands

##### Create New Project
```bash
cd <project_directory> && hdlforge vivado --project <project_file.hdlforge.toml> --step new --clean
```

##### Synthesis
```bash
cd <project_directory> && hdlforge vivado --project <project_file.hdlforge.toml> --step syn --run-flow <flow_name>
```

##### Implementation
```bash
cd <project_directory> && hdlforge vivado --project <project_file.hdlforge.toml> --step impl --run-flow <flow_name>
```

##### Generate Bitstream
```bash
cd <project_directory> && hdlforge vivado --project <project_file.hdlforge.toml> --step bit --run-flow <flow_name>
```

##### List Runs
```bash
cd <project_directory> && hdlforge vivado --project <project_file.hdlforge.toml> --step list_runs
```

##### Reset Run
```bash
cd <project_directory> && hdlforge vivado --project <project_file.hdlforge.toml> --step reset_run
```

#### Help Commands
```bash
hdlforge help
hdlforge Verilator --help
hdlforge vivado --help
hdlforge projects --help
```

### Project Configuration

#### Project Structure
- **Project Directory**: Top-level folder containing the `.hdlforge.toml` file
- **Project File**: `<project_name>.hdlforge.toml` - Configuration file in project directory
- **Execution Context**: All commands must be run from the project directory

#### Configuration File Sections

##### Basic Settings
```toml
[settings]
project_name = "unique_project_identifier"
project_path = "$REPO_TOP/projects/<project_name>"
```

##### Verilator Settings
```toml
[verilator_settings]
build_dir = "_verilator"  # Default build directory
includes_paths = ["path/to/includes"]

[[verilator_settings.sim_targets]]
name = "main"
top_module = "top_module_name"
test_name = "test_case_name"
python_file = "test_script.py"
build_args = ["--trace"]
defines = ["DEBUG"]
parameters = ["G_WIDTH=32"]
PYTHONPATH = ["additional/python/paths"]
```

##### Vivado Settings
```toml
[vivado_settings]
build_dir = "_vivado"  # Default build directory
project_name = "vivado_project_name"
top_module = "top_module_name"
part = "xc7a200tfbg484-1"

[[vivado_settings.runs_flow]]
name = "main"
synth = "synth_1"
impl = ["impl_1"]
paramaters = ["-flatten_hierarchy none"]
defines = ["DEBUG"]
```

##### Source Files
```toml
[[sources.files]]
file = ["path/to/source1.sv", "path/to/source2.sv"]
verilator = true
vivado = true
relative_to_project_path = true
vivado_fileset = "sources_1"
```

### File Organization

#### Source File Categories
- **sv_common**: Packages, interfaces, shared modules
- **sv_functional**: Protocol implementations, data processing
- **sv_interface**: Configuration, control, communication
- **sv_top**: System integration and hierarchy
- **sv_platform**: Hardware abstraction
- **vhdl_files**: Platform-specific components, IP cores

#### Dependency Management
- **Packages**: Core SystemVerilog packages for constants, types, functions
- **Interfaces**: Interface definitions (must be included first)
- **Common Modules**: FIFOs, dual-port RAM, watchdog, exception handler
- **Build Order**: Controlled by TOML file sections and file dependencies

### Output Organization

#### Verilator Outputs
- **Build Directory**: `<verilator_settings.build_dir>` (default: `_verilator`)
- **Test-Specific Folders**: Each `SimTargetName` gets its own subdirectory
- **VCD Files**: Located at `build_dir/SimTargetName/dump.vcd`
- **Log Files**: All HDLForge output logged to `/opt/project_setup/logs/hdlforge_YYYYMMDD_pidXXXXX.log`

#### Directory Structure Example
```
project_dir/
├── _verilator/
│   ├── main/           # SimTargetName=main
│   │   └── dump.vcd
│   └── test_variant/   # SimTargetName=test_variant
│       └── dump.vcd
└── _vivado/            # Vivado build directory
```

### File Locations & Development Workflow

#### HDLForge Installation
- **Installed Files**: `/opt/project_setup/`
- **Repository Files**: `/home/ykarmon/repo/Fabrinetes/source/project_setup/`
- **Main Script**: `tasks.py` → installed to system PATH as `hdlforge`

#### Development Workflow
1. **Edit**: Files in repository `/path/to/repo/Fabrinetes/source/project_setup/`
2. **Test**: Changes locally in repository directory
3. **Commit**: Changes to Git repository
4. **Reinstall**: HDLForge to update system-installed files
5. **Verify**: Changes work in installed version

> ⚠️ **Warning**: Never edit files in `/opt/project_setup/` or `/usr/local/bin/` directly

#### Setup HDLForge (if not in PATH)
```bash
# Option 1: Add to PATH
export PATH=$PATH:<hdlforge_directory>

# Option 2: Create symlink
sudo ln -s <hdlforge_script> /usr/local/bin/hdlforge

# Option 3: Add alias
alias hdlforge='<hdlforge_script>'

# Option 4: Copy to system
cp <hdlforge_script> /usr/local/bin/hdlforge
```

### Error Handling & Best Practices

#### Common Error: Missing Project Parameter
**Error**: `'<tool>' did not receive required positional arguments: 'project'`

**Solution**: Add `--project <project_file.hdlforge.toml>` to your command
```bash
# Correct usage
hdlforge Verilator --project <project_name>.hdlforge.toml --step build --SimTargetName main

# List available projects
hdlforge projects
```

#### Best Practices
1. **Always run commands from the project directory**
2. **Always specify project explicitly**: Use `--project <project_file.hdlforge.toml>` parameter (required)
3. **Use specific simulation targets**: Always specify `--SimTargetName` parameter
4. **Verify builds**: Check for 0 errors and 0 warnings
5. **Manage dependencies**: Ensure proper file order in TOML configuration
6. **Clean builds**: Use `--clean` flag when encountering build issues
7. **Global access**: HDLForge is available in PATH and can be called from anywhere

#### Troubleshooting Configuration Issues
- **Missing files**: Reorder compilation order with dependencies - do NOT add include statements
- **Include statements**: Only include interface declarations (`include "interfaces.sv"`), do NOT specify path
- **Dependencies**: Files with dependencies must be included in order in project configuration file

---

## 🤝 Contributing

We welcome contributions from the FPGA and open-source communities.

1. Fork the repo
2. Create a feature branch
3. Submit a pull request with a clear description

---

## 📬 Contact

Questions or feedback?
Open a GitHub issue or email: **[yoav@karmon.biz](mailto:yoav@karmon.biz)**

---

**Bring the power of Fabrinetes to your FPGAs — one container at a time.**
