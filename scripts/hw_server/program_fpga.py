#!/usr/bin/env python3
"""
Hardware Server FPGA Programmer (Main Executor)

This is the main entry point for programming the FPGA.
It can be called directly or imported as a module.

Usage:
    python3 program_fpga.py [server_ip] [bitstream_path] [probes_path]

Arguments:
    server_ip (optional): Hardware server IP address (default: 10.1.130.74)
    bitstream_path (required): Path to .bit or .vit file
    probes_path (required): Path to .ltx file
"""

import sys
import os

# Add the python directory to the path so we can import modules
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.join(script_dir, 'python')
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)

# Change to python directory to ensure proper module resolution
os.chdir(python_dir)

# Import and run the main function
from connect_and_program_fpga import main

if __name__ == "__main__":
    main()

