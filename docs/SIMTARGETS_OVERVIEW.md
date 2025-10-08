# SimTargets in HDLForge - Complete Overview

## What Are SimTargets?

**SimTargets** are named simulation configurations in HDLForge that allow you to define multiple test scenarios for your hardware designs within a single project. Think of them as "build profiles" for verification - each SimTarget represents a different way to test your HDL code.

## Why Use SimTargets?

### The Problem They Solve

Without SimTargets, you would need:
- Separate project files for each test configuration
- Manual command-line parameter management
- Complex scripting to organize different test scenarios
- No clear separation between different test types

### What SimTargets Provide

✅ **Declarative Configuration** - Define all test scenarios in one place
✅ **Reusability** - Same RTL code, multiple test configurations  
✅ **Organization** - Clear separation of test scenarios (smoke, debug, performance, etc.)  
✅ **Flexibility** - Easy parameter changes without code modifications  
✅ **Automation** - Simple CLI for CI/CD integration  
✅ **Traceability** - Separate output directories per target  

## Quick Example

### Configuration (in `.hdlforge.toml`)

```toml
[verilator_settings]
build_dir = "_verilator"
includes_paths = ["$REPO_TOP/rtl/includes"]

# Quick smoke test
[verilator_settings.sim_targets.smoke_test]
top_module = "uart"
python_file = "tests/test_uart.py"
test_name = "test_basic_tx_rx"

# Debug with full tracing
[verilator_settings.sim_targets.debug]
top_module = "uart"
python_file = "tests/test_uart.py"
build_args = ["--trace", "--trace-structs"]
defines = {"DEBUG": "1"}

# Performance test
[verilator_settings.sim_targets.perf_test]
top_module = "uart"
python_file = "tests/test_uart.py"
test_name = "test_high_speed_burst"
build_args = ["-O3"]
```

### Usage (command line)

```bash
# Run smoke test
hdlforge Verilator --project uart.hdlforge.toml --step build sim --SimTargetName smoke_test

# Run debug session with full tracing
hdlforge Verilator --project uart.hdlforge.toml --step build sim --SimTargetName debug

# Run performance test
hdlforge Verilator --project uart.hdlforge.toml --step build sim --SimTargetName perf_test
```

### Results

Each SimTarget creates its own output directory:
```
_verilator/
├── smoke_test/
│   ├── dump.vcd
│   └── test_results.xml
├── debug/
│   ├── dump.vcd  (with detailed traces)
│   └── test_results.xml
└── perf_test/
    ├── dump.vcd
    └── test_results.xml
```

## Key Concepts

### 1. Configuration Fields

| Field | Required | Purpose |
|-------|----------|---------|
| `top_module` | ✓ | HDL module to simulate |
| `python_file` | ✓ | Cocotb test file |
| `test_name` | ✗ | Specific test function to run |
| `build_args` | ✗ | Verilator compiler flags |
| `defines` | ✗ | Preprocessor defines |
| `parameters` | ✗ | Module parameters |
| `PYTHONPATH` | ✗ | Python import paths |

### 2. Workflow Steps

```
Command → Verify SimTarget → Extract Config → Build → Simulate → Output
```

1. **Command**: User specifies `--SimTargetName`
2. **Verify**: HDLForge checks the target exists
3. **Extract**: Configuration is extracted from TOML
4. **Build**: Verilator compiles with specified options
5. **Simulate**: Cocotb runs tests
6. **Output**: Results saved to `<build_dir>/<SimTargetName>/`

### 3. Integration Points

**With Verilator:**
- `top_module` → top-level module to compile
- `build_args` → compiler flags
- `defines` → `-D` preprocessor defines
- `parameters` → `-G` module parameters

**With Cocotb:**
- `python_file` → test module to run
- `test_name` → specific test function (optional)
- `PYTHONPATH` → additional import paths
- `top_module` → DUT interface

## Common Use Cases

### Use Case 1: Development Stages

```toml
# Fast iteration during development
[verilator_settings.sim_targets.quick]
top_module = "my_module"
python_file = "tests/test.py"

# Full verification before commit
[verilator_settings.sim_targets.full]
top_module = "my_module"
python_file = "tests/test.py"
build_args = ["--trace", "--coverage"]

# CI/CD optimized version
[verilator_settings.sim_targets.ci]
top_module = "my_module"
python_file = "tests/test.py"
build_args = ["-O3"]
```

### Use Case 2: Different Test Scenarios

```toml
# Normal operation
[verilator_settings.sim_targets.normal]
top_module = "processor"
python_file = "tests/test_processor.py"
test_name = "test_normal_operation"

# Edge cases
[verilator_settings.sim_targets.edge_cases]
top_module = "processor"
python_file = "tests/test_processor.py"
test_name = "test_edge_cases"

# Error injection
[verilator_settings.sim_targets.error_injection]
top_module = "processor"
python_file = "tests/test_processor.py"
test_name = "test_error_handling"
defines = {"ENABLE_ERROR_INJECTION": "1"}
```

### Use Case 3: Parameterized Testing

