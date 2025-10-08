# SimTargets Architecture and Data Flow

## Architecture Overview

This document provides a technical overview of how SimTargets work within the HDLForge architecture.

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         HDLForge CLI                             │
│  (hdlforge Verilator --project X.toml --SimTargetName Y)        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Invokes
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  tasks.py: Verilator Task                        │
│  - Loads project file                                            │
│  - Calls verify_sim_target()                                     │
│  - Extracts SimTarget configuration                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Reads
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              <project>.hdlforge.toml File                        │
│                                                                   │
│  [verilator_settings]                                            │
│    build_dir = "_verilator"                                      │
│                                                                   │
│  [verilator_settings.sim_targets.<name>]                         │
│    top_module = "..."                                            │
│    python_file = "..."                                           │
│    build_args = [...]                                            │
│    defines = {...}                                               │
│    parameters = {...}                                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Configuration
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Verilator Compiler                            │
│  - Compiles RTL sources                                          │
│  - Applies defines and parameters                                │
│  - Generates C++ simulation model                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Produces
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              Build Output Directory                              │
│  <build_dir>/                                                    │
│    ├── obj_dir/           (C++ compiled objects)                 │
│    └── V<top_module>      (Verilator executable)                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ If step=sim
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cocotb Test Runner                            │
│  - Sets TOPLEVEL=<top_module>                                    │
│  - Sets MODULE=<python_file_stem>                                │
│  - Sets TESTCASE=<test_name> (if specified)                      │
│  - Adds PYTHONPATH entries                                       │
│  - Executes simulation                                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ Generates
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│        Simulation Output Directory                               │
│  <build_dir>/<SimTargetName>/                                    │
│    ├── dump.vcd           (Waveform data)                        │
│    ├── dump.csv           (CSV export)                           │
│    └── <test logs>        (Cocotb output)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Command Invocation

```bash
hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName main
```

**Flow:**
1. User invokes hdlforge command
2. Parsed by Invoke task system
3. Routed to `Verilator()` task function

### 2. Project Loading

```python
project_file_path = get_project_file_path(project)
working_path, project_data = load_project_data(project_file_path)
```

**Flow:**
1. Locate project file in current directory
2. Load and parse TOML configuration
3. Extract working path and project data dictionary

### 3. SimTarget Verification

```python
verilator_settings = project_data["verilator_settings"]
SimTargetName = verify_sim_target(SimTargetName, verilator_settings)
```

**Verification Logic:**
```python
def verify_sim_target(SimTargetName, verilator_settings):
    if SimTargetName is None:
        # List available targets and exit
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
    elif SimTargetName not in verilator_settings["sim_targets"]:
        # Invalid target name
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")
    
    return SimTargetName
```

### 4. Configuration Extraction

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

**Result:** All configuration values extracted and validated

### 5. Build Step (if step contains "build")

```python
from cocotb.runner import get_runner
runner = get_runner("verilator")

runner.build(
    verilog_sources=veruilator_sources_file,
    hdl_toplevel=f"{top_module}",
    waves=True,
    always=True,
    verbose=False,
    build_dir=f"{build_dir}",
    defines=defines,
    includes=includes_paths_list,
    parameters=parameters,
    log_file=log_file,
    build_args=combined_build_args,
    clean=clean
)
```

**Actions:**
1. Initialize Verilator runner from cocotb
2. Compile all source files
3. Apply defines and parameters
4. Generate C++ simulation model
5. Compile C++ code

### 6. Simulation Step (if step contains "sim")

```python
runner.test(
    hdl_toplevel=f"{top_module}",
    test_module=f"{python_file_path.stem}",
    testcase=test_name,
    build_dir=f"{build_dir}",
    extra_env=extra_env,
    test_dir=f"{build_dir}/{SimTargetName}",
    waves=True
)
```

**Actions:**
1. Set environment variables (TOPLEVEL, MODULE, TESTCASE)
2. Add PYTHONPATH entries
3. Execute Verilator simulation
4. Run cocotb test(s)
5. Generate VCD waveform file
6. Collect test results

## Configuration Schema

### SimTarget Schema (TOML)

```toml
[verilator_settings.sim_targets.<target_name>]
# Required fields
top_module = string              # HDL module name

python_file = string             # Path to test file (relative to project)

# Optional fields
test_name = string | null        # Specific test function name
                                 # Default: null (runs all tests)

build_args = [string]            # Verilator build arguments
                                 # Default: []

defines = {string: string}       # Preprocessor defines
                                 # Default: {}

parameters = {string: string}    # Module parameters
                                 # Default: {}

PYTHONPATH = [string]            # Additional Python paths
                                 # Default: []
```

