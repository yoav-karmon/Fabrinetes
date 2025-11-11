# HDLForge Build System

## TLDR

**What:** Unified FPGA build system - Verilator simulation + Vivado synthesis via JSON config

**Quick Start:**
```bash
cd <project_directory>
hdlforge Verilator --step build --SimTargetName <target>
hdlforge Verilator --step sim --SimTargetName <target>
hdlforge vivado --step syn --run-flow <flow>
hdlforge vivado --step bit --run-flow <flow>
```

**Core Concept:** One JSON file + automatic environment setup = reproducible builds

> **📘 Details:** See sections below for complete usage and configuration

---

## 1. Overview

### 1.1 What is HDLForge?

HDLForge is a unified build system for FPGA development that:
- **Wraps multiple tools:** Verilator (simulation) and Vivado (synthesis/implementation)
- **Single configuration:** One JSON file defines entire project
- **Project-as-code:** All settings, sources, and build parameters in version control
- **Environment management:** Automatic PATH/PYTHONPATH setup via Git repository detection

### 1.2 Why HDLForge?

**Problem:** FPGA development requires managing multiple tools with different interfaces, complex environment setup, and scattered configuration files.

**Solution:** HDLForge provides:
- Single JSON configuration for entire project
- Automatic environment detection and setup
- Unified command-line interface
- Reproducible builds across teams and machines

### 1.3 Supported Tools

| Tool            | Purpose             | Steps                   | Output                  |
|-----------------|---------------------|-------------------------|-------------------------|
| **Verilator**   | Simulation          | build → sim             | Waveforms, test results |
| **Vivado**      | FPGA Implementation | new → syn → impl → bit  | Bitstream               |

---

## 2. Architecture

> **📘 Complete Details:** [HDLForge-Architecture.md](HDLForge-Architecture.md)

### 2.1 Two-Stage Execution Model

HDLForge separates environment management from build logic:

```
User Command
    ↓
┌─────────────────────────────────────┐
│ 1. Bash Wrapper (hdlforge)          │
│    • Parse arguments & discover      │
│      project file                    │
│    • Navigate to project directory   │
│    • Setup environment (via          │
│      update_repo_path function)      │
│    • Launch Python core              │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 2. Python Core (tasks.py)           │
│    • Load JSON configuration         │
│    • Collect & resolve file paths    │
│    • Execute Verilator or Vivado     │
└──────────────┬──────────────────────┘
               ↓
          Tool Output
    (artifacts, logs, reports)
```

**Why this design?**
- **Bash:** Handles OS-level concerns (environment, directories)
- **Python:** Handles build logic (configuration, tool orchestration)
- **Clean separation:** Enables easy extension and debugging

### 2.2 Environment & Logging

**Automatic Environment Setup:**

HDLForge automatically configures your environment via the `update_repo_path` function:
- `REPO_TOP` - Git repository root (auto-detected)
- `PATH` / `PYTHONPATH` - Updated with repository tools and modules

**Logging:**
- **Location:** `hdlforge/project_setup/logs/hdlforge_YYYYMMDD_pid<PID>.log`
- All output captured and displayed simultaneously

---

## 3. Project Configuration

HDLForge uses a single JSON file (`.hdlforge.json`) to define your entire project.

### 3.1 File Structure

**Basic sections:**
- `settings` - Project name and path
- `verilator_settings` - Verilator/Cocotb configuration
- `vivado_settings` - Vivado synthesis/implementation configuration  
- `sources` - Source files with tool filters

### 3.2 Key Concepts

**Path Expansion:**
- `$REPO_TOP` expands to Git repository root (auto-detected)
- `relative_to_project_path` controls path resolution

**Tool Filtering:**
- Mark files with `"verilator": true` or `"vivado": true`
- Share files across tools or keep tool-specific

### 3.3 Configuration Examples

