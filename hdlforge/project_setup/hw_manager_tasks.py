#!/usr/bin/env python
"""
Hardware Manager - FPGA Hardware Operations Tool

Manages FPGA hardware operations such as programming bitstreams, reading chip DNA,
and reading ILA values via hardware server.
"""

import subprocess
import sys
import os
from pathlib import Path


def _get_tcl_script(script_name: str) -> Path:
    """Get path to TCL script in hw_server/tcl directory."""
    script_dir = Path(__file__).parent
    fabrinetes_root = script_dir.parent.parent
    tcl_script = fabrinetes_root / "scripts" / "hw_server" / "tcl" / script_name
    if not tcl_script.exists():
        print(f"[!x!] TCL script not found: {tcl_script}")
        sys.exit(1)
    return tcl_script


def _run_vivado_tcl(tcl_script: Path, args: list, verbose: bool = False):
    """Run Vivado with TCL script."""
    vivado_cmd = [
        "vivado",
        "-mode", "batch",
        "-notrace",
        "-source", str(tcl_script),
        "-tclargs"
    ] + args
    
    if verbose:
        print(f"[i] Executing: {' '.join(vivado_cmd)}")
    
    try:
        result = subprocess.run(vivado_cmd, check=True, capture_output=not verbose)
        if not verbose and result.stdout:
            print(result.stdout.decode())
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!x!] Command failed")
        if e.stderr:
            print(e.stderr.decode())
        sys.exit(1)
    except FileNotFoundError:
        print("[!x!] vivado not found. Please ensure Vivado is installed and in PATH")
        sys.exit(1)


def hw_manager(c, cmd: str, server_ip: str = None, bitstream_path: str = None, probes_path: str = None, verbose: bool = False):
    """
    Hardware manager for FPGA operations.
    
    Args:
        c: Invoke context
        cmd: Command to execute ('program', 'read_dna', or 'read_ila')
        server_ip: Hardware server IP address (default: 10.1.130.74)
        bitstream_path: Path to bitstream file (.bit file)
        probes_path: Optional path to probes file (.ltx file)
        verbose: Enable verbose output
    """
    # Default server IP if not provided
    if not server_ip:
        server_ip = "10.1.130.74"
    
    if cmd == "program":
        if not bitstream_path:
            print("[!x!] Bitstream path is required for program command")
            print("[i] Usage: hdlforge --tool hw_manager --cmd program --bitstream <path> [--server_ip <ip>] [--probes <path>]")
            sys.exit(1)
        
        # Verify bitstream file exists
        bitstream = Path(bitstream_path)
        if not bitstream.exists():
            print(f"[!x!] Bitstream file not found: {bitstream_path}")
            sys.exit(1)
        
        # Verify probes file exists if provided
        if probes_path:
            probes = Path(probes_path)
            if not probes.exists():
                print(f"[!x!] Probes file not found: {probes_path}")
                sys.exit(1)
        
        tcl_script = _get_tcl_script("connect_and_program_fpga.tcl")
        
        # Build arguments
        args = [server_ip, str(bitstream.absolute())]
        if probes_path:
            args.append(str(Path(probes_path).absolute()))
        
        if verbose:
            print(f"[i] Server IP: {server_ip}")
            print(f"[i] Bitstream: {bitstream.absolute()}")
            if probes_path:
                print(f"[i] Probes: {Path(probes_path).absolute()}")
        
        _run_vivado_tcl(tcl_script, args, verbose)
        print("[✓] FPGA programmed successfully")
        
    elif cmd == "read_dna":
        tcl_script = _get_tcl_script("connect_and_read_dna.tcl")
        
        if verbose:
            print(f"[i] Server IP: {server_ip}")
        
        _run_vivado_tcl(tcl_script, [server_ip], verbose)
        print("[✓] Chip DNA read successfully")
        
    elif cmd == "read_ila":
        if not bitstream_path or not probes_path:
            print("[!x!] Both bitstream and probes paths are required for read_ila command")
            print("[i] Usage: hdlforge --tool hw_manager --cmd read_ila --bitstream <path> --probes <path> [--server_ip <ip>]")
            sys.exit(1)
        
        # Verify files exist
        bitstream = Path(bitstream_path)
        probes = Path(probes_path)
        if not bitstream.exists():
            print(f"[!x!] Bitstream file not found: {bitstream_path}")
            sys.exit(1)
        if not probes.exists():
            print(f"[!x!] Probes file not found: {probes_path}")
            sys.exit(1)
        
        tcl_script = _get_tcl_script("read_ila.tcl")
        
        args = [server_ip, str(bitstream.absolute()), str(probes.absolute())]
        
        if verbose:
            print(f"[i] Server IP: {server_ip}")
            print(f"[i] Bitstream: {bitstream.absolute()}")
            print(f"[i] Probes: {probes.absolute()}")
        
        _run_vivado_tcl(tcl_script, args, verbose)
        print("[✓] ILA values read successfully")
        
    else:
        print(f"[!x!] Unknown command: {cmd}")
        print("[i] Available commands: program, read_dna, read_ila")
        sys.exit(1)


def help_hw_manager():
    """
    Show detailed help for Hardware Manager tool
    """
    print("=" * 80)
    print("HDLFORGE HW_MANAGER - Hardware Manager")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Hardware manager for FPGA operations via hardware server:")
    print("    - Program FPGA with bitstream files")
    print("    - Read chip DNA (device identification)")
    print("    - Read ILA (Integrated Logic Analyzer) values")
    print()
    print("USAGE:")
    print("  hdlforge --tool hw_manager --cmd <command> [options]")
    print()
    print("COMMANDS:")
    print("  program                             Program FPGA with bitstream file")
    print("  read_dna                            Read chip DNA from FPGA")
    print("  read_ila                            Read ILA probe values from FPGA")
    print()
    print("ARGUMENTS:")
    print("    --cmd <COMMAND>                    Command to execute: program, read_dna, or read_ila (required)")
    print("    --server_ip <IP>                  Hardware server IP address (default: 10.1.130.74)")
    print("    --bitstream <PATH>                Path to bitstream file (.bit file)")
    print("    --probes <PATH>                   Path to probes file (.ltx file)")
    print("    --verbose                          Enable verbose output")
    print()
    print("EXAMPLES:")
    print("  # Program FPGA")
    print("  hdlforge --tool hw_manager --cmd program --bitstream design.bit")
    print("  hdlforge --tool hw_manager --cmd program --bitstream design.bit --probes design.ltx")
    print()
    print("  # Read chip DNA")
    print("  hdlforge --tool hw_manager --cmd read_dna")
    print()
    print("  # Read ILA values")
    print("  hdlforge --tool hw_manager --cmd read_ila --bitstream design.bit --probes design.ltx")
    print()
    print("NOTES:")
    print("  • Requires Vivado to be installed and in PATH")
    print("  • Hardware server must be running on the specified IP address")
    print("  • Default hardware server port is 3121")
    print("  • For read_ila, both bitstream and probes files are required")
    print()
    print("=" * 80)

