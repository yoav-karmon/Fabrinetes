"""FPGA Programming Helper Functions"""

import os
import re
import sys
from typing import Optional

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


def verify_bitstream_file(bitstream_path: str) -> None:
    """Verify bitstream file exists."""
    if not bitstream_path:
        raise ValueError("Bitstream path not provided")
    
    if not os.path.exists(bitstream_path):
        raise FileNotFoundError(f"Bitstream file not found: {bitstream_path}")
    
    if not os.path.isfile(bitstream_path):
        raise ValueError(f"Path is not a file: {bitstream_path}")


def verify_probes_file(probes_path: str) -> None:
    """Verify probes file exists."""
    if not probes_path:
        return  # Probes file is optional
    
    if not os.path.exists(probes_path):
        raise FileNotFoundError(f"Probes file not found: {probes_path}")
    
    if not os.path.isfile(probes_path):
        raise ValueError(f"Path is not a file: {probes_path}")


def set_bitstream_file(console: VivadoTCLConsole, hw_device: str, bitstream_path: str) -> None:
    """Set bitstream file property on hardware device."""
    # Convert path to absolute and use forward slashes for TCL
    abs_path = os.path.abspath(bitstream_path).replace('\\', '/')
    print(f"Setting bitstream file: {abs_path}")
    
    cmd = f'set_property PROGRAM.FILE {{{abs_path}}} ${hw_device}'
    output = send_tcl_command(console, cmd, timeout=5)
    
    if "ERROR" in output:
        raise RuntimeError(f"Failed to set bitstream file: {output}")


def set_probes_file(console: VivadoTCLConsole, hw_device: str, probes_path: str) -> None:
    """Set probes file property on hardware device."""
    if not probes_path:
        return  # Probes file is optional
    
    # Convert path to absolute and use forward slashes for TCL
    abs_path = os.path.abspath(probes_path).replace('\\', '/')
    print(f"Setting probes file: {abs_path}")
    
    cmd = f'set_property PROBES.FILE {{{abs_path}}} ${hw_device}'
    output = send_tcl_command(console, cmd, timeout=5)
    
    if "ERROR" in output:
        raise RuntimeError(f"Failed to set probes file: {output}")


def program_fpga_device(console: VivadoTCLConsole, hw_device: str, bitstream_path: str, probes_path: Optional[str] = None) -> None:
    """Program FPGA device with bitstream and probes file."""
    print("=" * 50)
    print("Programming FPGA Device")
    print("=" * 50)
    
    # Verify files exist
    verify_bitstream_file(bitstream_path)
    if probes_path:
        verify_probes_file(probes_path)
    
    # Set bitstream file
    set_bitstream_file(console, hw_device, bitstream_path)
    
    # Set probes file if provided
    if probes_path:
        set_probes_file(console, hw_device, probes_path)
    
    # Program the device
    print("Programming device...")
    output = send_tcl_command(console, f"program_hw_devices ${hw_device}", timeout=60)
    
    # Check for errors
    if "ERROR" in output:
        raise RuntimeError(f"Failed to program device: {output}")
    
    # Check for success indicators
    if "program_hw_devices: Time" in output or "Device programmed successfully" in output:
        print("Device programmed successfully")
    else:
        # Look for any error patterns
        error_match = re.search(r'ERROR[:\s]+(.+)', output, re.IGNORECASE)
        if error_match:
            raise RuntimeError(f"Programming failed: {error_match.group(1)}")
    
    print("=" * 50)

