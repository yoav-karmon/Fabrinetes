# HDLForge - Verilator Integration

> **📘 Main Documentation:** [HDLForge.md](HDLForge.md)  
> **📚 Complete Examples:** [HDLForge-Verilator-Examples.md](HDLForge-Verilator-Examples.md)

---

## 1. Overview

### 1.1 What is Verilator Integration?

Fast, cycle-accurate simulation using Python-based Cocotb testbenches.

**Purpose:** Verification with Python testing framework

**Key Benefits:**
- **Speed:** 10-100x faster than traditional simulators
- **Python testbenches:** Familiar Python ecosystem
- **Waveforms:** VCD output (GTKWave compatible)
- **CI/CD friendly:** JUnit XML results

### 1.2 Workflow

```
SystemVerilog → Verilator (build) → Simulation Model → Cocotb (sim) → Results & Waveforms
```

---

## 2. Architecture

### 2.1 Technology Stack

| Component        | Purpose                                    |
|------------------|--------------------------------------------|
| **Verilator**    | Compiles SystemVerilog to simulation model |
| **Cocotb**       | Python coroutine-based testbench framework |
| **cocotb.runner** | Python API for build/test management       |
| **GTKWave**      | Waveform viewer                            |

### 2.2 Execution Flow

```
hdlforge Verilator --step build --SimTargetName <target>
    ↓
ProjectLoader → Extract config → Collect sources
    ↓
cocotb.runner.get_runner("verilator")
    ↓
Verilator compiles SystemVerilog
    ↓
hdlforge Verilator --step sim --SimTargetName <target>
    ↓
cocotb.runner.test() → Execute Python testbench
    ↓
Results: dump.vcd + results.xml
```

**Key:** HDLForge uses `cocotb.runner` Python API (no makefiles needed).

---

## 3. Configuration Structure

### 3.1 Minimal Example

```json
{
  "settings": {
    "project_name": "my_project",
    "project_path": "$REPO_TOP/my_project"
  },
  "verilator_settings": {
    "build_dir": "_verilator",
    "includes_paths": [],
    "sim_targets": [
      {
        "name": "basic_test",
        "top_module": "top",
        "test_name": "my_test",
        "python_file": "tests/my_test.py",
        "build_args": ["--trace"],
        "PYTHONPATH": ["tests"]
      }
    ]
  },
  "sources": {
    "files": [
      {
        "verilator": true,
        "relative_to_project_path": true,
        "file": ["sources/rtl/top.sv"]
      }
    ]
  }
}
```

### 3.2 Key Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `build_dir` | string | No | Build directory, default: `_verilator` |
| `includes_paths` | array | No | SystemVerilog include directories |
| `sim_targets` | array | Yes | Simulation target configurations |

### 3.3 Simulation Target Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Target identifier for `--SimTargetName` |
| `top_module` | string | Yes | Top-level module name |
| `test_name` | string | Yes | Python test function name (must have `@cocotb.test()`) |
| `python_file` | string | Yes | Path to Python test file |
| `build_args` | array | No | Verilator flags (e.g., `["--trace"]`) |
| `defines` | object | No | Preprocessor defines |
| `parameters` | object | No | Module parameters |
| `PYTHONPATH` | array | No | Python module search paths |

---

## 4. Basic Usage

### 4.1 Build Command

**Purpose:** Compile SystemVerilog with Verilator

```bash
hdlforge Verilator --step build --SimTargetName <target> [--clean] [--flags "<flags>"]
```

**Options:**
- `--clean` - Force rebuild
- `--flags "<flags>"` - Additional Verilator flags
- `--extra-env KEY=value` - Environment variables

**Output:** `<project_path>/_verilator/<target>/`

### 4.2 Simulate Command

**Purpose:** Run Python testbench with Cocotb

```bash
hdlforge Verilator --step sim --SimTargetName <target> [--extra-env KEY=value]
```

**Output:**
- `dump.vcd` - Waveform file (GTKWave)
- `results.xml` - Test results (JUnit format)

**Python Testbench Requirements:**
```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

@cocotb.test()
async def my_test(dut):
    """Test function"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    await RisingEdge(dut.clk)
    # Test logic...
```

