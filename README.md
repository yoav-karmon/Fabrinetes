# Fabrinetes

> Inspired by Kubernetes. Built for FPGA Devs.

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

2. Build your first container:
```bash
./fabrinetes.py --cmd build --config-file containers/fabrinetes-dev-local/config.toml | bash
```

3. Run a simulation:
```bash
hdlforge Verilator --project router.hdlforge.toml --step sim --SimTargetName main
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

### CLI Mode (Automation)
```bash
# Build container
./fabrinetes.py --cmd build --config-file containers.toml | bash

# Run container
./fabrinetes.py --cmd run --config-file containers.toml | bash

# Execute commands
./fabrinetes.py --cmd exec --config-file containers.toml --exec-cmd "hdlforge test" | bash
```

### Interactive VS Code Mode
1. Open VS Code in the repository root
2. Install "Remote - Containers" extension
3. Use Command Palette: "Remote-Containers: Reopen in Container"
4. Select your fabrinetes container configuration

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

- [Testing Guide](doc/testing_guide.md) - Comprehensive testing procedures
- [Repository Structure](doc/repository_explanation.md) - Project organization
- [HDLForge Migration](doc/HDLForge_v2_Migration_Guide.md) - v2.0 migration guide
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