# Fabrinetes Examples

This directory contains example projects demonstrating the Fabrinetes FPGA development workflow.

## Available Examples

### 32-bit Address Generator (`addr_32bit/`)
A complete example featuring:
- SystemVerilog RTL design
- Cocotb Python testbench
- HDLForge TOML configuration
- Vivado synthesis and implementation
- Comprehensive test scenarios

**Quick Start:**
```bash
cd examples/addr_32bit
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName basic_test
```

> **Note**: All HDLForge commands now require the `--project` parameter. The old format `hdlforge <project_file> <command>` is no longer supported.

## Example Structure

Each example follows a consistent structure:

```
example_name/
├── src/                    # RTL source files
├── tests/                  # Cocotb testbenches
├── constraints/            # Vivado constraint files
├── example_name.hdlforge.toml  # HDLForge project configuration
└── README.md              # Example-specific documentation
```

## Running Examples

All examples use the HDLForge build system and can be run with:

```bash
# Navigate to example directory
cd examples/example_name

# Run Verilator simulation
hdlforge Verilator --project example_name.hdlforge.toml --step sim --SimTargetName test_name

# Run Vivado synthesis
hdlforge vivado --project example_name.hdlforge.toml --step syn --run-flow main
```

## Contributing Examples

When adding new examples:

1. Follow the established directory structure
2. Include comprehensive testbenches
3. Provide clear documentation
4. Use proper HDLForge TOML configuration
5. Test both Verilator and Vivado flows

## Documentation

- [HDLForge Reference Guide](../README.md#hdlforge-reference-guide)
- [HDLForge v2.0 Migration Guide](../HDLForge_v2_Migration_Guide.md) - **Important**: Read this if upgrading from v1.x
- [Fabrinetes Main Documentation](../README.md)
- [Testing Guide](../testing_guide.md)
