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


def tshark_wrapper(c, pcap_file: str, output_format: str = 'to_plain_text',
                   frame_number: int = None, frame_start: int = None, frame_end: int = None,
                   frame_list: list = None, count: int = None, skip: int = None,
                   tshark_args_append: str = None, verbose: bool = False):
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
    """
    Show detailed help for tshark Wrapper tool
    """
    print("=" * 80)
    print("HDLFORGE TSHARK_WRAPPER - tshark Command Wrapper")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  A wrapper around tshark providing convenience options for common operations.")
    print("  Simplifies frame selection and enables checksum verification by default.")
    print()
    print("  This tool does NOT replace tshark - it wraps it with helpful presets.")
    print("  Use --tsharkArgsAppend to pass any additional tshark arguments directly.")
    print()
    print("USAGE:")
    print("  hdlforge --tool tsharkWrapper --pcap <FILE> [options]")
    print()
    print("REQUIRED ARGUMENTS:")
    print("    --pcap <FILE>                          PCAP file to analyze")
    print()
    print("OUTPUT FORMAT:")
    print("    --format to_plain_text                 Plain text output with hex dump (default)")
    print()
    print("FRAME SELECTION (convenience options):")
    print("    --frame <N>                            Display only frame number N")
    print("    --frame_start <N> --frame_end <M>      Display frames N through M")
    print("    --frame_list <N,M,O>                   Display specific frames (comma-separated)")
    print("    --count <N>                            Display first N packets")
    print("    --skip <N> --count <M>                 Skip N packets, then display M packets")
    print()
    print("RAW TSHARK ARGUMENTS:")
    print("    --tsharkArgsAppend '<ARGS>'            Append raw tshark arguments to command")
    print("                                           Quote the entire argument string")
    print()
    print("OPTIONS:")
    print("    --verbose                              Show tshark command being executed")
    print()
    print("EXAMPLES:")
    print("  # Display all packets with checksums verified")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap")
    print()
    print("  # Display only frame 4")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --frame 4")
    print()
    print("  # Display frames 10 through 20")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --frame_start 10 --frame_end 20")
    print()
    print("  # Display frames 1, 5, and 10")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --frame_list 1,5,10")
    print()
    print("  # Display first 10 packets")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --count 10")
    print()
    print("  # Skip first 100 packets, then display next 10")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --skip 100 --count 10")
    print()
    print("  # Append custom tshark arguments (filter by IP)")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --tsharkArgsAppend '-Y ip.addr==192.168.1.1'")
    print()
    print("  # Append multiple custom arguments")
    print("  hdlforge --tool tsharkWrapper --pcap capture.pcap --tsharkArgsAppend '-T fields -e frame.number -e ip.src'")
    print()
    print("CHECKSUM VERIFICATION (enabled by default):")
    print("  The wrapper automatically enables checksum verification for:")
    print("    - Ethernet FCS (Frame Check Sequence)")
    print("    - IPv4 header checksum")
    print("    - TCP checksum")
    print("    - UDP checksum")
    print()
    print("NOTES:")
    print("  - This is a WRAPPER around tshark, not a replacement")
    print("  - Requires tshark (part of Wireshark): sudo apt-get install tshark")
    print("  - Use --tsharkArgsAppend for any tshark option not covered above")
    print("  - See 'tshark --help' or 'man tshark' for all available tshark options")
    print()
    print("=" * 80)

