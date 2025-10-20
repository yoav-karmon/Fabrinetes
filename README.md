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

2. Use the setup script to build and run your first container:
```bash
./setup.sh -f containers/fabrinetes-dev-local/config.toml
```

The setup script will:
- Show available Docker images from Docker Hub
- Let you select an image (or use the latest)
- Build and run the container automatically
- Display progress and completion status

3. Access your container:

**VS Code/Cursor Remote Container (Recommended)**
1. Open VS Code or Cursor in the repository root
2. Install "Remote - Containers" extension
3. Use Command Palette: "Remote-Containers: Attach to Running Container"
4. Select your running fabrinetes container
5. Start developing with full IDE integration

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