#!/usr/bin/env python
"""
tshark Wrapper - Wrapper for tshark commands with convenience options.

Simplifies common tshark operations with preset checksum verification and frame selection.
"""

import subprocess
import sys
import os
import shlex
from pathlib import Path

import hdlforge_command_tree


def _has_unique_project_file(directory: Path) -> bool:
    project_files = list(directory.glob("*.hdlforge.json")) + list(
        directory.glob("*.hdlforge.toml")
    )
    return len(project_files) == 1


def tshark_wrapper(c, pcap_file: str, output_format: str = 'to_plain_text',
                   frame_number: int = None, frame_start: int = None, frame_end: int = None,
                   frame_list: list = None, count: int = None, skip: int = None,
                   tshark_args_append: str = None, disable_heuristics: bool = False,
                   disable_protocols: str = None, verbose: bool = False):
    """
    Wrapper for tshark with convenience options and checksum verification.
    
    Args:
        c: Invoke context
        pcap_file: Path to the PCAP file to analyze
        output_format: Output format (currently only 'to_plain_text' supported)
        frame_number: Single frame number to display
        frame_start: Start frame number for range (requires frame_end)
        frame_end: End frame number for range (requires frame_start)
        frame_list: List of specific frame numbers to display
        count: Number of packets to display (use with skip for pagination)
        skip: Number of packets to skip before displaying (use with count)
        tshark_args_append: Additional tshark arguments to append (raw string)
        disable_heuristics: If True, disable UDP heuristic protocol dissectors
        disable_protocols: Comma-separated list of protocols to disable (e.g., "mndp,ssdp")
        verbose: Enable verbose output
    """
    # Verify pcap file exists
    pcap_path = Path(pcap_file)
    if not pcap_path.exists():
        print(f"[!x!] PCAP file not found: {pcap_file}")
        sys.exit(1)
    
    # Check tshark is available
    try:
        subprocess.run(['tshark', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[!x!] tshark not found. Install wireshark-cli or tshark:")
        print("    sudo apt-get install tshark")
        sys.exit(1)
    
    # Build tshark command
    cmd = ['tshark', '-r', str(pcap_path)]
    
    # Add checksum verification options
    checksum_opts = [
        '-o', 'eth.check_fcs:TRUE',
        '-o', 'ip.check_checksum:TRUE',
        '-o', 'tcp.check_checksum:TRUE',
        '-o', 'udp.check_checksum:TRUE',
    ]
    
    # Build display filter based on frame selection
    display_filter = None
    
    if frame_number is not None:
        display_filter = f"frame.number == {frame_number}"
    elif frame_start is not None and frame_end is not None:
        display_filter = f"frame.number >= {frame_start} && frame.number <= {frame_end}"
    elif frame_list:
        conditions = [f"frame.number == {n}" for n in frame_list]
        display_filter = " || ".join(conditions)
    elif skip is not None and count is not None:
        display_filter = f"frame.number > {skip}"
        cmd.extend(['-c', str(count)])
    elif count is not None:
        cmd.extend(['-c', str(count)])
    
    # Add display filter if set
    if display_filter:
        cmd.extend(['-Y', display_filter])
    
    # Output format options
    if output_format == 'to_plain_text':
        cmd.extend(['-V', '-x'])  # Verbose with hex dump
    
    # Add checksum options
    cmd.extend(checksum_opts)
    
    # Load FPGA config protocol dissector (if available)
    # Look in project-relative locations (cwd, PCAP location, or the HDLForge project folder).
    # Note: This is project-specific, not part of HDLForge itself
    dissector_paths = []
    
    # Method 1: Check the selected HDLForge project folder first (highest priority).
    root_folder = os.environ.get("HDLFORGE_PROJECT_FOLDER")
    if root_folder:
        dissector_paths.append(Path(root_folder) / "sources" / "PY" / "TEST_UTILS" / "fpga_config_protocol.lua")
    
    # Method 2: Find project root by looking for .hdlforge.json files (walk up from PCAP or CWD)
    project_root = None
    for search_start in [pcap_path.parent, Path.cwd()]:
        for parent in [search_start] + list(search_start.parents)[:6]:  # Check up to 6 levels up
            if _has_unique_project_file(parent):
                project_root = parent
                break
        if project_root:
            break
    
    if project_root:
        dissector_paths.append(project_root / "sources" / "PY" / "TEST_UTILS" / "fpga_config_protocol.lua")
    
    # Method 3: Check relative to PCAP file location
    pcap_parent = pcap_path.parent
    for parent in [pcap_parent] + list(pcap_parent.parents)[:5]:  # Check up to 5 levels up
        test_path = parent / "sources" / "PY" / "TEST_UTILS" / "fpga_config_protocol.lua"
        if test_path.exists():
            dissector_paths.append(test_path)
            break
    
    # Method 4: Check relative to current working directory
    dissector_paths.extend([
        Path.cwd() / "sources" / "PY" / "TEST_UTILS" / "fpga_config_protocol.lua",
        Path.cwd() / "TEST_UTILS" / "fpga_config_protocol.lua",
    ])
    
    # Try each path until we find one that exists
    # Use absolute paths to avoid issues with working directory changes
    dissector_loaded = False
    for dissector_path in dissector_paths:
        try:
            abs_path = dissector_path.resolve() if not dissector_path.is_absolute() else dissector_path
            if abs_path.exists():
                cmd.extend(['-X', f'lua_script:{abs_path}'])
                dissector_loaded = True
                if verbose:
                    print(f"[i] Loading FPGA config dissector: {abs_path}")
                break
        except (OSError, RuntimeError):
            # Path resolution failed, try next path
            continue
    
    # If no dissector found and verbose, report it
    if not dissector_loaded and verbose:
        print(f"[!] FPGA config dissector not found. Checked paths:")
        for dp in dissector_paths[:3]:  # Show first 3 paths checked
            print(f"    - {dp}")
    
    # Disable heuristic protocol dissectors (prevents false protocol detection)
    if disable_heuristics:
        # Disable UDP heuristic dissectors to prevent false detection like MNDP
        cmd.extend(['-o', 'udp.try_heuristic_first:FALSE'])
    
    # Disable specific protocols
    if disable_protocols:
        for proto in disable_protocols.split(','):
            proto = proto.strip()
            if proto:
                cmd.extend(['--disable-protocol', proto])
    
    # Append any additional tshark arguments
    if tshark_args_append:
        extra_args = shlex.split(tshark_args_append)
        cmd.extend(extra_args)
    
    if verbose:
        print(f"[i] Running: {' '.join(cmd)}")
        sys.stdout.flush()
    
    # Execute tshark
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        if result.returncode != 0:
            print(f"[!x!] tshark exited with code {result.returncode}")
            sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n[i] Interrupted")
        sys.exit(130)


def help_tshark_wrapper():
    print(hdlforge_command_tree.help_text(hdlforge_command_tree.parse(['tsharkWrapper'], Path.cwd())))
