# Hardware Server TCL Scripts

This directory contains TCL scripts for interacting with Vivado hardware servers.

## Script Structure

The scripts are organized into modular components:

- **`connect_and_read_dna.tcl`** - Main script (47 lines) - orchestrates the workflow
- **`hw_server_helpers.tcl`** - Helper functions for hardware server operations (71 lines)
- **`dna_helpers.tcl`** - Helper functions for DNA reading operations (149 lines)

## Scripts

### `connect_and_read_dna.tcl`

Main script that connects to a Vivado hardware server, refreshes the target, and reads the chip DNA value.

#### Usage

```bash
# Use default server (10.1.130.74) - normal mode
vivado -mode batch -source connect_and_read_dna.tcl

# Use default server (10.1.130.74) - quiet mode (suppress command echoing)
vivado -mode batch -notrace -source connect_and_read_dna.tcl

# Specify custom server IP - normal mode
vivado -mode batch -source connect_and_read_dna.tcl -tclargs <server_ip>

# Specify custom server IP - quiet mode
vivado -mode batch -notrace -source connect_and_read_dna.tcl -tclargs <server_ip>
```

#### Examples

```bash
# Connect to default server
vivado -mode batch -source connect_and_read_dna.tcl

# Connect to custom server
vivado -mode batch -source connect_and_read_dna.tcl -tclargs 192.168.1.100
```

#### Requirements

- Vivado hardware server running on the target machine
- Network connectivity to the hardware server
- FPGA device connected and powered on
- Hardware server listening on port 3121 (default)

#### Output

The script will:
1. Connect to the hardware server
2. Discover available hardware targets
3. Refresh the selected target
4. Discover hardware devices
5. Read and display the chip DNA value

#### Error Handling

The script includes error handling for:
- Connection failures (network issues, server not running)
- Missing hardware targets (FPGA not connected)
- Missing hardware devices
- DNA read failures (may require device to be opened first)

## Hardware Server Setup

To start a hardware server on the target machine:

```bash
hw_server
```

Or with custom port:

```bash
hw_server -s tcp::3121
```

## Troubleshooting

### Connection Failed

- Verify hardware server is running: `ps aux | grep hw_server`
- Check network connectivity: `ping <server_ip>`
- Verify firewall allows port 3121
- Check server logs for errors

### No Hardware Targets Found

- Ensure FPGA is connected via JTAG/USB
- Verify FPGA is powered on
- Check cable connection
- Try refreshing hardware manager in Vivado GUI

### Cannot Read Chip DNA

- Device may need to be opened first
- Verify device is properly initialized
- Check if device supports DNA register access

