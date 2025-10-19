# HDLForge v2.0 Migration Guide

## Overview

HDLForge has been updated from version 1.x to version 2.0 with significant improvements to the command-line interface. This guide helps users migrate from the old format to the new, cleaner interface.

## What Changed

### 🔄 Command Structure Change

**Old Format (v1.x) - No Longer Supported:**
```bash
hdlforge <project_file> <command> [options]
```

**New Format (v2.0) - Required:**
```bash
hdlforge <command> --project <project_file> [options]
```

### 🛠️ Technical Changes

- **Replaced `invoke` with `argparse`**: Better command-line parsing and error handling
- **Simplified argument handling**: Cleaner, more predictable command structure
- **Removed dependency**: No longer requires the `invoke` Python package
- **Enhanced error messages**: Clear usage instructions when commands are used incorrectly

## Migration Examples

### Verilator Commands

**Before (v1.x):**
```bash
hdlforge <project_file.hdlforge.toml> Verilator --step sim --SimTargetName <target_name>
hdlforge <project_file.hdlforge.toml> Verilator --step build --SimTargetName <target_name> --clean
```

**After (v2.0):**
```bash
hdlforge Verilator --project <project_file.hdlforge.toml> --step sim --SimTargetName <target_name>
hdlforge Verilator --project <project_file.hdlforge.toml> --step build --SimTargetName <target_name> --clean
```

### Vivado Commands

**Before (v1.x):**
```bash
hdlforge <project_file.hdlforge.toml> vivado --step new --clean
hdlforge <project_file.hdlforge.toml> vivado --step syn --run-flow <flow_name>
```

**After (v2.0):**
```bash
hdlforge vivado --project <project_file.hdlforge.toml> --step new --clean
hdlforge vivado --project <project_file.hdlforge.toml> --step syn --run-flow <flow_name>
```

### Help Commands

**Before (v1.x):**
```bash
hdlforge help
hdlforge projects
```

**After (v2.0):**
```bash
hdlforge help
hdlforge projects
```
> **Note**: Help commands remain unchanged and don't require `--project`

## Benefits of v2.0

### ✅ Improved User Experience
- **Consistent Interface**: All commands follow the same pattern
- **Clear Error Messages**: Better feedback when commands are used incorrectly
- **Explicit Parameters**: The `--project` parameter makes it clear which project file is being used

### ✅ Technical Improvements
- **Reduced Dependencies**: No longer requires `invoke` package
- **Better Parsing**: `argparse` provides more robust command-line argument handling
- **Cleaner Code**: Simplified internal implementation

### ✅ Better Error Handling
```bash
# Old format now shows clear error message:
$ hdlforge <project_file.hdlforge.toml> Verilator --step sim
❌ --project argument is required
Usage: hdlforge <command> --project <project_file> [options]
Example: hdlforge Verilator --project <project_file.hdlforge.toml> --step sim --SimTargetName <target_name>
```

## Project Configuration Structure

### TOML File Structure
```toml
[settings]
project_name = "<project_name>"
project_path = "<project_path>"

[verilator_settings]
build_dir = "<build_directory>"

[[verilator_settings.sim_targets]]
name = "<target_name>"
top_module = "<top_module_name>"
test_name = "<test_function_name>"
python_file = "<test_file.py>"
build_args = ["<build_argument>"]
defines = ["<define_name>"]
parameters = ["<parameter_name>=<value>"]

[vivado_settings]
project_name = "<vivado_project_name>"
top_module = "<top_module_name>"
part = "<fpga_part_number>"

[[vivado_settings.runs_flow]]
name = "<flow_name>"
synth = "<synthesis_run_name>"
impl = ["<implementation_run_name>"]
```

### Simulation Target Structure
Each simulation target in `[[verilator_settings.sim_targets]]` defines:
- **name**: Target identifier used with `--SimTargetName`
- **top_module**: SystemVerilog top-level module name
- **test_name**: Python test function name (decorated with `@cocotb.test()`)
- **python_file**: Path to test file relative to project
- **build_args**: Additional Verilator compilation flags
- **defines**: Preprocessor defines for compilation
- **parameters**: Module parameters for instantiation

## Complete Command Reference

### Verilator Commands
```bash
# Build (compile SystemVerilog to C++)
hdlforge Verilator --project <project_file.hdlforge.toml> --step build --SimTargetName <target_name> [--clean] [--extra-env <env_var>=<value>] [--flags <flags>]

# Simulation (run simulation - requires successful build)
hdlforge Verilator --project <project_file.hdlforge.toml> --step sim --SimTargetName <target_name>
```

### Vivado Commands
```bash
# Create new project
hdlforge vivado --project <project_file.hdlforge.toml> --step new --clean

# Synthesis
hdlforge vivado --project <project_file.hdlforge.toml> --step syn --run-flow <flow_name>

# Implementation
hdlforge vivado --project <project_file.hdlforge.toml> --step impl --run-flow <flow_name>

# Generate bitstream
hdlforge vivado --project <project_file.hdlforge.toml> --step bit --run-flow <flow_name>

# List runs
hdlforge vivado --project <project_file.hdlforge.toml> --step list_runs

# Reset run
hdlforge vivado --project <project_file.hdlforge.toml> --step reset_run
```

### Project Management Commands
```bash
# Show help
hdlforge help

# List available projects
hdlforge projects

# Get detailed help for specific tool
hdlforge Verilator --help
hdlforge vivado --help
```

## Troubleshooting

### Common Migration Issues

**Issue**: Command fails with "❌ --project argument is required"
**Solution**: Add `--project <project_file.hdlforge.toml>` to your command

**Issue**: Old scripts or documentation still use v1.x format
**Solution**: Update all references to use the new `--project` parameter

**Issue**: Confusion about which format to use
**Solution**: Always use the new format: `hdlforge <command> --project <project_file> [options]`

### Getting Help

If you encounter issues during migration:

1. **Check the help**: `hdlforge help`
2. **Verify project file**: `hdlforge projects`
3. **Test with example**: Use the `addr_32bit` example to verify your setup
4. **Check logs**: HDLForge logs are saved to `/opt/project_setup/logs/`

## Example Migration Script

Here's a simple script to help migrate common commands:

```bash
#!/bin/bash
# Migration helper script

PROJECT_FILE="<project_file.hdlforge.toml>"
TARGET_NAME="<target_name>"

echo "Testing HDLForge v2.0 commands..."

# Test help command
echo "1. Testing help command..."
hdlforge help

# Test projects command
echo "2. Testing projects command..."
hdlforge projects

# Test Verilator build
echo "3. Testing Verilator build..."
hdlforge Verilator --project "$PROJECT_FILE" --step build --SimTargetName "$TARGET_NAME"

# Test Verilator simulation
echo "4. Testing Verilator simulation..."
hdlforge Verilator --project "$PROJECT_FILE" --step sim --SimTargetName "$TARGET_NAME"

echo "Migration test completed!"
```

## Conclusion

HDLForge v2.0 provides a cleaner, more consistent command-line interface. While the migration requires updating command syntax, the benefits include better error handling, reduced dependencies, and improved user experience.

**Key Takeaway**: Always use `hdlforge <command> --project <project_file.hdlforge.toml> [options]` format for all commands except `help` and `projects`.

---

*For more information, see the main [HDLForge Reference Guide](../README.md#hdlforge-reference-guide) in the main README.*
