
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
| `Invoke`     | Task runner used internally in CLI           |
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
./fabrinetes Verilator --project router --step sim
````

* Generates VCD (`dump.vcd`)
* Uses Cocotb Python testbench
* GTKWave is preinstalled and usable inside container

---

## 🏗️ Vivado Flow

```bash
./fabrinetes vivado --project router --new --bit
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
./fabrinetes vivado --project router --new --bit
./fabrinetes Verilator --project router --step sim
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

### Technical Documentation
- **[Invoke Tasks](./invoke_tasks/README.md)** - Complete documentation of all Fabrinetes tasks, including architecture, usage, and development guidelines
- **[Test Framework](./invoke_tasks/test/README.md)** - Detailed documentation of the automated testing system, test scenarios, and framework architecture

### Development Guidelines
- **ContainerInfo Dataclass** - Centralized naming system using `ContainerInfo` dataclass for all container, image, and tarball naming. Always use `get_container_info(config_file)` to get consistent naming across all modules.

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
