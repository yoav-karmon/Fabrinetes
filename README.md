
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

| Tool         | Purpose                                      |
|--------------|----------------------------------------------|
| `python`     | 3.10                                         |
| `docker   `  | Out-of-the-box simulation engine             |
| `VScode`     | Python-based testbench framework             |
| `MobaXterm`  | X11 GUI support from Windows hosts           |

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

### Benefits
✅ **Single source of truth** for all naming  
✅ **Type safety** with dataclass structure  
✅ **Consistent naming** across all modules  
✅ **Easy maintenance** - change naming logic in one place  
✅ **Automatic validation** of config file structure  

**Always use `get_container_info(config_file)` instead of manual TOML parsing!**

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
- **[Invoke Tasks](./invoke_tasks/README.md)** - Complete documentation of all Fabrinetes tasks, including architecture, usage, and development guidelines
- **[Test Framework](./invoke_tasks/test/README.md)** - Detailed documentation of the automated testing system, test scenarios, and framework architecture

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
