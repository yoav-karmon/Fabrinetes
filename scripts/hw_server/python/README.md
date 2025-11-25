# Hardware Server Python Scripts

This directory contains Python scripts for interacting with Vivado hardware servers.

## Scripts

### `connect_and_read_dna.py`

Connects to a Vivado hardware server, refreshes the target, and reads the chip DNA value by communicating with Vivado TCL console via subprocess pipes.

#### Features

- Opens Vivado TCL console as a subprocess
- Sends TCL commands through stdin pipe
- Reads output from stdout in real-time
- Keeps Vivado console open during execution
- Automatically closes console when done

#### Usage

```bash
# Use default server (10.1.130.74)
python3 connect_and_read_dna.py

# Specify custom server IP
python3 connect_and_read_dna.py <server_ip>
```

#### Examples

```bash
# Connect to default server
python3 connect_and_read_dna.py

# Connect to custom server
python3 connect_and_read_dna.py 192.168.1.100
```

#### Requirements

- Python 3.6+
- Vivado installed and in PATH
- Network connectivity to hardware server
- FPGA device connected and powered on

#### How It Works

The script uses `subprocess.Popen` to start Vivado in TCL mode:
- `stdin=subprocess.PIPE`: Send TCL commands via pipe
- `stdout=subprocess.PIPE`: Read output from pipe
- Commands are sent line by line
- Output is read and parsed in real-time
- The console remains open until script completes

#### Output

The script will:
1. Connect to the hardware server
2. Discover available hardware targets
3. Open and refresh the selected target
4. Discover hardware devices
5. Read and display the chip DNA value

#### Error Handling

The script includes error handling for:
- Connection failures (network issues, server not running)
- Missing hardware targets (FPGA not connected)
- Missing hardware devices
- DNA read failures

#### Comparison with TCL Script

| Feature | TCL Script | Python Script |
|---------|-----------|---------------|
| Execution | Batch mode | Interactive TCL console |
| Communication | Direct TCL | Subprocess pipes |
| Output parsing | Native TCL | Regex parsing |
| Integration | Standalone | Can be imported as module |
| Error handling | TCL error handling | Python exception handling |

## Troubleshooting

### Vivado Not Found

- Verify Vivado is in PATH: `which vivado`
- Source Vivado settings: `source /path/to/Vivado/settings64.sh`

### Connection Failed

- Verify hardware server is running: `ps aux | grep hw_server`
- Check network connectivity: `ping <server_ip>`
- Verify firewall allows port 3121

### No Hardware Targets Found

- Ensure FPGA is connected via JTAG/USB
- Verify FPGA is powered on
- Check cable connection
- Try refreshing hardware manager in Vivado GUI

### Cannot Read Chip DNA

- Device may need to be opened/programmed first
- Verify device supports DNA register access
- Check if device is properly initialized


