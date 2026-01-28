# HDLForge VCD Analyzer

## Overview

The VCD (Value Change Dump) analyzer is an HDLForge tool for debugging FPGA simulations by analyzing waveform data using a module-based approach. The tool focuses on analyzing signals within specific modules rather than individual signal queries.

**VCD File Location**: `_verilator/<test_name>/dump.vcd` (generated after simulation)

## Quick Start

```bash
# List all modules in the design
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list

# Get pin values for a specific module
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_pins 'top.config_interface_inst.arp_server_inst'

# Get all signal values for a specific module
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_all 'top.config_interface_inst.arp_server_inst'
```

## Command Structure

```bash
hdlforge --tool vcd_analyzer --vcdfilename <file> [action] [options]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--vcdfilename <FILE>` | VCD file to analyze (required) |

### Actions (choose one)

| Action | Description |
|--------|-------------|
| `--get_modules_list` | List all modules in the design hierarchy |
| `--get_values_pins <PATH>` | Get value changes for pin signals only (signals ending with `_i` or `_o`) |
| `--get_values_all <PATH>` | Get value changes for all signals in the module (including internal signals) |

### Options

| Option | Description |
|--------|-------------|
| `--human` | Human-readable output format with aligned columns (for use with `--get_values_pins` or `--get_values_all`) |

## Module-Based Analysis

The VCD analyzer uses a module-centric approach, focusing on analyzing signals within specific module instances rather than individual signal queries.

### Module Hierarchy

Modules are identified by their hierarchical path in the design:
- `top` - Top-level module
- `top.config_interface_inst` - Instance under top
- `top.config_interface_inst.arp_server_inst` - Nested instance

### Pin Signals vs All Signals

- **Pin Signals** (`--get_values_pins`): Only signals that are module ports (ending with `_i` for inputs or `_o` for outputs)
- **All Signals** (`--get_values_all`): All signals within the module, including internal state and intermediate signals

## Examples

### List All Modules

```bash
# List all modules in the design
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list
```

Output:
```
constants_pkg
top
top.config_block_inst
top.config_interface_inst
top.config_interface_inst.arp_server_inst
top.config_interface_inst.arp_server_inst.arp_exception_handler_inst
...
```

### Get Pin Values

```bash
# Get pin values for a module (inputs/outputs only)
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_pins 'top.config_interface_inst.arp_server_inst'
```

Output format:
```
rst_async_i[0] edges in ns:0x1@0,0x0@290
packed_mac_address_i[0][7:0] edges in ns:0x00@0,0x34@1490
mac_data_stream_i.sop[0] edges in ns:0x0@0,0x1@2720,0x0@2750
arp_response_fifo_wr_en_o[0] edges in ns:0x0@0,0x1@2940,0x0@3050
...
```

### Get All Signal Values

```bash
# Get all signal values for a module (including internal signals)
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_all 'top.config_interface_inst.arp_server_inst'
```

This includes internal signals like:
- `state[4:0]` - Internal state machine
- `checksum_accum[31:0]` - Internal calculation registers
- `eth_buffer.*` - Internal buffer structures

### Human-Readable Format

```bash
# Use --human for aligned, readable output
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_pins 'top.config_interface_inst.arp_server_inst' --human
```

Output with aligned columns:
```
rst_async_i[0]                                       edges in ns:0x1@0,0x0@290
packed_mac_address_i[0][7:0]                         edges in ns:0x00@0,0x34@1490
mac_data_stream_i.sop[0]                             edges in ns:0x0@0,0x1@2720
...
```

## Output Format

The output uses a compressed format showing signal value changes:

```
signal_name[range] edges in ns:value@time,value@time,...
```

Where:
- `signal_name[range]` - Signal name with bit range
- `edges in ns:` - Indicates value changes are shown
- `value@time` - Value at specific time (in nanoseconds)
- Multiple `value@time` pairs show all value changes

Example:
```
state_o[3:0] edges in ns:0x0@0,0x1@2750,0x2@2910,0x3@2920,0x4@2930,0x0@3040
```

This shows:
- Initial value: `0x0` at time `0ns`
- Changed to `0x1` at time `2750ns`
- Changed to `0x2` at time `2910ns`
- etc.

## VCD Indexing

The tool automatically creates an index for fast queries:
- Index stored in `.<vcd_filename>.idx/` folder next to VCD file
- First query builds index (~2-5 seconds)
- Subsequent queries use cached index (~0.3 seconds)
- Index auto-invalidates when VCD file changes

## Common Debugging Scenarios

### Finding a Module

```bash
# First, list all modules to find the one you need
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list | grep arp
```

### Analyzing Module Interface

```bash
# Check all pin signals (interface) of a module
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_pins 'top.config_interface_inst.arp_server_inst' --human
```

### Analyzing Internal Module Behavior

```bash
# Check all signals including internal state
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_all 'top.config_interface_inst.arp_server_inst' --human
```

### Filtering Output

```bash
# Use grep to filter specific signals
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_all 'top.config_interface_inst.arp_server_inst' | grep state
```

## Debugging Workflow

1. **Run simulation**: `hdlforge --tool Verilator --step sim --SimTargetName <test>`
2. **List modules**: `hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list`
3. **Find target module**: Pipe to `grep` to find modules of interest
4. **Analyze pins**: Use `--get_values_pins` to see module interface behavior
5. **Analyze internals**: Use `--get_values_all` to see internal state and signals
6. **Filter results**: Use `grep` to focus on specific signals

## Troubleshooting

### Module Not Found

- Check module path spelling (case-sensitive)
- Use `--get_modules_list` to see available modules
- Ensure module path matches hierarchy (e.g., `top.instance_inst`)

### No Signals Found

- Module may not have any signals (empty or only sub-modules)
- Try using `--get_values_all` instead of `--get_values_pins` to see internal signals
- Check that the module path is correct

### Slow First Query

- Normal - building VCD index
- Subsequent queries will be fast (~0.3s)
- Index is cached in `.<vcd_filename>.idx/` directory

### Shell Expansion Issues

If you see errors about unrecognized arguments when using wildcards:

```bash
# ❌ Wrong - shell expands *arp* to filenames
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list *arp*

# ✅ Correct - use grep to filter
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list | grep arp
```

The `--get_modules_list` flag does not accept arguments. Use `grep` to filter the output instead.

## Finding Signals

Use module-based commands with `grep` to find signals by pattern:

```bash
# List all modules
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list

# Filter modules by pattern
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_modules_list | grep state

# Get signal values and filter
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --get_values_all 'top.module_inst' --human | grep state
```

The new API provides:
- Better organization by module hierarchy
- Faster analysis of related signals
- Compressed output format for easier scanning
- Focus on module-level debugging