> **📘 Complete configuration details:**
> - Verilator: [HDLForge-Verilator.md](HDLForge-Verilator.md#3-configuration-structure)
> - Vivado: [HDLForge-Vivado.md](HDLForge-Vivado.md#3-configuration-structure)
> - Architecture: [HDLForge-Architecture.md](HDLForge-Architecture.md#33-project-loader)

---

## 4. Basic Usage

### 4.1 Project File Discovery

**Auto-Detection (Recommended):**
```bash
cd <project_directory>           # Must cd to directory containing *.hdlforge.json
hdlforge Verilator --step build --SimTargetName main
```
- **Requires:** You must `cd` to project directory first
- HDLForge finds project file in current directory
- Requires exactly one `*.hdlforge.json` or `*.hdlforge.toml` file
- Prefers JSON over TOML if both exist

**Explicit Specification (No cd Required):**
```bash
# Absolute path - works from ANY directory
hdlforge Verilator --project /path/to/project.hdlforge.json --step build --SimTargetName main

# Relative path - resolved from current directory
hdlforge Verilator --project ../other/project.hdlforge.json --step build --SimTargetName main
```
- **No manual `cd` needed:** HDLForge wrapper changes to project directory automatically
- After directory change, runs `update_repo_path` to set environment
- All operations execute from project directory

**Working Directory Summary:**

| Mode                                | User cd? | Auto cd? | Final Directory   |
|-------------------------------------|----------|----------|-------------------|
| **Auto-detection** (no `--project`) | ✓ Yes    | No       | Current directory |
| **Explicit** (`--project` flag)     | No       | ✓ Yes    | Project directory |

**Error Handling:**
- **No files found:** Error with suggestion to create project file
- **Multiple files found:** Error requiring explicit `--project` flag
- **File not found:** Lists available project files in directory

### 4.2 Command Structure

**General Format:**
```bash
hdlforge <command> [--project <file>] [options]
```

**Available Commands:**
- `Verilator` - Simulation and verification builds
- `vivado` - Synthesis, implementation, and bitstream generation
- `projects` - List available projects in current directory
- `help` - Show help information

### 4.3 Environment

**Automatic:** HDLForge configures `REPO_TOP`, `PATH`, and `PYTHONPATH` automatically.

> **📘 How it works:** [HDLForge-Architecture.md](HDLForge-Architecture.md#41-environment-management)

---

## 5. Verilator - Simulation

> **📘 Detailed Documentation:** [HDLForge-Verilator.md](HDLForge-Verilator.md)

### 5.1 Overview

**Purpose:** Fast, cycle-accurate simulation with Python testbenches

**Key Features:**
- Python-based testbenches (Cocotb framework)
- VCD waveform generation (GTKWave compatible)
- JUnit XML test results

### 5.2 Commands

```bash
# Build: Compile SystemVerilog with Verilator
hdlforge Verilator --step build --SimTargetName <target>

# Simulate: Run Python testbench with Cocotb
hdlforge Verilator --step sim --SimTargetName <target>
```

**Key Options:**
- `--clean` - Force rebuild
- `--flags "<flags>"` - Additional Verilator flags
- `--extra-env KEY=value` - Environment variables

**Output:**
- `dump.vcd` - Waveform file (view with GTKWave)
- `results.xml` - Test results (JUnit format)

> **📘 Complete guide:** [HDLForge-Verilator.md](HDLForge-Verilator.md)
> - Configuration structure
> - Python testbench examples
> - Error handling and debugging

---

## 6. Vivado - FPGA Implementation

> **📘 Detailed Documentation:** [HDLForge-Vivado.md](HDLForge-Vivado.md)

### 6.1 Overview

**Purpose:** FPGA synthesis, implementation, and bitstream generation

**Key Features:**
- Automated project creation
- Multiple run flow strategies
- TCL-based management
- Batch mode execution

### 6.2 Commands

```bash
# Create Project
hdlforge vivado --step new [--clean]

# Synthesis
hdlforge vivado --step syn --run-flow <flow_name>

# Implementation
hdlforge vivado --step impl --run-flow <flow_name>

# Bitstream
hdlforge vivado --step bit --run-flow <flow_name>
```

**Output:**
- `.xpr` - Vivado project file
- `.dcp` - Design checkpoints (netlist, placed/routed)
- `.bit` - FPGA bitstream file
- `runme.log` - Execution logs

> **📘 Complete guide:** [HDLForge-Vivado.md](HDLForge-Vivado.md)
> - Configuration structure
> - Run flows and strategies
> - Timing analysis and debugging

---

## 7. Summary

HDLForge provides a clean separation between environment management (Bash) and build logic (Python), enabling:
- **Reproducible builds** through JSON configuration
- **Automatic environment setup** via `update_repo_path`
- **Flexible tool integration** with Verilator and Vivado
- **Simplified workflows** from a single command-line interface

For implementation details, API reference, and extension guidance, see [HDLForge-Architecture.md](HDLForge-Architecture.md).

---

## 8. Documentation Map

| Document                                                  | Purpose                             | When to Use                                |
|-----------------------------------------------------------|-------------------------------------|--------------------------------------------|
| **[HDLForge.md](HDLForge.md)** (this doc)                | Quick start and overview            | Starting out, quick reference              |
| **[HDLForge-Verilator.md](HDLForge-Verilator.md)**       | Complete Verilator/Cocotb guide     | Writing testbenches, debugging simulations |
| **[HDLForge-Vivado.md](HDLForge-Vivado.md)**             | Complete Vivado synthesis guide     | FPGA implementation, timing closure        |
| **[HDLForge-Architecture.md](HDLForge-Architecture.md)** | Internal architecture & API         | Extending HDLForge, deep debugging         |

### 8.1 Common Workflows

**Getting Started:**
1. Create `.hdlforge.json` file (see tool-specific docs for examples)
2. Run from project directory or use `--project` flag
3. HDLForge handles all environment setup automatically

**Simulation Workflow:**
```bash
hdlforge Verilator --step build --SimTargetName my_test
hdlforge Verilator --step sim --SimTargetName my_test
gtkwave _verilator/my_test/dump.vcd
```

**FPGA Workflow:**
```bash
hdlforge vivado --step new --clean
hdlforge vivado --step syn --run-flow default
hdlforge vivado --step impl --run-flow default
hdlforge vivado --step bit --run-flow default
```

> **📘 Full examples:** See [HDLForge-Verilator.md](HDLForge-Verilator.md#7-examples) and [HDLForge-Vivado.md](HDLForge-Vivado.md#8-examples)
