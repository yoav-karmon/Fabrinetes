#!/usr/bin/env python3
"""
Hardware Server Connection and FPGA Programmer (Python)

This script connects to a Vivado hardware server, refreshes the target,
and programs the FPGA with bitstream and probes files by communicating 
with Vivado TCL console.

Usage:
    python3 connect_and_program_fpga.py [server_ip] [bitstream_path] [probes_path]

Arguments:
    server_ip (optional): Hardware server IP address (default: 10.1.130.74)
    bitstream_path (optional): Path to .bit or .vit file (default: ~/repo/fpga/fpga_projects/phy10gbaser/_vivado/phy10gbaser/phy10gbaser.runs/impl_1/top.bit)
    probes_path (optional): Path to .ltx file (default: ~/repo/fpga/fpga_projects/phy10gbaser/_vivado/phy10gbaser/phy10gbaser.runs/impl_1/top.ltx)
"""

import sys
import os

# Handle both direct execution and module import
if __name__ == "__main__" or not __package__:
    # Running as script directly, use absolute imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from connect_and_read_dna import VivadoTCLConsole
    from hw_server_helpers import init_hw_server
    from fpga_programming_helpers import program_fpga_device
else:
    # Running as module, use relative imports
    from .connect_and_read_dna import VivadoTCLConsole
    from .hw_server_helpers import init_hw_server
    from .fpga_programming_helpers import program_fpga_device


def main():
    """Main entry point - matches TCL script structure exactly."""
    
    # Parse arguments
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "10.1.130.74"
    
    # Set default paths
    default_bitstream = os.path.expanduser(
        "~/repo/fpga/fpga_projects/phy10gbaser/_vivado/phy10gbaser/phy10gbaser.runs/impl_1/top.bit"
    )
    default_probes = os.path.expanduser(
        "~/repo/fpga/fpga_projects/phy10gbaser/_vivado/phy10gbaser/phy10gbaser.runs/impl_1/top.ltx"
    )
    
    bitstream_path = sys.argv[2] if len(sys.argv) > 2 else default_bitstream
    probes_path = sys.argv[3] if len(sys.argv) > 3 else default_probes
    
    # Expand user paths
    bitstream_path = os.path.expanduser(bitstream_path)
    probes_path = os.path.expanduser(probes_path)
    
    print("=" * 50)
    print("Hardware Server FPGA Programming Script")
    print("=" * 50)
    print(f"Server IP: {server_ip}")
    print(f"Bitstream: {bitstream_path}")
    print(f"Probes: {probes_path}")
    print()
    
    console = VivadoTCLConsole()
    try:
        if not console.start():
            sys.exit(1)
        
        # Initialize hardware server connection
        hw_device = init_hw_server(console, server_ip)
        
        # Program the FPGA
        program_fpga_device(console, hw_device, bitstream_path, probes_path)
        
        print()
        print("Script completed successfully")
        
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        console.close()


if __name__ == "__main__":
    main()

