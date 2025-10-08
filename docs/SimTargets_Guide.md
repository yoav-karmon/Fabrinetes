# SimTargets in HDLForge

## Overview

**SimTargets** are a core concept in HDLForge that define specific simulation configurations for Verilator-based verification. Each SimTarget represents a unique simulation scenario with its own top module, test file, parameters, and build settings.

## What is a SimTarget?

A SimTarget is a named configuration within the `verilator_settings` section of an HDLForge project file (`.hdlforge.toml`) that specifies:

- **Top module** to simulate
- **Python test file** (cocotb testbench)
- **Build arguments** for Verilator compilation
- **Defines and parameters** for the HDL code
- **Test name** (specific test case to run)
- **PYTHONPATH** additions for Python dependencies

## SimTarget Structure

### Location in Project File

SimTargets are defined in the `[verilator_settings.sim_targets]` section of your `.hdlforge.toml` file:

```toml
[verilator_settings]
build_dir = "_verilator"
includes_paths = ["$REPO_TOP/rtl/includes"]

[verilator_settings.sim_targets.main]
top_module = "my_module"
python_file = "tests/test_main.py"
test_name = "test_basic"
build_args = ["--trace", "--timing"]
defines = {}
parameters = {}
PYTHONPATH = ["$REPO_TOP/tests/lib"]

[verilator_settings.sim_targets.advanced]
top_module = "my_module"
python_file = "tests/test_advanced.py"
test_name = "test_advanced_scenario"
build_args = ["--trace", "--timing", "-O3"]
defines = {"DEBUG": "1"}
parameters = {"WIDTH": "32"}
PYTHONPATH = ["$REPO_TOP/tests/lib"]
```

## SimTarget Configuration Options

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `top_module` | string | Name of the top-level SystemVerilog/Verilog module to simulate |
| `python_file` | string | Path to the Python test file (cocotb testbench), relative to project directory |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `test_name` | string | `None` | Specific test function to run in the Python file. If not specified, all tests run |
| `build_args` | list | `[]` | Additional Verilator compilation arguments (e.g., `--trace`, `--timing`, `-O3`) |
| `defines` | dict | `{}` | Preprocessor defines to pass to Verilator (e.g., `{"DEBUG": "1"}`) |
| `parameters` | dict | `{}` | Module parameters/generics (e.g., `{"WIDTH": "32", "DEPTH": "1024"}`) |
| `PYTHONPATH` | list | `[]` | Additional Python paths to add for test execution |

## How SimTargets Work

### 1. Command Line Usage

SimTargets are specified using the `--SimTargetName` parameter:

```bash
# Build step
hdlforge Verilator --project myproject.hdlforge.toml --step build --SimTargetName main

# Simulation step
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main

# Combined build and simulation
hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName main
```

### 2. Verification Process

When you execute a command with a SimTarget, HDLForge:

1. **Validates** the SimTargetName exists in `verilator_settings.sim_targets`
2. **Extracts** the configuration (top_module, python_file, build_args, etc.)
3. **Compiles** the Verilator sources with the specified settings
4. **Runs** the cocotb test with the specified Python file and test name
5. **Generates** output in `<build_dir>/<SimTargetName>/` directory

### 3. Implementation Details

The SimTarget verification is handled by the `verify_sim_target()` function in `tasks.py`:

```python
def verify_sim_target(SimTargetName, verilator_settings):
    if SimTargetName is None:
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
    elif(SimTargetName not in verilator_settings["sim_targets"]):
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")
    
    return SimTargetName
```

Once validated, the SimTarget is extracted and used:

```python
SimTarget = verilator_settings["sim_targets"][SimTargetName]
top_module = SimTarget["top_module"]
build_args = SimTarget.get("build_args", [])
defines = SimTarget.get("defines", {})
parameters = SimTarget.get("parameters", {})
python_file_path = Path(working_path) / SimTarget["python_file"]
test_name = SimTarget.get("test_name", None)
PYTHONPATH = SimTarget.get("PYTHONPATH", [])
```

## Output and Results

### Build Output

The build process generates compiled Verilator C++ code in:
```
<verilator_settings.build_dir>/
```

### Simulation Output

Simulation results are stored in:
```
<verilator_settings.build_dir>/<SimTargetName>/
├── dump.vcd      # Waveform file (if waves=True)
├── dump.csv      # CSV export of waveforms (if conversion enabled)
└── <test logs>   # Cocotb test output
```

## Use Cases and Examples

### Use Case 1: Multiple Test Scenarios

You might have different test scenarios for the same module:

