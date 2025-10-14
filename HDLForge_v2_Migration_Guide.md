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
hdlforge addr_32bit.hdlforge.toml Verilator --step sim --SimTargetName basic_test
hdlforge addr_32bit.hdlforge.toml Verilator --step build --SimTargetName basic_test --clean
```

**After (v2.0):**
```bash
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName basic_test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step build --SimTargetName basic_test --clean
```

### Vivado Commands

**Before (v1.x):**
```bash
hdlforge addr_32bit.hdlforge.toml vivado --step new --clean
hdlforge addr_32bit.hdlforge.toml vivado --step syn --run-flow main
```

**After (v2.0):**
```bash
hdlforge vivado --project addr_32bit.hdlforge.toml --step new --clean
hdlforge vivado --project addr_32bit.hdlforge.toml --step syn --run-flow main
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
$ hdlforge addr_32bit.hdlforge.toml Verilator --step sim
❌ --project argument is required
Usage: hdlforge <command> --project <project_file> [options]
Example: hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName basic_test
```

## Complete Command Reference

### Verilator Commands
```bash
# Build (compile SystemVerilog to C++)
hdlforge Verilator --project <project_file.hdlforge.toml> --step build --SimTargetName <target_name> [--clean] [--extra-env DEBUG=1] [--flags <flags>]

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

PROJECT_FILE="addr_32bit.hdlforge.toml"

echo "Testing HDLForge v2.0 commands..."

# Test help command
echo "1. Testing help command..."
hdlforge help

# Test projects command
echo "2. Testing projects command..."
hdlforge projects

# Test Verilator build
echo "3. Testing Verilator build..."
hdlforge Verilator --project "$PROJECT_FILE" --step build --SimTargetName basic_test

# Test Verilator simulation
echo "4. Testing Verilator simulation..."
hdlforge Verilator --project "$PROJECT_FILE" --step sim --SimTargetName basic_test

echo "Migration test completed!"
```

## Conclusion

HDLForge v2.0 provides a cleaner, more consistent command-line interface. While the migration requires updating command syntax, the benefits include better error handling, reduced dependencies, and improved user experience.

**Key Takeaway**: Always use `hdlforge <command> --project <project_file.hdlforge.toml> [options]` format for all commands except `help` and `projects`.

---

*For more information, see the main [HDLForge Reference Guide](../README.md#hdlforge-reference-guide) in the main README.*