---

## 5. Common Errors & Solutions

### 5.1 Build Errors

**Module Not Found**
```
%Error: Cannot find file containing module: 'my_module'
```
→ Check `sources.files` array and `relative_to_project_path` setting

**Missing Includes**
```
`include "my_header.svh": cannot find file
```
→ Add directory to `verilator_settings.includes_paths`

### 5.2 Simulation Errors

**Python Module Not Found**
```
ModuleNotFoundError: No module named 'my_test'
```
→ Verify `python_file` path and add directory to target's `PYTHONPATH`

**Test Function Not Found**
```
AttributeError: module 'my_test' has no attribute 'test_function'
```
→ Verify `test_name` matches function name and has `@cocotb.test()` decorator

**Signal Not Found**
```
AttributeError: 'SimHandle' object has no attribute 'xxx'
```
→ Check DUT signal names match SystemVerilog exactly

### 5.3 Debugging Tips

1. **Enable verbose output:**
   ```bash
   hdlforge Verilator --step build --SimTargetName test --flags "--debug"
   ```

2. **View waveforms:**
   ```bash
   gtkwave <project_path>/_verilator/<target>/dump.vcd
   ```

3. **Add logging to testbench:**
   ```python
   cocotb.log.info(f"Signal value: {dut.my_signal.value}")
   ```

4. **Check environment:**
   ```bash
   echo $REPO_TOP
   echo $PYTHONPATH
   ```

---

## 6. Best Practices

### 6.1 Project Organization

```
project/
├── project.hdlforge.json
├── sources/
│   ├── rtl/          # RTL source files
│   ├── include/      # Include files (.svh)
│   └── interfaces/   # Interface definitions
└── tests/
    ├── test1.py
    ├── test2.py
    ├── utils/        # Shared utilities
    └── monitors/     # Reusable monitors
```

### 6.2 Build Args

**Essential flags:**
- `--trace` - Always use for waveform generation
- `--coverage` - Enable coverage collection
- `--assert` - Enable SystemVerilog assertions

```json
"build_args": ["--trace", "--assert", "--coverage"]
```

### 6.3 PYTHONPATH Organization

```json
"PYTHONPATH": [
  "tests",           # Test files
  "tests/utils",     # Shared utilities
  "tests/monitors"   # Reusable monitors
]
```

### 6.4 Test Development

1. **Start simple** - Basic connectivity test first
2. **Add complexity gradually** - One feature at a time
3. **Use logging** - Liberal `cocotb.log.info()`
4. **Check waveforms** - Always verify in GTKWave
5. **Modular tests** - Separate reset, basic, edge cases
6. **Reusable components** - Create monitors and drivers

---

## 7. Quick Reference

### Common Commands

```bash
# Build and simulate
cd <project>
hdlforge Verilator --step build --SimTargetName my_test
hdlforge Verilator --step sim --SimTargetName my_test

# Clean rebuild
hdlforge Verilator --step build --SimTargetName my_test --clean

# View waveforms
gtkwave _verilator/my_test/dump.vcd

# With additional flags
hdlforge Verilator --step build --SimTargetName test --flags "--debug --coverage"

# With environment variables
hdlforge Verilator --step sim --SimTargetName test --extra-env DEBUG=1,VERBOSE=1
```

### Typical Workflow

```bash
# 1. Create project configuration (my_project.hdlforge.json)
# 2. Write SystemVerilog RTL
# 3. Write Python testbench with @cocotb.test()
# 4. Build and simulate
hdlforge Verilator --step build --SimTargetName my_test
hdlforge Verilator --step sim --SimTargetName my_test
# 5. Debug with waveforms
gtkwave _verilator/my_test/dump.vcd
```

---

## 8. Additional Resources

- **Complete Examples:** [HDLForge-Verilator-Examples.md](HDLForge-Verilator-Examples.md)
- **Cocotb Documentation:** https://docs.cocotb.org/
- **Verilator Manual:** https://verilator.org/guide/latest/
- **GTKWave:** http://gtkwave.sourceforge.net/
- **Architecture Details:** [HDLForge-Architecture.md](HDLForge-Architecture.md)