```toml
[verilator_settings.sim_targets.smoke_test]
top_module = "uart"
python_file = "tests/test_uart.py"
test_name = "test_basic_tx_rx"

[verilator_settings.sim_targets.stress_test]
top_module = "uart"
python_file = "tests/test_uart.py"
test_name = "test_high_speed_burst"
build_args = ["--trace", "-O3"]

[verilator_settings.sim_targets.debug]
top_module = "uart"
python_file = "tests/test_uart.py"
build_args = ["--trace", "--trace-structs"]
defines = {"DEBUG": "1", "VERBOSE": "1"}
```

### Use Case 2: Different Top Modules

You might want to simulate different modules in the same project:

```toml
[verilator_settings.sim_targets.fifo_test]
top_module = "async_fifo"
python_file = "tests/test_fifo.py"

[verilator_settings.sim_targets.memory_test]
top_module = "dual_port_ram"
python_file = "tests/test_memory.py"

[verilator_settings.sim_targets.full_system]
top_module = "system_top"
python_file = "tests/test_integration.py"
```

### Use Case 3: Parameterized Testing

Test the same module with different parameter values:

```toml
[verilator_settings.sim_targets.width_8]
top_module = "data_processor"
python_file = "tests/test_processor.py"
parameters = {"DATA_WIDTH": "8"}

[verilator_settings.sim_targets.width_16]
top_module = "data_processor"
python_file = "tests/test_processor.py"
parameters = {"DATA_WIDTH": "16"}

[verilator_settings.sim_targets.width_32]
top_module = "data_processor"
python_file = "tests/test_processor.py"
parameters = {"DATA_WIDTH": "32"}
```

## Best Practices

### 1. Naming Conventions

- Use descriptive names: `main`, `debug`, `smoke_test`, `stress_test`
- Keep names lowercase with underscores
- Make the purpose clear from the name

### 2. Organization

- Create a `main` target as the default/primary test
- Use separate targets for different test scenarios
- Group related tests with similar prefixes (e.g., `perf_test_1`, `perf_test_2`)

### 3. Build Arguments

- Use `--trace` for waveform generation during development
- Use `-O3` for performance testing
- Use `--trace-structs` for detailed debugging
- Use `--timing` for timing-aware simulation

### 4. Python Path Management

- Add test library paths via `PYTHONPATH`
- Use environment variables in paths (e.g., `$REPO_TOP/tests/lib`)
- Keep test utilities in a shared directory

### 5. Test Isolation

- Each SimTarget gets its own output directory
- Simulations don't interfere with each other
- Clean builds can be done per-target with `--clean`

## Error Handling

### Missing SimTargetName

If you forget to specify `--SimTargetName`:

```
Available SimTargetNames: main, debug, stress_test
[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>
```

### Invalid SimTargetName

If you specify a non-existent SimTarget:

```
Available SimTargetNames: main, debug, stress_test
[!x!]  SimTargetName 'typo' not found in verilator_settings['sim_targets']
```

## Integration with Cocotb

SimTargets are designed to work seamlessly with cocotb testbenches:

1. The `python_file` points to your cocotb test file
2. The `test_name` (if specified) selects a specific test function
3. The `top_module` is set as the `TOPLEVEL` for cocotb
4. Additional paths in `PYTHONPATH` are made available to the test

### Example Cocotb Test

```python
# tests/test_main.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def test_basic(dut):
    """Basic functionality test"""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())
    
    await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    
    # Test logic here...

@cocotb.test()
async def test_advanced(dut):
    """Advanced scenario test"""
    # Advanced test logic here...
```

With SimTarget configuration:
```toml
[verilator_settings.sim_targets.basic]
python_file = "tests/test_main.py"
test_name = "test_basic"  # Runs only test_basic

[verilator_settings.sim_targets.advanced]
python_file = "tests/test_main.py"
test_name = "test_advanced"  # Runs only test_advanced

[verilator_settings.sim_targets.all]
python_file = "tests/test_main.py"
# No test_name specified - runs all tests
```

## Workflow Examples

### Development Workflow

```bash
# 1. Run quick smoke test
hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName smoke_test

# 2. Debug with full tracing
hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName debug

# 3. View waveforms
gtkwave _verilator/debug/dump.vcd
```

### CI/CD Workflow

```bash
# Run all test targets in sequence
for target in smoke_test stress_test regression_test; do
    hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName $target
done
```

### Iterative Development

```bash
# Build once
hdlforge Verilator --project myproject.hdlforge.toml --step build --SimTargetName main

# Run simulations multiple times without rebuilding
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
# (modify test file)
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
# (modify test file again)
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
```

## Summary

SimTargets provide a flexible, declarative way to define multiple simulation scenarios within a single HDLForge project. They enable:

- **Reusability**: Same RTL, different tests
- **Organization**: Clear separation of test scenarios
- **Flexibility**: Easy parameter and configuration changes
- **Automation**: Simple command-line interface for CI/CD
- **Traceability**: Separate output directories per target

By using SimTargets effectively, you can create a comprehensive verification suite that covers all aspects of your HDL design.
