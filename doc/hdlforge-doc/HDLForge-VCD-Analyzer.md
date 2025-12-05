# HDLForge VCD Analyzer

## Overview

The VCD (Value Change Dump) analyzer is an HDLForge tool for debugging FPGA simulations by analyzing waveform data.

**VCD File Location**: `_verilator/<test_name>/dump.vcd` (generated after simulation)

## Quick Start

```bash
# Find signals
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*clk*"

# Show values (clock-aligned sampling)
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.clk" --value --count 10

# Show edges (actual value changes)
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.data" --edge --count 5
```

## Command Structure

```bash
hdlforge --tool vcd_analyzer --vcdfilename <file> [action] [options]
```

### Actions (choose one)

| Action | Description |
|--------|-------------|
| `--timestamps` | List all timestamps in VCD |
| `--find_signal_names [pattern]` | Find signals (supports wildcards) |
| `--signal <name> --value` | Show signal values at timestamps |
| `--signal <name> --edge` | Show signal value changes only |

### Signal Query Options

| Option | Default | Description |
|--------|---------|-------------|
| `--time <ps>` | `0` | Start timestamp (picoseconds) |
| `--count <n>` | all | Number of values/edges to show |
| `--radix hex/int/bin` | all | Output format |
| `--verbose` | off | Show full VCD details |
| `--no-clock` | off | Disable clock-aligned sampling |
| `--rebuild-index` | off | Force rebuild VCD index |

## Clock Analysis

The tool automatically analyzes VCD timestamps to detect the simulation clock:

```
[Clock Analysis]
  Timestamps uniformly spaced: 5000ps between edges
  Clock period: 10000ps (10.0ns)
  Frequency: 100.00MHz
  Using tick = 10000ps for value sampling
```

- **With clock (default)**: Samples at clock-aligned timestamps (skips falling edges)
- **With `--no-clock`**: Samples at every timestamp

## Value Mode vs Edge Mode

### `--value` Mode
Shows signal values at consecutive timestamps (including unchanged values):

```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.counter" --value --count 5
```
Output shows values at times 0, 10000, 20000, 30000, 40000 (clock-aligned).

### `--edge` Mode  
Shows only actual value changes (edges):

```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.counter" --edge --count 5
```
Output:
- Initial value at time 0
- Value at `--time` (if not 0)
- Next 5 actual value changes

## Examples

### Find Signals
```bash
# All signals
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names

# With wildcard
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*clk*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*state*"
```

### Signal Values
```bash
# 10 values starting from time 0 (clock-aligned)
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.data" --value --count 10

# Values starting from specific time
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.data" --value --time 50000 --count 10

# All timestamps (no clock alignment)
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.data" --value --count 10 --no-clock
```

### Signal Edges
```bash
# First 5 edges
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.state" --edge --count 5

# Edges after specific time
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.state" --edge --time 100000 --count 10
```

### Output Format
```bash
--radix hex    # Hexadecimal (0x00000004)
--radix int    # Integer (4)
--radix bin    # Binary (00000100)
```

## VCD Indexing

The tool automatically creates an index for fast queries:
- Index stored in `.dump.vcd.idx/` folder next to VCD file
- First query builds index (~2-5 seconds)
- Subsequent queries use cached index (~0.3 seconds)
- Index auto-invalidates when VCD file changes

Force rebuild:
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --rebuild-index --find_signal_names
```

## Output Structure

```json
{
  "signal_name": {
    "time": "5000",
    "calc_value": {
      "hex": "0x00000004",
      "int": 4,
      "bin": "00000100"
    },
    "width": 8,
    "note": {"status": "sampled value"}
  }
}
```

## Common Debugging Scenarios

### Reset Sequence
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*rst*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*rst*" --edge --count 10
```

### Clock Domain
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*clk*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "top.clk" --edge --count 20
```

### State Machine
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --find_signal_names "*state*"
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*state*" --edge --time 5000 --count 20
```

### Packet Data
```bash
hdlforge --tool vcd_analyzer --vcdfilename dump.vcd --signal "*data*" --value --time 50000 --count 20 --radix hex
```

## Debugging Workflow

1. **Run simulation**: `hdlforge --tool Verilator --step sim --SimTargetName <test>`
2. **Find signals**: `--find_signal_names "*pattern*"`
3. **Check edges**: `--signal "name" --edge --count 20`
4. **Analyze values**: `--signal "name" --value --time <timestamp> --count 20`

## Troubleshooting

### No Signal Found
- Check spelling (case-sensitive)
- Use wildcards to find similar signals
- Verify signal exists with `--find_signal_names`

### Slow First Query
- Normal - building VCD index
- Subsequent queries will be fast (~0.3s)
- Use `--rebuild-index` if index seems stale

### Unexpected Sampling
- Default uses clock-aligned sampling
- Use `--no-clock` to see all timestamps
- Check clock analysis message for deduced period

### No Value at Timestamp
- VCD files only record value changes
- Use `--edge` to see when signal changed
- Check if timestamp is within simulation range