```toml
# Test with different data widths
[verilator_settings.sim_targets.width_8]
top_module = "data_path"
python_file = "tests/test_data_path.py"
parameters = {"DATA_WIDTH": "8"}

[verilator_settings.sim_targets.width_16]
top_module = "data_path"
python_file = "tests/test_data_path.py"
parameters = {"DATA_WIDTH": "16"}

[verilator_settings.sim_targets.width_32]
top_module = "data_path"
python_file = "tests/test_data_path.py"
parameters = {"DATA_WIDTH": "32"}
```

## Documentation Structure

The SimTargets documentation is organized into four main documents:

### 📘 [SimTargets Guide](SimTargets_Guide.md)
**For:** Users wanting to learn about SimTargets  
**Content:** Complete overview, examples, best practices, integration with Cocotb

### 📄 [SimTargets Quick Reference](SimTargets_Quick_Reference.md)
**For:** Daily usage and quick lookup  
**Content:** Command syntax, configuration templates, common patterns

### 🔧 [SimTargets Architecture](SimTargets_Architecture.md)
**For:** Developers and advanced users  
**Content:** Technical details, data flow, system architecture, integration points

### 🔍 [SimTargets Troubleshooting](SimTargets_Troubleshooting.md)
**For:** Debugging issues  
**Content:** Common errors, solutions, diagnostic commands, debugging tips

## Getting Started Path

**New to SimTargets? Follow this path:**

1. **Start Here** → Read this overview document (you are here!)
2. **Learn Basics** → Read sections 1-3 of [SimTargets Guide](SimTargets_Guide.md)
3. **Try It Out** → Use examples from [Quick Reference](SimTargets_Quick_Reference.md)
4. **Deep Dive** → Read full [SimTargets Guide](SimTargets_Guide.md)
5. **Keep Handy** → Bookmark [Quick Reference](SimTargets_Quick_Reference.md) for daily use
6. **When Stuck** → Check [Troubleshooting Guide](SimTargets_Troubleshooting.md)
7. **Go Advanced** → Study [Architecture](SimTargets_Architecture.md) for deep understanding

## Quick Start Template

Here's a minimal SimTarget configuration to get started:

```toml
# Your project file: myproject.hdlforge.toml

[settings]
project_name = "myproject"
project_path = "$REPO_TOP/projects/myproject"

[verilator_settings]
build_dir = "_verilator"
includes_paths = []

# Your first SimTarget
[verilator_settings.sim_targets.main]
top_module = "my_top_module"
python_file = "tests/test_main.py"
build_args = ["--trace"]
```

Then run:
```bash
hdlforge Verilator --project myproject.hdlforge.toml --step build sim --SimTargetName main
```

## Common Commands

```bash
# Build and simulate
hdlforge Verilator --project <file>.hdlforge.toml --step build sim --SimTargetName <target>

# Build only (faster iteration)
hdlforge Verilator --project <file>.hdlforge.toml --step build --SimTargetName <target>

# Simulate only (requires prior build)
hdlforge Verilator --project <file>.hdlforge.toml --step sim --SimTargetName <target>

# Clean build
hdlforge Verilator --project <file>.hdlforge.toml --step build --SimTargetName <target> --clean

# View waveforms
gtkwave _verilator/<target>/dump.vcd
```

## Best Practices Summary

1. ✅ **Start with a `main` target** for your primary test
2. ✅ **Use descriptive names** (smoke_test, debug, perf_test)
3. ✅ **Enable tracing during development** (`--trace` in build_args)
4. ✅ **Disable tracing for CI/CD** (remove --trace, add -O3)
5. ✅ **One target per test scenario** (don't overload targets)
6. ✅ **Use parameters** instead of multiple source files
7. ✅ **Organize tests in directories** (tests/unit, tests/integration)
8. ✅ **Build once, sim many times** during iteration

## Key Takeaways

🎯 **SimTargets = Configuration Profiles for Testing**

Each SimTarget is a named configuration that specifies:
- Which module to test
- Which test to run
- How to compile it
- Where to put the results

🎯 **Declarative > Imperative**

Instead of complex scripts with command-line arguments, you declare all configurations in TOML and select them by name.

🎯 **Flexibility Without Complexity**

Add new test scenarios without changing code - just add a new SimTarget in the TOML file.

🎯 **Built for CI/CD**

Simple command-line interface makes automation easy:
```bash
for target in smoke_test unit_test integration_test; do
    hdlforge Verilator --project test.hdlforge.toml --step build sim --SimTargetName $target
done
```

## Next Steps

- **Read** the [SimTargets Guide](SimTargets_Guide.md) for complete details
- **Bookmark** the [Quick Reference](SimTargets_Quick_Reference.md)
- **Try** creating your first SimTarget
- **Experiment** with different configurations
- **Share** your use cases with the community

## Questions?

- Check the [Troubleshooting Guide](SimTargets_Troubleshooting.md)
- Review the [Architecture](SimTargets_Architecture.md) for technical details
- Open an issue on GitHub
- Email: yoav@karmon.biz

---

**Ready to get started?** Head to the [SimTargets Guide](SimTargets_Guide.md)!
