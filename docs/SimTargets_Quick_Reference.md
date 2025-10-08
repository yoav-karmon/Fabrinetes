# SimTargets Quick Reference

## Command Syntax

```bash
hdlforge Verilator --project <file>.hdlforge.toml --step <build|sim> --SimTargetName <target>
```

## Basic Usage

```bash
# Build only
hdlforge Verilator --project myproject.hdlforge.toml --step build --SimTargetName main

# Simulate only (requires prior build)
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main

# Build and simulate
hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName main

# Clean build
hdlforge Verilator --project myproject.hdlforge.toml --step build --SimTargetName main --clean
```

## SimTarget Configuration Template

```toml
[verilator_settings]
build_dir = "_verilator"
includes_paths = ["$REPO_TOP/rtl/includes"]

[verilator_settings.sim_targets.<target_name>]
top_module = "module_name"              # REQUIRED: Top module to simulate
python_file = "tests/test_file.py"      # REQUIRED: Cocotb test file
test_name = "test_function_name"        # OPTIONAL: Specific test to run
build_args = ["--trace", "--timing"]    # OPTIONAL: Verilator flags
defines = {"DEBUG": "1"}                # OPTIONAL: Preprocessor defines
parameters = {"WIDTH": "32"}            # OPTIONAL: Module parameters
PYTHONPATH = ["$REPO_TOP/tests/lib"]    # OPTIONAL: Python paths
```

## Configuration Fields

| Field | Required | Type | Example |
|-------|----------|------|---------|
| `top_module` | ✓ | string | `"my_module"` |
| `python_file` | ✓ | string | `"tests/test.py"` |
| `test_name` | ✗ | string | `"test_basic"` |
| `build_args` | ✗ | list | `["--trace", "-O3"]` |
| `defines` | ✗ | dict | `{"DEBUG": "1"}` |
| `parameters` | ✗ | dict | `{"WIDTH": "32"}` |
| `PYTHONPATH` | ✗ | list | `["$REPO_TOP/lib"]` |

## Common Build Arguments

| Argument | Purpose |
|----------|---------|
| `--trace` | Enable waveform generation (dump.vcd) |
| `--timing` | Enable timing-aware simulation |
| `-O3` | Optimize for performance |
| `--trace-structs` | Detailed struct tracing for debugging |
| `--coverage` | Enable coverage analysis |

## Output Locations

```
<build_dir>/                    # Verilator build output
<build_dir>/<SimTargetName>/    # Simulation-specific output
    ├── dump.vcd                # Waveform file
    └── dump.csv                # CSV export (if enabled)
```

## Example: Multiple Targets

```toml
# Basic smoke test
[verilator_settings.sim_targets.smoke_test]
top_module = "uart"
python_file = "tests/test_uart.py"
test_name = "test_basic_tx_rx"

# Performance test
[verilator_settings.sim_targets.perf_test]
top_module = "uart"
python_file = "tests/test_uart.py"
test_name = "test_high_speed"
build_args = ["-O3"]

# Debug test with full tracing
[verilator_settings.sim_targets.debug]
top_module = "uart"
python_file = "tests/test_uart.py"
build_args = ["--trace", "--trace-structs"]
defines = {"DEBUG": "1"}
```

## Common Patterns

### Pattern 1: Same Module, Different Tests

```toml
[verilator_settings.sim_targets.test1]
top_module = "my_module"
python_file = "tests/test_suite.py"
test_name = "test_scenario_1"

[verilator_settings.sim_targets.test2]
top_module = "my_module"
python_file = "tests/test_suite.py"
test_name = "test_scenario_2"
```

### Pattern 2: Same Module, Different Parameters

```toml
[verilator_settings.sim_targets.width_8]
top_module = "processor"
python_file = "tests/test_processor.py"
parameters = {"DATA_WIDTH": "8"}

[verilator_settings.sim_targets.width_32]
top_module = "processor"
python_file = "tests/test_processor.py"
parameters = {"DATA_WIDTH": "32"}
```

### Pattern 3: Different Modules

```toml
[verilator_settings.sim_targets.fifo_test]
top_module = "async_fifo"
python_file = "tests/test_fifo.py"

[verilator_settings.sim_targets.ram_test]
top_module = "dual_port_ram"
python_file = "tests/test_ram.py"

[verilator_settings.sim_targets.integration]
top_module = "system_top"
python_file = "tests/test_system.py"
```

## Troubleshooting

### Error: SimTargetName must be specified

```bash
# Fix: Add --SimTargetName parameter
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
```

### Error: SimTargetName 'X' not found

```bash
# Check available targets in your .hdlforge.toml file
# Look in [verilator_settings.sim_targets] section
```

### Missing Output Files

```bash
# Ensure you ran build before sim
hdlforge Verilator --project myproject.hdlforge.toml --step build --SimTargetName main
hdlforge Verilator --project myproject.hdlforge.toml --step sim --SimTargetName main
```

### No Waveform Generated

```toml
# Add --trace to build_args
[verilator_settings.sim_targets.main]
top_module = "my_module"
python_file = "tests/test.py"
build_args = ["--trace"]  # Add this line
```

## Tips

- **Start with a `main` target** as your default test
- **Use `--trace` during development** for debugging
- **Remove `--trace` for CI/CD** to speed up tests
- **Use separate targets** for different test scenarios
- **Group related targets** with consistent naming
- **Build once, sim many times** during iterative development

## See Also

- [Full SimTargets Guide](SimTargets_Guide.md)
- [HDLForge Documentation](../source/project_setup/HDLForge_Documentation.toml)
- [README](../README.md)
