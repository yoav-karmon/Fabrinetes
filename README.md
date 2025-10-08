
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
./fabrinetes Verilator --project router --step sim --SimTargetName main
````

* Generates VCD (`dump.vcd`)
* Uses Cocotb Python testbench
* GTKWave is preinstalled and usable inside container
* Define multiple **SimTargets** for different test scenarios (see [SimTargets Guide](docs/SimTargets_Guide.md))

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

[verilator_settings]
build_dir = "_verilator"
includes_paths = ["$REPO_TOP/rtl/includes"]

[verilator_settings.sim_targets.main]
top_module = "router_top"
python_file = "tests/test_router.py"
build_args = ["--trace", "--timing"]
```

This becomes your **single source of truth**:
→ All tools (Vivado, Verilator) pull configuration, source lists, and build logic from it.

**Learn more:**
- [SimTargets Guide](docs/SimTargets_Guide.md) - Comprehensive guide to simulation targets
- [SimTargets Quick Reference](docs/SimTargets_Quick_Reference.md) - Quick command reference

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
