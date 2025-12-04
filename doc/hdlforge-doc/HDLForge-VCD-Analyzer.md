# HDLForge VCD Analyzer

## Overview

The VCD (Value Change Dump) analyzer is an HDLForge tool for debugging FPGA simulations by analyzing waveform data.

**VCD File Location**: `_verilator/<test_name>/dump.vcd` (generated after simulation)

## Quick Start

```bash
# Via hdlforge
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*clk*" --time 5000

# Direct Python (from fpga repo root)
python3 tools/vcd_analyzer.py --vcdfilename <vcd_file> [options]
```

## Basic Operations

### List Timestamps
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --timestamps
```

### Find Signals
```bash
# All signals
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names

# With wildcard
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*clk*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*state*"
```

### Get Signal Values
```bash
# At specific time
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal init_clk --time 5000

# Multiple timestamps
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal init_clk --time 5000 10000 15000

# All value changes
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal init_clk
```

### Signal Edges (Transitions)
```bash
# All edges after timestamp
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal init_clk --time 5000 --edge

# First N edges
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal init_clk --time 5000 --edge 5
```

### Count Values
```bash
# Show 10 values starting from timestamp
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal init_clk --time 5000 --count 10
```

## Output Format Options

### Radix
```bash
--radix hex    # Hexadecimal (0x00000004)
--radix int    # Integer (4)
--radix bin    # Binary (00000100)
```

### Verbose
```bash
--verbose      # Show all VCD data including var_id and signal definition
```

## Output Structure

```json
{
  "signal_name": {
    "time": "5000",
    "calc_value": {
      "hex": "0x00000004",
      "int": 4,
      "bin": "00000100",
      "raw_vcd": "4"
    },
    "width": 8
  }
}
```

## Common Debugging Scenarios

### Reset Sequence
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*rst*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*rst*" --time 10000 --edge
```

### Clock Domain
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*clk*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*clk*" --time 0 --edge 20
```

### State Machine
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*state*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*state*" --time 5000 --edge
```

### Packet Data
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*data*" --time 50000 --radix hex
```

## Key Features

### Last-Known Value
When querying timestamps where signal didn't change, returns last known value before that timestamp (VCD files only record changes).

### Closest Timestamp
When requested timestamp doesn't exist, finds closest available timestamp and reports it.

### Wildcard Matching
Uses Python `fnmatch`: `*` matches any sequence, `?` matches single character.

## Debugging Workflow

1. **Run simulation**: `hdlforge --tool Verilator --step sim --SimTargetName <test>`
2. **Find signals**: `--find_signal_names "*pattern*"`
3. **Analyze values**: `--signal "name" --time <timestamp> --count 20`
4. **Track transitions**: `--signal "name" --time <timestamp> --edge`

## Best Practices

1. **Start broad**: Use wildcards to find relevant signals first
2. **Narrow down**: Focus on specific signals once identified
3. **Use time ranges**: Query multiple timestamps to see evolution
4. **Check edges**: Use `--edge` to see when signals transition
5. **Use appropriate radix**: `hex` for multi-bit, `int` for counters

## Troubleshooting

### No Signal Found
- Check spelling (case-sensitive)
- Use wildcards to find similar signals
- Verify signal exists with `--find_signal_names`

### No Value at Timestamp
- VCD files only record value changes
- Use `--edge` to see when signal changed
- Check if timestamp is within simulation range

### Unexpected Values
- Verify signal width matches expectations
- Check for X (unknown) or Z (high-impedance)
- Use `--verbose` to see raw VCD data