### Python Representation

```python
SimTarget = {
    "top_module": str,
    "python_file": str,
    "test_name": Optional[str],
    "build_args": List[str],
    "defines": Dict[str, str],
    "parameters": Dict[str, str],
    "PYTHONPATH": List[str]
}
```

## Environment Variables Set by HDLForge

When running a simulation, HDLForge sets these environment variables:

| Variable | Source | Example |
|----------|--------|---------|
| `TOPLEVEL` | `SimTarget["top_module"]` | `"uart_tx"` |
| `TOPLEVEL_LANG` | Fixed | `"verilog"` |
| `MODULE` | `SimTarget["python_file"]` (stem) | `"test_uart"` |
| `TESTCASE` | `SimTarget["test_name"]` | `"test_basic_tx"` |
| `PYTHONPATH` | `SimTarget["PYTHONPATH"]` | Extended with paths |

## File System Layout

### Project Structure

```
project_directory/
├── myproject.hdlforge.toml          # Project configuration
├── rtl/                             # RTL source files
│   ├── uart_tx.sv
│   ├── uart_rx.sv
│   └── interfaces.sv
├── tests/                           # Test files
│   ├── test_uart.py                 # Cocotb tests
│   └── lib/                         # Test utilities
│       └── uart_utils.py
└── _verilator/                      # Build directory
    ├── obj_dir/                     # Verilator objects
    ├── Vuart_tx                     # Verilator executable
    ├── main/                        # SimTarget "main" output
    │   ├── dump.vcd
    │   └── dump.csv
    └── debug/                       # SimTarget "debug" output
        ├── dump.vcd
        └── results.xml
```

## Error Handling Flow

### Missing SimTargetName

```
User Command: hdlforge Verilator --project X.toml --step sim
                                                          ↓
verify_sim_target(SimTargetName=None, verilator_settings)
                                                          ↓
SimTargetName is None → Print available targets → exit(1)
```

### Invalid SimTargetName

```
User Command: hdlforge Verilator --project X.toml --step sim --SimTargetName typo
                                                          ↓
verify_sim_target(SimTargetName="typo", verilator_settings)
                                                          ↓
"typo" not in sim_targets → Print available targets → exit(1)
```

### Valid SimTargetName

```
User Command: hdlforge Verilator --project X.toml --step sim --SimTargetName main
                                                          ↓
verify_sim_target(SimTargetName="main", verilator_settings)
                                                          ↓
"main" in sim_targets → return "main" → Continue execution
```

## Integration Points

### With Cocotb

SimTargets map directly to cocotb's test execution model:

| SimTarget Field | Cocotb Usage |
|----------------|--------------|
| `top_module` | Set as `TOPLEVEL` env var |
| `python_file` | Set as `MODULE` env var (without .py) |
| `test_name` | Set as `TESTCASE` env var |
| `PYTHONPATH` | Extended for test imports |

### With Verilator

SimTargets configure Verilator compilation:

| SimTarget Field | Verilator Usage |
|----------------|-----------------|
| `top_module` | Top-level module to compile |
| `build_args` | Additional compiler flags |
| `defines` | `-D` preprocessor defines |
| `parameters` | `-G` module parameters |

## Performance Characteristics

### Build Step

- **Time:** O(source_files) + O(complexity)
- **Output:** Compiled C++ simulation model
- **Caching:** Verilator uses incremental compilation

### Simulation Step

- **Time:** O(test_complexity) + O(simulation_time)
- **Output:** VCD waveforms, test logs
- **Caching:** No caching; always runs fresh

## Best Practices for Architecture

1. **Separate Build and Sim**: Run build once, sim multiple times
2. **Use Multiple Targets**: Different targets for different scenarios
3. **Isolate Outputs**: Each SimTarget gets its own output directory
4. **Parameterize**: Use `parameters` instead of multiple source files
5. **Organize Tests**: Keep test files organized in dedicated directories

## See Also

- [SimTargets Guide](SimTargets_Guide.md) - User guide and examples
- [SimTargets Quick Reference](SimTargets_Quick_Reference.md) - Command reference
- [tasks.py](../source/project_setup/tasks.py) - Implementation code
