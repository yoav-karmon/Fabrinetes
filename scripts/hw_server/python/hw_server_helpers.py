"""Hardware Server Helper Functions"""

import re
import sys
import os
from typing import Optional, Tuple, List

# Handle both direct execution and module import
if __name__ == "__main__" or not __package__:
    # Running as script directly, use absolute imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from connect_and_read_dna import VivadoTCLConsole
    from tcl_helpers import send_tcl_command
else:
    # Running as module, use relative imports
    from .connect_and_read_dna import VivadoTCLConsole
    from .tcl_helpers import send_tcl_command


def connect_to_hw_server(console: VivadoTCLConsole, server_ip: str) -> None:
    """Connect to hardware server (exits on failure)."""
    hw_server_url = f"{server_ip}:3121"
    print(f"Connecting to hardware server at {hw_server_url}...")
    output = send_tcl_command(console, f"connect_hw_server -url {hw_server_url}", timeout=5)
    if "ERROR" in output:
        print(f"ERROR: Failed to connect to hardware server: {output}")
        print(f"Please ensure hardware server is running at {server_ip}")
        raise SystemExit(1)
    print("Successfully connected to hardware server")


def discover_and_open_target(console: VivadoTCLConsole) -> None:
    """Discover and open hardware target (exits on failure)."""
    print("Discovering hardware targets...")
    send_tcl_command(console, "set hw_targets [get_hw_targets]", timeout=2)
    output = send_tcl_command(console, r"puts [llength $hw_targets]", timeout=1)
    
    count_match = re.search(r'(\d+)', output)
    target_count = int(count_match.group(1)) if count_match else 0
    
    if target_count == 0:
        print("ERROR: No hardware targets found")
        print("Please ensure FPGA is connected and powered on")
        raise SystemExit(1)
    
    print(f"Found {target_count} hardware target(s):")
    output = send_tcl_command(console, r"foreach target $hw_targets { puts [get_property NAME $target] }", timeout=2)
    targets = []
    for line in output.split('\n'):
        line = line.strip()
        if line and 'xilinx_tcf' in line and not any(line.startswith(x) for x in ['%', 'vivado', 'INFO', 'WARNING']):
            targets.append(line)
            print(f"  - {line}")
    
    hw_target_name = targets[0] if targets else ""
    print(f"Using target: {hw_target_name}")
    send_tcl_command(console, r"set hw_target [lindex $hw_targets 0]; current_hw_target $hw_target", timeout=2)
    
    print("Opening hardware target...")
    output = send_tcl_command(console, r"open_hw_target $hw_target", timeout=3)
    if "ERROR" in output:
        print(f"ERROR: Failed to open hardware target: {output}")
        raise SystemExit(1)
    
    print("Refreshing hardware target...")
    send_tcl_command(console, "refresh_hw_target", timeout=3)
    print("Hardware target ready")


def discover_and_select_device(console: VivadoTCLConsole) -> str:
    """Discover and select hardware device (exits on failure, returns device name)."""
    print("Discovering hardware devices...")
    send_tcl_command(console, r"set hw_devices [get_hw_devices]", timeout=2)
    output = send_tcl_command(console, r"puts [llength $hw_devices]", timeout=1)
    
    device_count_match = re.search(r'(\d+)', output)
    device_count = int(device_count_match.group(1)) if device_count_match else 0
    
    if device_count == 0:
        print("ERROR: No hardware devices found on target")
        raise SystemExit(1)
    
    print(f"Found {device_count} hardware device(s):")
    cmd = r'foreach device $hw_devices { set device_name [get_property NAME $device]; if { [catch {set device_type [get_property TYPE $device]} result] } { set device_type "unknown" }; puts "$device_name ($device_type)" }'
    output = send_tcl_command(console, cmd, timeout=2)
    
    device_info = []
    for line in output.split('\n'):
        line = line.strip()
        match = re.match(r'^([^(]+)\s*\(([^)]+)\)', line)
        if match:
            device_name = match.group(1).strip()
            device_type = match.group(2).strip()
            device_info.append((device_name, device_type))
    
    for device_name, device_type in device_info:
        print(f"  - {device_name} ({device_type})")
    
    hw_device_name = device_info[0][0]
    print(f"Using device: {hw_device_name}")
    send_tcl_command(console, r"set hw_device [lindex $hw_devices 0]; current_hw_device $hw_device", timeout=2)
    return hw_device_name


def init_hw_server(console: VivadoTCLConsole, server_ip: str) -> str:
    """Initialize hardware server connection and discover device (exits on failure, returns device name)."""
    send_tcl_command(console, "open_hw_manager", timeout=2)
    connect_to_hw_server(console, server_ip)
    print()
    
    discover_and_open_target(console)
    print()
    
    hw_device = discover_and_select_device(console)
    print()
    
    return hw_device

