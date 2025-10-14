# 32-bit Address Generator Example

This example demonstrates a complete FPGA development workflow using Fabrinetes, featuring:

- **SystemVerilog RTL**: A 32-bit address generator module
- **Cocotb Testbench**: Comprehensive Python-based verification
- **HDLForge Configuration**: TOML-based project management
- **Vivado Integration**: Complete synthesis and implementation flow

## Project Structure

```
addr_32bit/
├── src/
│   └── addr_32bit.sv          # SystemVerilog RTL source
├── tests/
│   └── test_addr_32bit.py    # Cocotb testbench
├── constraints/
│   └── addr_32bit.xdc        # Vivado constraints
└── addr_32bit.hdlforge.toml  # HDLForge project configuration
```

## Features

### RTL Module (`addr_32bit.sv`)
- 32-bit address output with configurable increment
- Enable/disable control
- Reset functionality
- Clock domain crossing safe
- Built-in assertions for verification

### Testbench (`test_addr_32bit.py`)
- Basic functionality test
- Reset behavior verification
- Enable/disable testing
- Address increment validation
- Edge case testing
- Random value testing

### HDLForge Configuration
- Multiple simulation targets for different test scenarios
- Verilator integration with tracing and coverage
- Vivado synthesis and implementation setup
- Proper source file organization

## Usage

### Running Verilator Simulation

```bash
# Navigate to project directory
cd examples/addr_32bit

# Build and run basic test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step build --SimTargetName basic_test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName basic_test

# Run other test scenarios
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName reset_test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName enable_test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName increment_test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName edge_cases_test
hdlforge Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName random_test
```

### Running Vivado Synthesis

```bash
# Create new Vivado project
hdlforge vivado --project addr_32bit.hdlforge.toml --step new --clean

# Run synthesis
hdlforge vivado --project addr_32bit.hdlforge.toml --step syn --run-flow main

# Run implementation
hdlforge vivado --project addr_32bit.hdlforge.toml --step impl --run-flow main

# Generate bitstream
hdlforge vivado --project addr_32bit.hdlforge.toml --step bit --run-flow main
```

### Viewing Simulation Results

After running Verilator simulation, you can view the VCD waveform:

```bash
gtkwave _verilator/basic_test/dump.vcd
```

## Test Scenarios

1. **Basic Functionality**: Tests address generation with default increment
2. **Reset Behavior**: Verifies proper reset and restart functionality
3. **Enable/Disable**: Tests enable/disable control and address holding
4. **Address Increment**: Tests various increment values
5. **Edge Cases**: Tests zero increment and maximum increment scenarios
6. **Random Values**: Tests with random increment values for robustness

## Configuration Options

The module supports the following parameters:
- `ADDR_WIDTH`: Address width (default: 32)
- `INCREMENT`: Default increment value (default: 1)

The testbench can be configured with different increment values and test scenarios through the HDLForge TOML configuration.

## Expected Results

All tests should pass with the following expected behaviors:
- Address starts at 0 after reset
- Address increments by specified value on each clock cycle when enabled
- Address holds current value when disabled
- Valid signal follows enable signal
- Reset properly clears address and valid signal

This example serves as a template for more complex FPGA designs using the Fabrinetes workflow.
