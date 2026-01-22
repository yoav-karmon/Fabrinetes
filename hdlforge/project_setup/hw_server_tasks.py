#!/usr/bin/env python3
"""
HW Server task handler for HDLForge
Interactive FPGA programming and debugging with persistent Vivado console
"""

import json
import os
import sys
import struct
import subprocess
import shutil
import time
import readline  # Enable command history with up/down arrows
from pathlib import Path
from typing import Dict, Optional, List

from prettytable import PrettyTable
from hw_server_console import VivadoTCLConsole


# Menu database structure - single source of truth for menu display
# Updated by _perform_scan(), used by _draw_menu_table()
_menu_db = {
    'devices': [],      # List of {'dna': str, 'name': str, 'usr_access': str, 'target_idx': int, 'device_idx': int, 'ila_list': [], 'vio_list': []}
    'files': [],        # List of {'filename': str, 'usr_access': str, 'path': str}
    'config_files': [], # List of JSON config files in invoked folder
    'selected_dna': '', # Currently selected device DNA
    'loaded_config': '',# Currently loaded config file path
    'hw_server_ip': 'localhost',   # Hardware server IP
    'hw_server_port': '3121',      # Hardware server port
    'config_version': '',          # Version from config file (e.g., "v1.6.0")
    'config_timestamp': '',        # Timestamp from config file (e.g., "2026-01-16 14:54")
    'config_bitstream': '',        # Bitstream filename from config
    'config_probes': '',           # Probes/ltx filename from config
    'last_checkout_tag': '',       # Last tag that was checked out
    'checkout_files': {},          # Dict of {filepath: mtime} for files from checkout
    'scanned': False,   # Whether scan has been performed
    'invoked_cwd': '',  # Directory where hw_server was invoked
}


# Global debug flag (set by hw_server function)
_debug_mode = False

def set_debug_mode(enabled: bool) -> None:
    """Set global debug mode."""
    global _debug_mode
    _debug_mode = enabled

def log_message(text: str) -> None:
    """Output a log message with [LOG]: prefix. Only shown in debug mode, except for errors."""
    # Always show error messages (starting with [!x!])
    if text.startswith("[!x!]"):
        print(f"[ERROR]: {text[6:]}", flush=True)  # Remove [!x!] prefix and show as ERROR
    elif _debug_mode:
        print(f"[LOG]: {text}", flush=True)


# Track if last command failed (for --cmd batch mode exit on failure)
_last_command_failed = False

def result_message(text: str) -> None:
    """Output a result message with [RESULT]: prefix."""
    global _last_command_failed
    # Track failures for batch mode
    _last_command_failed = "FAILED" in text.upper()
    print(f"[RESULT]: {text}", flush=True)


def display_box(title: str, content_lines: list = None, auto_close: bool = False) -> None:
    """Display content in a single box with title. If content_lines provided, display them inside.
    If auto_close is True, close the box automatically."""
    width = 60
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)
    if content_lines:
        for line in content_lines:
            print(f" {line}")
        if auto_close:
            print("=" * width)  # Close box only if auto_close is True
    # If no content_lines, caller will add content and close manually


def display_close_box() -> None:
    """Close a display box."""
    # Separator removed - no longer printing ==== after results
    pass


def hw_server(c, cmd: str = None, **kwargs):
    """
    HW Server command handler - Interactive FPGA programming and debugging.
    
    Args:
        c: Invoke context
        cmd: Command to execute (program, scan_ila, scan_jtag, etc.) - for backward compatibility
        **kwargs: Additional arguments
            cmd_list: List of menu selections from --cmd (can be multiple)
    """
    # Get configuration from kwargs
    server_ip = kwargs.get('server_ip', '')
    server_port = kwargs.get('server_port', '')
    bitstream = kwargs.get('bitstream', '')
    probes = kwargs.get('probes', '')
    config_file = kwargs.get('config_file', '')  # Only use if explicitly provided with -c
    interactive = kwargs.get('interactive', False)  # -i flag
    chain_commands = kwargs.get('chain_commands', [])  # -ic commands
    cmd_list = kwargs.get('cmd_list', [])  # --cmd commands (can be multiple)
    force_commit = kwargs.get('force', False)  # -f flag for force commit
    debug = kwargs.get('debug', False)  # -d/--debug flag
    set_debug_mode(debug)  # Set global debug mode
    
    # Use original CWD from where user invoked hdlforge (for Vivado logs and relative paths)
    invoked_cwd = kwargs.get('original_cwd', os.getcwd())
    
    # Load config file: use -f/-c if provided, otherwise auto-detect from invoke location
    config = {}
    config_path = ""
    
    if config_file:
        # Explicit config file provided via -f or -c
        config_path = os.path.expanduser(config_file)
        if not os.path.isabs(config_path):
            config_path = os.path.join(invoked_cwd, config_path)
    else:
        # Auto-detect: look for config.json in invoke location
        auto_config_path = os.path.join(invoked_cwd, "config.json")
        if os.path.exists(auto_config_path):
            config_path = auto_config_path
    
    if config_path:
        config = _load_config(config_path)
        if not config:
            log_message(f"[!x!] Config file not found or invalid: {config_path}")
            sys.exit(1)
        # Show which config file is being used
        print(f"[RESULT]: Using config file: {config_path}")
    else:
        # No config file found - continue without config (some features won't work)
        if not _debug_mode:
            pass  # Don't show message in non-debug mode
        else:
            log_message("No config file found (auto-detection failed, continuing without config)")
    
    # Handle new config format: DNA is the key, device settings are nested under it
    # e.g., { "DNA_VALUE": { "hw_server_host": "...", "bit_file": "...", ... } }
    # Note: device_name is no longer used - filename is the device name now
    device_dna = ''
    device_config = config
    
    config_keys = list(config.keys())
    if config_keys and not any(k in config_keys for k in ['hw_server_host', 'hw_server_port', 'bit_file', 'ltx_file', 'device']):
        # New format: first key is the DNA, value is the device config
        device_dna = config_keys[0]
        device_config = config.get(device_dna, {})
    else:
        # Old format: direct config with 'device' field
        device_dna = config.get('device', '') if isinstance(config.get('device'), str) else ''
    
    # Apply config values (only if not overridden by command line)
    if not server_ip:
        server_ip = device_config.get('hw_server_host', 'localhost')
    if not server_port:
        server_port = str(device_config.get('hw_server_port', '3121'))
    if not bitstream:
        bitstream = device_config.get('bit_file', '')
    if not probes:
        probes = device_config.get('ltx_file', '')
    
    # Resolve relative paths from config relative to invoked directory
    if bitstream and not os.path.isabs(bitstream) and not bitstream.startswith('~'):
        bitstream = os.path.join(invoked_cwd, bitstream)
    if probes and not os.path.isabs(probes) and not probes.startswith('~'):
        probes = os.path.join(invoked_cwd, probes)
    
    # Get VIO outputs from device config
    vio_outputs = device_config.get('vio_outputs', {})
    
    # Expand paths
    if bitstream:
        bitstream = os.path.expanduser(bitstream)
    if probes:
        probes = os.path.expanduser(probes)
    
    # Validate command (if provided)
    valid_cmds = ['program', 'scan_ila', 'scan_jtag', 'read_dna', 'read_usr_access', 'read_usr_access_device']
    if cmd and cmd not in valid_cmds:
        log_message(f"[!x!] Unknown command: {cmd}")
        log_message(f"[i] Valid commands: {', '.join(valid_cmds)}")
        sys.exit(1)
    
    # If no command, no cmd_list, and not interactive mode, show help
    if not cmd and not cmd_list and not interactive and not chain_commands:
        help_hw_server()
        return
    
    # Print header as logs
    log_message("HW Server - Interactive FPGA Tools")
    log_message(f"  Server:    {server_ip}:{server_port}")
    log_message(f"  Work dir:  {invoked_cwd}")
    if bitstream:
        log_message(f"  Bitstream: {bitstream}")
    if probes:
        log_message(f"  Probes:    {probes}")
    
    # Start Vivado console (from invoked location for logs)
    # For interactive mode, we'll start it lazily when needed
    console = VivadoTCLConsole(working_dir=invoked_cwd, debug=debug)
    
    # Store device DNA from config for later use (only if present and valid)
    console.config_device_dna = device_dna if device_dna and device_dna.strip() else None
    # Note: device names are now derived from config filenames via _get_device_name_by_dna()
    
    # Determine if we need console immediately (non-interactive commands always need it)
    # Note: cmd_list is now handled in interactive loop, so we don't need console immediately for it
    need_console_now = cmd is not None or chain_commands is not None
    
    try:
        if need_console_now:
            log_message("Initializing Vivado TCL console...")
            if not console.start():
                log_message("[!x!] Failed to start Vivado")
                sys.exit(1)
            
            log_message("Connecting to hardware server...")
            if not console.connect_hw_server(server_ip, server_port):
                log_message("[!x!] Failed to connect to hardware server")
                sys.exit(1)
            
            log_message("Connected successfully!")
            log_message(f"Target: {console.target}")
            log_message(f"Device: {console.device}")
        
        # Execute single command if provided (backward compatibility)
        if cmd:
            _execute_command(console, cmd, bitstream, probes)
        
        # Execute chain commands if provided (-ic)
        if chain_commands:
            # Ensure console is started for chain commands
            if not console.process:
                log_message("Initializing Vivado TCL console...")
                if not console.start():
                    log_message("[!x!] Failed to start Vivado")
                    sys.exit(1)
                
                log_message("Connecting to hardware server...")
                if not console.connect_hw_server(server_ip, server_port):
                    log_message("[!x!] Failed to connect to hardware server")
                    sys.exit(1)
                
                log_message("Connected successfully!")
                log_message(f"Target: {console.target}")
                log_message(f"Device: {console.device}")
            
            log_message("[BATCH MODE] Command Chain")
            # Also show descriptions next to each command
            described = []
            for cmd_token in chain_commands:
                desc = _describe_chain_command(cmd_token)
                if desc:
                    described.append(f"{cmd_token} ({desc})")
                else:
                    described.append(cmd_token)
            log_message(f"Commands: {'  '.join(described)}")
            total = len(chain_commands)
            for idx, chain_cmd in enumerate(chain_commands, start=1):
                label = chain_cmd
                desc = _describe_chain_command(chain_cmd)
                if desc:
                    label = f"{chain_cmd} ({desc})"
                log_message(f"[BATCH MODE] Executing ({idx}/{total}): {label}")
                ok = _execute_menu_choice(console, chain_cmd, bitstream, probes, vio_outputs, force_commit, server_ip, server_port, invoked_cwd, config_path)
                status = "COMPLETED" if ok else "FAILED or EXIT REQUESTED"
                log_message(f"[BATCH MODE] Completed ({idx}/{total}): {label}  -> {status}")
                if not ok:
                    break
        
        # Interactive mode (-i) or after cmd_list - console starts lazily when needed
        # If cmd_list was used, always enter interactive mode after executing commands
        if interactive or cmd_list:
            _interactive_loop(console, bitstream, probes, vio_outputs, config_path, server_ip, server_port, invoked_cwd, cmd_list)
    
    except KeyboardInterrupt:
        log_message("")
        log_message("Interrupted by user. Exiting...")
    except Exception as e:
        log_message("")
        log_message(f"[!x!] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Only close console if it was actually started
        if console.process:
            console.close()
            log_message("")
            log_message("Vivado console closed.")


def _execute_command(console: VivadoTCLConsole, cmd: str, bitstream: str, probes: str) -> bool:
    """Execute a single command."""
    if cmd == 'program':
        if not bitstream:
            log_message("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return False
        
        # Step 1: Read USR_ACCESS from bitstream file
        log_message("Step 1/3 - Reading USR_ACCESS from bitstream file")
        usr_access_value = _read_usr_access_value(bitstream)
        if usr_access_value is not None:
            major = (usr_access_value >> 16) & 0xFF
            minor = (usr_access_value >> 8) & 0xFF
            patch = usr_access_value & 0xFF
            result_message(f"Bitstream USR_ACCESS: V{major}.{minor}.{patch} (0x{usr_access_value:08X})")
        else:
            log_message("Warning: Could not read USR_ACCESS from bitstream file")
        
        # Step 2: Program FPGA
        log_message("Step 2/3 - Programming FPGA")
        success = console.program_fpga(bitstream, probes)
        
        if not success:
            result_message("PROGRAMMING FAILED")
            return False
        
        # Step 3: Verify USR_ACCESS from device
        log_message("Step 3/3 - Verifying USR_ACCESS from device")
        device_value = _read_usr_access_from_device_value(console)
        
        if device_value is not None:
            major = (device_value >> 16) & 0xFF
            minor = (device_value >> 8) & 0xFF
            patch = device_value & 0xFF
            result_message(f"Device USR_ACCESS: V{major}.{minor}.{patch} (0x{device_value:08X})")
            if usr_access_value is not None:
                if usr_access_value == device_value:
                    result_message("PROGRAMMING SUCCESS - USR_ACCESS verified")
                else:
                    result_message(f"PROGRAMMING SUCCESS - USR_ACCESS mismatch (bitstream: 0x{usr_access_value:08X}, device: 0x{device_value:08X})")
            else:
                result_message("PROGRAMMING SUCCESS")
        else:
            result_message("PROGRAMMING SUCCESS - USR_ACCESS not verified")
        
        return success
    
    elif cmd == 'scan_ila':
        if not probes:
            log_message("[!x!] Probes file must be specified with --probes or in config file")
            return False
        scan_result = console.scan_ila_vio(probes)
        # Result message is printed by scan_ila_vio itself
        if not scan_result:
            result_message("SCAN FAILED")
        return scan_result
    
    elif cmd == 'scan_jtag' or cmd == 'read_dna':
        jtag_result = console.scan_jtag()
        # Result message is printed by scan_jtag itself
        if not jtag_result:
            result_message("JTAG SCAN FAILED")
        return jtag_result
    
    elif cmd == 'read_usr_access':
        if not bitstream:
            log_message("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return False
        return _read_usr_access(bitstream)
    
    elif cmd == 'read_usr_access_device':
        if not console.connected:
            log_message("[!x!] Not connected to hardware server. Cannot read from device.")
            return False
        return _read_usr_access_from_device(console)
    
    return False


def _describe_chain_command(choice: str) -> str:
    """Return a human-readable description for a chain/interactive command."""
    c = choice.lower().strip()

    # Top-level numeric / word commands
    if c in ("1", "pr", "prog", "program", "pro"):
        return "Program FPGA"
    # Scan removed - now runs automatically when device is selected
    if c in ("2", "jt", "jtag", "scan", "scan_jtag", "read_dna"):
        return "Scan JTAG / Read DNA"
    if c.startswith("open "):
        dna_part = c[5:].strip()
        return f"Open device: {dna_part}"
    if c in ("3", "rb", "readbit", "read_bit", "read-file", "read_file", "read_usr_access"):
        return "Read USR_ACCESS/USERID from bitstream file"
    if c in ("4", "rd", "readdev", "read_dev", "read-device", "read_device", "read_usr_access_device"):
        return "Read USR_ACCESS/USERID from FPGA device"
    if c in ("5", "co", "checkout", "checkout_release"):
        return "Checkout release (restore files from git tag)"
    if c in ("6", "cl", "clear", "clear_fpga"):
        return "Clear/Reset FPGA Device"
    if c in ("q", "quit", "exit"):
        return "Exit"

    # ILA commands
    if c.startswith("ila-") and "-save-" not in c:
        idx = c[len("ila-"):]
        return f"Read ILA {idx}"
    if c.startswith("ila-") and "-save-ila" in c:
        idx = c[len("ila-"):].split("-save-ila")[0]
        return f"Save ILA {idx} as .ila"
    if c.startswith("ila-") and "-save-vcd" in c:
        idx = c[len("ila-"):].split("-save-vcd")[0]
        return f"Save ILA {idx} as .vcd"
    if c.startswith("ila-") and "-save-csv" in c:
        idx = c[len("ila-"):].split("-save-csv")[0]
        return f"Save ILA {idx} as .csv"


    return ""


def _ensure_console_started(console: VivadoTCLConsole, server_ip: str, server_port: str) -> bool:
    """Ensure console is started and connected to the specified hw_server. Returns True if successful."""
    # Check if already connected to the CORRECT hw_server
    if console.process and console.connected:
        # Check if connected to the right server
        current_server = getattr(console, 'connected_server', '')
        requested_server = f"{server_ip}:{server_port}"
        if current_server == requested_server:
            return True
        else:
            # Connected to wrong server - close and reconnect
            log_message(f"Reconnecting to {requested_server} (was: {current_server})...")
            console.close()
    
    if not console.process:
        log_message("Initializing Vivado TCL console...")
        if not console.start():
            log_message("[!x!] Failed to start Vivado")
            return False
    
    if not console.connected:
        log_message(f"Connecting to hardware server {server_ip}:{server_port}...")
        if not console.connect_hw_server(server_ip, server_port):
            log_message("[!x!] Failed to connect to hardware server")
            return False
        
        # Store which server we're connected to
        console.connected_server = f"{server_ip}:{server_port}"
        
        log_message("Connected successfully!")
        log_message(f"Target: {console.target}")
        log_message(f"Device: {console.device}")
    
    return True


def _confirm_action(action: str, details: list, warnings: list, force: bool = False) -> bool:
    """Show action details and warnings, ask for confirmation.
    
    Args:
        action: Name of the action (e.g., "PROGRAM", "CLEAR", "SET VIO")
        details: List of detail lines to display
        warnings: List of warning messages (displayed in yellow/highlighted)
        force: If True, skip confirmation prompt but still display info
        
    Returns:
        True if action should proceed, False if cancelled
    """
    print()
    print(f"{'='*60}")
    print(f" {action}")
    print(f"{'='*60}")
    
    # Display details
    for detail in details:
        print(f"  {detail}")
    
    # Display warnings
    if warnings:
        print()
        print("  [WARNINGS]")
        for warning in warnings:
            print(f"  !! {warning}")
    
    print(f"{'='*60}")
    
    # If force mode, proceed without asking
    if force:
        print("  (force mode: proceeding without confirmation)")
        print()
        return True
    
    # Ask for confirmation
    try:
        if sys.stdin.isatty():
            response = input("  Proceed? (y/N): ").strip().lower()
            if response in ('y', 'yes'):
                return True
            else:
                print("  Cancelled.")
                return False
        else:
            # Non-interactive mode - require force flag
            print("  Non-interactive mode: use -f to force execution")
            return False
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return False


def _execute_menu_choice(console: VivadoTCLConsole, choice: str, 
                         bitstream: str, probes: str, 
                         vio_outputs: dict = None, force: bool = False,
                         server_ip: str = 'localhost', server_port: str = '3121',
                         invoked_cwd: str = None, config_path: str = "",
                         cmd_queue: list = None) -> bool:
    """Execute a menu choice. Returns False if should exit.
    
    Args:
        cmd_queue: Optional list of commands to consume for sub-prompts (e.g., tag selection)
    """
    global _menu_db
    choice_lower = choice.lower().strip()
    
    # Handle sleep command
    if choice_lower.startswith("sleep "):
        try:
            sleep_arg = choice_lower[6:].strip()
            sleep_seconds = float(sleep_arg)
            if sleep_seconds < 0:
                result_message("SLEEP FAILED - Duration must be positive")
                return True
            time.sleep(sleep_seconds)
            return True
        except ValueError:
            result_message(f"SLEEP FAILED - Invalid duration: {sleep_arg}")
            return True
    
    # Handle load command (keep original case for path)
    if choice_lower.startswith("load "):
        config_file_arg = choice[5:].strip()  # Keep original case for path
        if not config_file_arg:
            result_message("LOAD FAILED - Usage: load <config_file.json>")
            return True
        
        # Expand environment variables and resolve path
        config_path_resolved = _expand_path(config_file_arg, invoked_cwd or os.getcwd())
        
        if not os.path.exists(config_path_resolved):
            result_message(f"LOAD FAILED - Config file not found: {config_path_resolved}")
            return True
        
        if not config_path_resolved.endswith('.json'):
            result_message(f"LOAD FAILED - Config file must be .json: {config_path_resolved}")
            return True
        
        # Close TCL console and disconnect from hw_server
        if console.connected:
            result_message("Disconnecting from hardware server...")
            console.close()
        
        # Load the new config
        try:
            new_config, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, new_device_dna, _, _, new_version, new_timestamp = _load_and_resolve_config(config_path_resolved, invoked_cwd)
            
            if not new_config:
                result_message(f"LOAD FAILED - Could not parse config: {config_path_resolved}")
                return True
            
            # Update console state
            if new_device_dna:
                console.config_device_dna = new_device_dna
            
            # Clear device selection and cache (need to re-scan with new config)
            console.device_explicitly_selected = False
            console.selected_device_dna = ''
            console.device = None
            console.target = None
            console.device_list_cache = []  # Clear old device cache to avoid stale data
            
            # Update menu database
            _menu_db['loaded_config'] = config_path_resolved
            _menu_db['devices'] = []
            _menu_db['files'] = []
            _menu_db['selected_dna'] = ''
            _menu_db['scanned'] = False
            _menu_db['hw_server_ip'] = new_server_ip or 'localhost'
            _menu_db['hw_server_port'] = new_server_port or '3121'
            _menu_db['config_version'] = new_version or ''
            _menu_db['config_timestamp'] = new_timestamp or ''
            _menu_db['config_bitstream'] = os.path.basename(new_bitstream) if new_bitstream else ''
            _menu_db['config_probes'] = os.path.basename(new_probes) if new_probes else ''
            
            result_message(f"CONFIG LOADED - {os.path.basename(config_path_resolved)}")
            result_message(f"  hw_server: {_menu_db['hw_server_ip']}:{_menu_db['hw_server_port']}")
            result_message(f"  device DNA: {new_device_dna}")
            if new_bitstream:
                version_str = new_version if new_version else 'NA'
                timestamp_str = new_timestamp if new_timestamp else 'NA'
                result_message(f"  bitstream: {os.path.basename(new_bitstream)} {version_str} ({timestamp_str})")
            
            # Auto-scan and open device
            if new_device_dna:
                result_message("")
                result_message("Scanning for device...")
                
                # Perform scan with new hw_server settings
                _perform_scan(console, new_bitstream, new_probes, new_server_ip, new_server_port)
                
                # If files list is empty after scan, populate from folder
                if not _menu_db.get('files') and invoked_cwd and os.path.isdir(invoked_cwd):
                    files_in_folder = []
                    for f in sorted(os.listdir(invoked_cwd)):
                        filepath = os.path.join(invoked_cwd, f)
                        if os.path.isfile(filepath) and (f.endswith('.bit') or f.endswith('.ltx')):
                            decoded = ''
                            if f.endswith('.bit'):
                                try:
                                    usr_access = _read_usr_access_value(filepath)
                                    userid = _read_userid_raw(filepath)
                                    version = _decode_version(usr_access) if usr_access else ''
                                    timestamp = _decode_timestamp(userid) if userid else ''
                                    if version or timestamp:
                                        decoded = f"{version} ({timestamp})" if version and timestamp else (version or timestamp)
                                except:
                                    pass
                            files_in_folder.append({'filename': f, 'path': filepath, 'decoded': decoded})
                    _menu_db['files'] = files_in_folder
                
                # Try to open the device by DNA from config
                found_device = False
                matched_idx = -1
                for idx, dev in enumerate(_menu_db.get('devices', [])):
                    dev_dna = dev.get('dna', '')
                    # Normalize DNAs for comparison
                    dev_clean = dev_dna.strip('0').upper() or '0'
                    config_clean = new_device_dna.strip('0').upper() or '0'
                    if dev_clean == config_clean:
                        matched_idx = idx
                        # Found matching device - open it by DNA (never use cached indices!)
                        if console.find_and_select_device_by_dna(dev_dna, "load"):
                            # Update console state
                            console.device_display_name = dev.get('name', '') or dev.get('dev_name', '')
                            console.target = dev.get('target_name', '')
                            console.device_explicitly_selected = True
                            console.selected_device_dna = dev_dna
                            _menu_db['selected_dna'] = dev_dna
                            
                            dev_name = dev.get('name', '')
                            if dev_name:
                                result_message(f"DEVICE OPENED - {dev_name} ({dev_dna})")
                            else:
                                result_message(f"DEVICE OPENED - {dev_dna}")
                        
                        # Scan ILA/VIO if probes file available
                        # Auto-detect probes file if not specified
                        probes_to_use = new_probes
                        if not probes_to_use:
                            probes_to_use = _menu_db.get('config_probes', '')
                            if probes_to_use and invoked_cwd:
                                probes_to_use = os.path.join(invoked_cwd, probes_to_use)
                        if not probes_to_use:
                            # Auto-detect from files list
                            for f in _menu_db.get('files', []):
                                if f.get('filename', '').endswith('.ltx'):
                                    probes_to_use = f.get('path', '')
                                    break
                        
                        if probes_to_use:
                            scan_result = console.scan_ila_vio(probes_to_use)
                            if scan_result:
                                ila_list = console._get_ila_list()
                                vio_list = console._get_vio_list()
                                if matched_idx >= 0 and matched_idx < len(_menu_db.get('devices', [])):
                                    _menu_db['devices'][matched_idx]['ila_list'] = ila_list
                                    _menu_db['devices'][matched_idx]['vio_list'] = vio_list
                                result_message(f"ILA/VIO scan: {len(ila_list)} ILA, {len(vio_list)} VIO found")
                        else:
                            result_message("(no probes file for ILA/VIO scan)")
                        
                        found_device = True
                        break
                
                if not found_device:
                    result_message(f"WARNING - Device DNA {new_device_dna} not found on JTAG chain")
            
            return True
        except Exception as e:
            result_message(f"LOAD FAILED - Error loading config: {e}")
            return True
    
    # Handle server command to edit hw_server settings
    if choice_lower.startswith("server"):
        args = choice_lower[6:].strip()
        
        if not args:
            # Interactive mode - prompt for IP and port
            try:
                current_ip = _menu_db.get('hw_server_ip', 'localhost')
                current_port = _menu_db.get('hw_server_port', '3121')
                
                result_message(f"Current hw_server: {current_ip}:{current_port}")
                result_message("")
                
                new_ip = input(f"Enter IP [{current_ip}]: ").strip()
                if not new_ip:
                    new_ip = current_ip
                
                new_port = input(f"Enter port [{current_port}]: ").strip()
                if not new_port:
                    new_port = current_port
                
                # Validate port
                try:
                    port_num = int(new_port)
                    if port_num < 1 or port_num > 65535:
                        result_message("SERVER FAILED - Port must be between 1 and 65535")
                        return True
                except ValueError:
                    result_message("SERVER FAILED - Port must be a number")
                    return True
                
                # Close TCL console completely (need to restart with new hw_server)
                if console.process or console.connected:
                    result_message("Closing TCL console...")
                    console.close()  # This terminates the process too
                
                # Update menu database
                _menu_db['hw_server_ip'] = new_ip
                _menu_db['hw_server_port'] = new_port
                _menu_db['devices'] = []
                _menu_db['scanned'] = False
                _menu_db['selected_dna'] = ''
                console.device_list_cache = []  # Clear old device cache
                
                result_message(f"SERVER UPDATED - {new_ip}:{new_port}")
                result_message("(run 'scan' to connect with new settings)")
                
            except (EOFError, KeyboardInterrupt):
                result_message("SERVER - Cancelled")
            return True
        else:
            # Parse ip:port from args
            if ':' in args:
                parts = args.split(':')
                new_ip = parts[0].strip()
                new_port = parts[1].strip()
            else:
                new_ip = args
                new_port = _menu_db.get('hw_server_port', '3121')
            
            # Validate port
            try:
                port_num = int(new_port)
                if port_num < 1 or port_num > 65535:
                    result_message("SERVER FAILED - Port must be between 1 and 65535")
                    return True
            except ValueError:
                result_message("SERVER FAILED - Port must be a number")
                return True
            
            # Close TCL console completely (need to restart with new hw_server)
            if console.process or console.connected:
                result_message("Closing TCL console...")
                console.close()  # This terminates the process too
            
            # Update menu database
            _menu_db['hw_server_ip'] = new_ip
            _menu_db['hw_server_port'] = new_port
            _menu_db['devices'] = []
            _menu_db['scanned'] = False
            _menu_db['selected_dna'] = ''
            console.device_list_cache = []  # Clear old device cache
            
            result_message(f"SERVER UPDATED - {new_ip}:{new_port}")
            result_message("(run 'scan' to connect with new settings)")
            return True
    
    # Handle file-bit command to set bitstream file path
    if choice_lower.startswith("file-bit"):
        args = choice[8:].strip()  # Keep original case for path
        
        current_bit = _menu_db.get('config_bitstream', '')
        
        if not args:
            # Interactive mode - prompt for path
            try:
                result_message(f"Current bitstream: {current_bit or '(none)'}")
                new_path = input("Enter bitstream path: ").strip()
                if not new_path:
                    result_message("FILE-BIT - Cancelled (no path entered)")
                    return True
            except (EOFError, KeyboardInterrupt):
                result_message("FILE-BIT - Cancelled")
                return True
        else:
            new_path = args
        
        # Expand and resolve path
        new_path = _expand_path(new_path, invoked_cwd or os.getcwd())
        
        if not os.path.exists(new_path):
            result_message(f"FILE-BIT WARNING - File not found: {new_path}")
        
        if not new_path.endswith('.bit'):
            result_message(f"FILE-BIT WARNING - File should be .bit: {new_path}")
        
        # Update menu database
        _menu_db['config_bitstream'] = os.path.basename(new_path)
        
        # Update files list with new bitstream info
        # Remove old .bit entry and add new one
        files = _menu_db.get('files', [])
        files = [f for f in files if not f.get('filename', '').endswith('.bit')]
        
        # Read version/timestamp from new bitstream
        decoded = ''
        if os.path.exists(new_path):
            try:
                usr_access = _read_usr_access_value(new_path)
                userid = _read_userid_raw(new_path)
                version = _decode_version(usr_access) if usr_access else ''
                timestamp = _decode_timestamp(userid) if userid else ''
                if version or timestamp:
                    decoded = f"{version} ({timestamp})" if version and timestamp else (version or timestamp)
            except:
                pass
        
        files.insert(0, {'filename': os.path.basename(new_path), 'path': new_path, 'decoded': decoded})
        _menu_db['files'] = files
        
        result_message(f"FILE-BIT UPDATED - {os.path.basename(new_path)}")
        if decoded:
            result_message(f"  {decoded}")
        return True
    
    # Handle file-ltx command to set probes file path
    if choice_lower.startswith("file-ltx"):
        args = choice[8:].strip()  # Keep original case for path
        
        current_ltx = _menu_db.get('config_probes', '')
        
        if not args:
            # Interactive mode - prompt for path
            try:
                result_message(f"Current probes file: {current_ltx or '(none)'}")
                new_path = input("Enter probes file path: ").strip()
                if not new_path:
                    result_message("FILE-LTX - Cancelled (no path entered)")
                    return True
            except (EOFError, KeyboardInterrupt):
                result_message("FILE-LTX - Cancelled")
                return True
        else:
            new_path = args
        
        # Expand and resolve path
        new_path = _expand_path(new_path, invoked_cwd or os.getcwd())
        
        if not os.path.exists(new_path):
            result_message(f"FILE-LTX WARNING - File not found: {new_path}")
        
        if not new_path.endswith('.ltx'):
            result_message(f"FILE-LTX WARNING - File should be .ltx: {new_path}")
        
        # Update menu database
        _menu_db['config_probes'] = os.path.basename(new_path)
        
        # Update files list with new ltx info
        # Remove old .ltx entry and add new one
        files = _menu_db.get('files', [])
        files = [f for f in files if not f.get('filename', '').endswith('.ltx')]
        files.append({'filename': os.path.basename(new_path), 'path': new_path, 'decoded': ''})
        _menu_db['files'] = files
        
        result_message(f"FILE-LTX UPDATED - {os.path.basename(new_path)}")
        return True
    
    choice = choice_lower  # Use lowercase for other commands
    
    # Check for force flag (-f) at end of command
    force_flag = False
    if choice.endswith(' -f'):
        force_flag = True
        choice = choice[:-3].strip()  # Remove trailing ' -f'
    elif choice == '-f':
        force_flag = True
        choice = ''
    
    if choice in ("1", "pr", "prog", "program", "pro"):
        # Reload config if available to get latest bitstream/probes paths
        current_bitstream = bitstream
        current_probes = probes
        config_version = ''
        config_timestamp = ''
        if config_path and os.path.exists(config_path):
            _, _, _, current_bitstream, current_probes, _, _, _, _, config_version, config_timestamp = _load_and_resolve_config(config_path, invoked_cwd, silent=True)
            if not current_bitstream:
                current_bitstream = bitstream  # Fallback to original
            if not current_probes:
                current_probes = probes  # Fallback to original
        
        if not current_bitstream:
            log_message("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return True
        
        if not console.selected_device_dna:
            log_message("[!x!] No device selected - use 'open <dna>' to select a device first")
            return True
        
        # Build confirmation details
        invoked_cwd_local = _menu_db.get('invoked_cwd', '') or invoked_cwd or ''
        device_name = _get_device_name_by_dna(console.selected_device_dna, invoked_cwd_local)
        
        details = []
        details.append(f"Device: {device_name or console.selected_device_dna}")
        details.append(f"DNA: {console.selected_device_dna}")
        if config_path:
            details.append(f"Config: {os.path.basename(config_path)}")
        details.append(f"Bitstream: {os.path.basename(current_bitstream)}")
        
        # Read bitstream version/timestamp
        bitstream_version = ''
        bitstream_timestamp = ''
        try:
            bitstream_usr_access = _read_usr_access_from_bitstream(current_bitstream)
            if bitstream_usr_access:
                major = (bitstream_usr_access >> 16) & 0xFF
                minor = (bitstream_usr_access >> 8) & 0xFF
                patch = bitstream_usr_access & 0xFF
                bitstream_version = f"V{major}.{minor}.{patch}"
                details.append(f"Bitstream Version: {bitstream_version}")
        except:
            pass
        
        # Collect warnings
        warnings = []
        
        # Check DNA mismatch with config
        if console.config_device_dna:
            selected_clean = console.selected_device_dna.strip('0').upper() or '0'
            config_clean = console.config_device_dna.strip('0').upper() or '0'
            if selected_clean != config_clean:
                warnings.append(f"Device DNA does not match config DNA!")
                warnings.append(f"  Selected: {console.selected_device_dna}")
                warnings.append(f"  Config:   {console.config_device_dna}")
        
        # Check if bitstream file exists
        if not os.path.exists(current_bitstream):
            warnings.append(f"Bitstream file not found: {current_bitstream}")
        
        # Ask for confirmation
        if not _confirm_action("PROGRAM FPGA", details, warnings, force_flag):
            return True
        
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        
        # Store the selected DNA before programming (to re-open after)
        selected_dna = console.selected_device_dna
        
        program_success = _execute_command(console, 'program', current_bitstream, current_probes)
        # After programming, clear ILA/VIO cache and re-open the device
        if program_success:
            console.core_cache = {}
            console.scanned = False
            
            # Re-open the device if we had one selected
            if selected_dna:
                result_message(f"Re-opening device {selected_dna}...")
                # Re-open device by DNA (never use cached indices!)
                try:
                    if console.find_and_select_device_by_dna(selected_dna, "program_reopen"):
                        # Restore console state
                        console.device_explicitly_selected = True
                        console.selected_device_dna = selected_dna
                        _menu_db['selected_dna'] = selected_dna
                        
                        # Find device entry in menu database and update it
                        matched_idx = -1
                        for idx, dev in enumerate(_menu_db.get('devices', [])):
                            dev_dna = dev.get('dna', '')
                            dev_dna_clean = dev_dna.lstrip('0').upper() or '0'
                            selected_clean = selected_dna.lstrip('0').upper() or '0'
                            if dev_dna_clean == selected_clean:
                                console.device_display_name = dev.get('name', '') or dev.get('dev_name', '') or dev.get('dna', '')
                                console.target = dev.get('target_name', '')
                                matched_idx = idx
                                break
                        
                        # Scan ILA/VIO on the re-opened device
                        if current_probes and os.path.exists(current_probes):
                            console.scan_ila_vio(current_probes)
                            result_message(f"ILA/VIO scan: {len(console._get_ila_list())} ILA, {len(console._get_vio_list())} VIO found")
                            
                            # Update menu database with ILA/VIO lists so menu shows them
                            if matched_idx >= 0 and matched_idx < len(_menu_db.get('devices', [])):
                                _menu_db['devices'][matched_idx]['ila_list'] = console._get_ila_list()
                                _menu_db['devices'][matched_idx]['vio_list'] = console._get_vio_list()
                        
                        result_message(f"Device re-opened: {selected_dna}")
                except Exception as e:
                    log_message(f"Could not re-open device: {e}")
        # Always return True to keep menu running - program failure is not exit condition
        return True
    # Device scan - scans JTAG chain, reads DNA and USR_ACCESS from each device
    # User must explicitly select with 'open <dna>'
    elif choice in ("2", "jt", "jtag", "scan", "scan_jtag"):
        # Use hw_server settings from _menu_db (updated by 'server' command)
        scan_ip = _menu_db.get('hw_server_ip', '') or server_ip or 'localhost'
        scan_port = _menu_db.get('hw_server_port', '') or server_port or '3121'
        
        if not _ensure_console_started(console, scan_ip, scan_port):
            return True
        # Use isolated scan function
        result = _perform_scan(console, bitstream, probes, scan_ip, scan_port)
        # No auto-selection - user must explicitly select device with 'open <dna>'
        return True
    elif choice.startswith("open "):
        # Handle device selection by DNA: open <dna>
        # DNA can be trimmed of leading zeros
        # If scan wasn't done, perform scan first
        # Use hw_server settings from _menu_db (updated by 'server' command)
        open_ip = _menu_db.get('hw_server_ip', '') or server_ip or 'localhost'
        open_port = _menu_db.get('hw_server_port', '') or server_port or '3121'
        
        if not _ensure_console_started(console, open_ip, open_port):
            return True
        
        # Check if scan was performed, if not do it now
        if not _menu_db.get('scanned') or not _menu_db.get('devices'):
            result_message("Performing scan before device selection...")
            _perform_scan(console, bitstream, probes, open_ip, open_port)
            
            # Populate files list from folder if still empty (for probes auto-detection)
            if not _menu_db.get('files') and invoked_cwd and os.path.isdir(invoked_cwd):
                files_in_folder = []
                for f in sorted(os.listdir(invoked_cwd)):
                    filepath = os.path.join(invoked_cwd, f)
                    if os.path.isfile(filepath) and (f.endswith('.bit') or f.endswith('.ltx')):
                        decoded = ''
                        if f.endswith('.bit'):
                            try:
                                usr_access = _read_usr_access_value(filepath)
                                userid = _read_userid_raw(filepath)
                                version = _decode_version(usr_access) if usr_access else ''
                                timestamp = _decode_timestamp(userid) if userid else ''
                                if version or timestamp:
                                    decoded = f"{version} ({timestamp})" if version and timestamp else (version or timestamp)
                            except:
                                pass
                        files_in_folder.append({'filename': f, 'path': filepath, 'decoded': decoded})
                _menu_db['files'] = files_in_folder
        
        try:
            idx_str = choice[5:].strip()  # Get DNA after "open "
            # Use menu database for device list
            device_list = _menu_db.get('devices', [])
            
            # Match by DNA value only (allowing leading zeros removal)
            # DNA can be provided with or without leading zeros
            matched_dev = None
            matched_idx = -1  # Index in device_list for updating device database
            input_dna_clean = idx_str.strip().lstrip('0').upper() or '0'
            
            for i, dev in enumerate(device_list):
                dev_dna = dev.get('dna', '')
                if dev_dna and dev_dna != "N/A":
                    # Remove leading zeros from device DNA for comparison
                    dev_dna_clean = dev_dna.lstrip('0').upper() or '0'
                    if dev_dna_clean == input_dna_clean:
                        matched_dev = dev
                        matched_idx = i
                        break
            
            # No index-based matching - only DNA matching is allowed
            
            if matched_dev:
                dev = matched_dev
                dev_dna = dev.get('dna', '')
                
                # ALWAYS clear ILA/VIO cache before device selection (even if same device)
                # This forces a fresh re-read of ILA/VIO cores every time a device is selected
                console.core_cache = {}
                console.scanned = False
                
                # Find and select device by DNA (never use cached indices!)
                if not console.find_and_select_device_by_dna(dev_dna, "open"):
                    result_message(f"OPEN FAILED - Could not find device with DNA {dev_dna}")
                    return True
                
                # Update console state
                console.device_display_name = dev.get('name', '') or dev.get('dev_name', '') or dev.get('dna', '')
                console.target = dev.get('target_name', '')
                
                # Mark device as explicitly selected by user and store its DNA for menu matching
                console.device_explicitly_selected = True
                console.selected_device_dna = dev_dna
                
                # Update menu database with selection
                _menu_db['selected_dna'] = dev.get('dna', '')
                
                # Automatically scan ILA/VIO when device is selected
                dna_display = dev.get('dna', 'N/A')
                result_message(f"DEVICE SELECTED - DNA: {dna_display}")
                
                # Use probes from parameter, or from _menu_db, or auto-detect from files
                probes_to_use = probes
                if not probes_to_use:
                    probes_to_use = _menu_db.get('config_probes', '')
                if not probes_to_use:
                    # Auto-detect from files list
                    for f in _menu_db.get('files', []):
                        if f.get('filename', '').endswith('.ltx'):
                            probes_to_use = f.get('path', '')
                            break
                
                if probes_to_use:
                    # Scan ILA/VIO and store results in device database
                    scan_result = console.scan_ila_vio(probes_to_use)
                    if scan_result:
                        # Store ILA/VIO lists in device entry (part of menu database)
                        ila_list = console._get_ila_list()
                        vio_list = console._get_vio_list()
                        if matched_idx >= 0 and matched_idx < len(_menu_db.get('devices', [])):
                            _menu_db['devices'][matched_idx]['ila_list'] = ila_list
                            _menu_db['devices'][matched_idx]['vio_list'] = vio_list
                    else:
                        result_message("SCAN FAILED - ILA/VIO scan could not complete")
                else:
                    result_message("(no probes file for ILA/VIO scan)")
                
                return True
            else:
                result_message(f"Invalid device selection: {choice}")
                return True
        except Exception as e:
            result_message(f"Invalid device selection: {choice} ({str(e)})")
            return True
    elif choice in ("3", "rb", "readbit", "read_bit", "read-file", "read_file", "read_usr_access"):
        # Option 4 doesn't need console - reads from bitstream file directly
        if not bitstream:
            log_message("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return True
        result = _read_usr_access(bitstream)
        return result
    
    elif choice in ("4", "rd", "readdev", "read_dev", "read-device", "read_device", "read_usr_access_device"):
        # Check device cache BEFORE opening TCL console (read-device can work with any device, but check cache first)
        if not console.device:
            result_message("READ FAILED - No device available (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        # Ensure device is properly set in TCL context before reading
        if console.device:
            console.send_command("set devices [get_hw_devices]", timeout=2)
            console.send_command("set device_found 0", timeout=1)
            console.send_command(f'foreach d $devices {{ if {{[get_property NAME $d] == "{console.device}"}} {{ set device $d; set device_found 1; break }} }}', timeout=3)
            console.send_command("if {!$device_found} { set device [lindex $devices 0] }", timeout=2)
            console.send_command("current_hw_device $device", timeout=2)
        result = _read_usr_access_from_device(console)
        return result
    elif choice in ("5", "co", "checkout", "checkout_release"):
        # Option 5: Checkout release (restore files from git tag)
        if not invoked_cwd:
            invoked_cwd = os.getcwd()
        
        # Get project paths
        project_dir, release_dir, git_repo_root, release_config, hw_config = _get_project_paths(invoked_cwd)
        
        # Show available releases and get selection
        tag_arg = _select_release_tag(project_dir, cmd_queue)
        if not tag_arg:
            return True
        
        log_message(f"Selected tag: {tag_arg}")
        
        # Close console if it's running (we'll restart after reloading config)
        if console.process:
            log_message("Closing Vivado console before checkout...")
            console.close()
        
        # Checkout files to release folder (overwrites existing)
        if not _pull_release_to_folder(project_dir, release_dir, git_repo_root, release_config, hw_config, tag_arg):
            result_message("CHECKOUT FAILED - Could not fetch release files")
            return True
        
        # Clear menu database to force re-read of files
        _menu_db['files'] = []
        _menu_db['scanned'] = False
        
        # Record the checked out tag
        _menu_db['last_checkout_tag'] = tag_arg
        result_message(f"CHECKOUT SUCCESS - release folder restored from tag {tag_arg} (only release folder is checked out)")
        
        # Reload config after checkout if it exists
        if hw_config.exists():
            log_message("Reloading config after checkout...")
            new_config, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, new_device_dna, new_config_path, _, new_version, new_timestamp = _load_and_resolve_config(str(hw_config), invoked_cwd)
            
            if new_config:
                # Update device DNA from config if present
                if new_device_dna and new_device_dna.strip():
                    console.config_device_dna = new_device_dna
                # Update the values for subsequent operations
                bitstream = new_bitstream
                probes = new_probes
                vio_outputs = new_vio_outputs
                server_ip = new_server_ip
                server_port = new_server_port
                config_path = new_config_path
                # Store modification times of checked out files for verification
                checkout_files = {}
                if new_bitstream and os.path.exists(new_bitstream):
                    checkout_files[new_bitstream] = os.path.getmtime(new_bitstream)
                if new_probes and os.path.exists(new_probes):
                    checkout_files[new_probes] = os.path.getmtime(new_probes)
                if new_config_path and os.path.exists(new_config_path):
                    checkout_files[new_config_path] = os.path.getmtime(new_config_path)
                _menu_db['checkout_files'] = checkout_files
                
                # Verify bitstream version/timestamp matches config if specified
                if new_bitstream and os.path.exists(new_bitstream):
                    _verify_bitstream_matches_config(new_bitstream, new_version, new_timestamp)
        else:
            log_message("No config.json found - checkout complete, use 'load' to load a config file")
        
        return True  # Continue with menu (checkout only, no programming)
    elif choice in ("6", "cl", "clear", "clear_fpga"):
        # Check device cache BEFORE opening TCL console
        if not console.device:
            result_message("CLEAR FAILED - No device available (use 'scan' then 'open <dna>')")
            return True
        
        if not console.selected_device_dna:
            result_message("CLEAR FAILED - No device selected (use 'open <dna>' to select)")
            return True
        
        # Build confirmation details
        invoked_cwd_local = _menu_db.get('invoked_cwd', '') or invoked_cwd or ''
        device_name = _get_device_name_by_dna(console.selected_device_dna, invoked_cwd_local)
        
        details = [
            f"Device: {device_name or console.selected_device_dna}",
            f"DNA: {console.selected_device_dna}",
            "This will reset the FPGA to an unprogrammed state.",
        ]
        warnings = []
        
        # Ask for confirmation
        if not _confirm_action("CLEAR FPGA", details, warnings, force_flag):
            return True
        
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        result = console.clear_fpga()
        if not result:
            return True  # Continue with menu on error
        
        # Clear menu database and re-scan after clear
        _menu_db['devices'] = []
        _menu_db['selected_dna'] = ''
        _menu_db['scanned'] = False
        console.device_explicitly_selected = False
        console.selected_device_dna = ''
        
        # Re-scan JTAG chain
        result_message("Re-scanning JTAG chain after clear...")
        _perform_scan(console, bitstream, probes, server_ip, server_port)
        return True
    elif choice in ("q", "quit", "exit"):
        return False
    # ILA commands (ila-1, ila-1-save-ila, ila-1-save-vcd, ila-1-save-csv)
    elif choice.startswith("ila-") and "-save-" not in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("READ FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            # Extract index from "ila-1" format
            idx_str = choice[len("ila-"):]
            ila_idx = int(idx_str) - 1
            # Check if ILA cores exist before trying to read
            ila_list = console._get_ila_list()
            if len(ila_list) == 0:
                result_message("READ FAILED - No ILA cores found (device may need to be programmed first)")
            else:
                console.print_ila_details(ila_idx)
        except ValueError:
            result_message(f"Invalid ILA selection: {choice}")
        except Exception as e:
            result_message(f"READ FAILED - Error reading ILA: {str(e)}")
        return True  # Always return True to continue menu loop
    elif choice.startswith("ila-") and "-save-ila" in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("SAVE FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            idx_str = choice[len("ila-"):].split("-save-ila")[0]
            ila_idx = int(idx_str) - 1
            console.save_ila_data(ila_idx, fmt="ila")
        except ValueError:
            result_message(f"Invalid ILA save selection: {choice}")
        return True  # Always return True to continue menu loop
    elif choice.startswith("ila-") and "-save-vcd" in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("SAVE FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            idx_str = choice[len("ila-"):].split("-save-vcd")[0]
            ila_idx = int(idx_str) - 1
            console.save_ila_data(ila_idx, fmt="vcd")
        except ValueError:
            result_message(f"Invalid VCD save selection: {choice}")
        return True  # Always return True to continue menu loop
    elif choice.startswith("ila-") and "-save-csv" in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("SAVE FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            idx_str = choice[len("ila-"):].split("-save-csv")[0]
            ila_idx = int(idx_str) - 1
            console.save_ila_data(ila_idx, fmt="csv")
        except ValueError:
            result_message(f"Invalid CSV save selection: {choice}")
        return True  # Always return True to continue menu loop
    
    # VIO commands (vio-1, vio-1-set-from-file, vio-1-set-hex)
    elif choice.startswith("vio-") and "-set-" not in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("READ FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            # Extract index from "vio-1" format
            idx_str = choice[len("vio-"):]
            vio_idx = int(idx_str) - 1
            # Check if VIO cores exist before trying to read
            vio_list = console._get_vio_list()
            if len(vio_list) == 0:
                result_message("READ FAILED - No VIO cores found (device may need to be programmed first)")
            else:
                # Read VIO and store last read values in device database
                last_values = console.print_vio_details(vio_idx, vio_outputs)
                _store_vio_last_values(console, vio_idx, last_values)
        except ValueError:
            result_message(f"Invalid VIO selection: {choice}")
        except Exception as e:
            result_message(f"READ FAILED - Error reading VIO: {str(e)}")
        return True  # Always return True to continue menu loop
    elif choice.startswith("vio-") and "-set-from-file" in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("SET FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        
        # Extract VIO index
        try:
            idx_str = choice[len("vio-"):].split("-set-from-file")[0]
            vio_idx = int(idx_str) - 1
        except ValueError:
            result_message(f"Invalid VIO set-from-file selection: {choice}")
            return True
        
        # Build confirmation details
        invoked_cwd_local = _menu_db.get('invoked_cwd', '') or invoked_cwd or ''
        device_name = _get_device_name_by_dna(console.selected_device_dna, invoked_cwd_local)
        
        details = [
            f"Device: {device_name or console.selected_device_dna}",
            f"DNA: {console.selected_device_dna}",
            f"VIO Index: {vio_idx + 1}",
        ]
        
        # Show config file info
        if config_path:
            details.append(f"Config: {os.path.basename(config_path)}")
        
        # Show VIO values that will be set
        if vio_outputs:
            details.append("Values to set:")
            for probe_name, value in vio_outputs.items():
                details.append(f"  {probe_name} = {value}")
        
        warnings = []
        
        # Check DNA mismatch with config
        if console.selected_device_dna and console.config_device_dna:
            selected_clean = console.selected_device_dna.strip('0') or '0'
            config_clean = console.config_device_dna.strip('0') or '0'
            if selected_clean.upper() != config_clean.upper():
                warnings.append(f"Device DNA does not match config DNA!")
                warnings.append(f"  Selected: {console.selected_device_dna}")
                warnings.append(f"  Config:   {console.config_device_dna}")
        
        # Check if no VIO outputs defined
        if not vio_outputs:
            warnings.append("No VIO outputs defined in config file")
        
        # Ask for confirmation
        if not _confirm_action("SET VIO FROM CONFIG", details, warnings, force_flag):
            return True
        
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            _set_vio_values_for_index(console, vio_idx, vio_outputs, True)  # Already confirmed
        except ValueError:
            result_message(f"Invalid VIO set-from-file selection: {choice}")
    elif choice.startswith("vio-") and "-set-hex" in choice:
        # Check device selection cache BEFORE opening TCL console
        if not console.device_explicitly_selected:
            result_message("SET FAILED - Device must be explicitly selected first (use 'scan' then 'open <dna>')")
            return True
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            idx_str = choice[len("vio-"):].split("-set-hex")[0]
            vio_idx = int(idx_str) - 1
            _set_vio_values_manual(console, vio_idx)
        except ValueError:
            result_message(f"Invalid VIO set-hex selection: {choice}")
        return True  # Always return True to continue menu loop
    else:
        log_message(f"Invalid option: {choice}")
    
    return True


def _store_vio_last_values(console: VivadoTCLConsole, vio_idx: int, probes_data: list) -> None:
    """Store last read VIO values in device database for menu display.
    
    Args:
        console: VivadoTCLConsole instance
        vio_idx: VIO index (0-based)
        probes_data: List of probe data dicts from print_vio_details
    """
    if not probes_data or not console.selected_device_dna:
        return
    
    # Find device in cache and store values
    for dev in console.device_list_cache:
        if dev.get('dna') == console.selected_device_dna:
            # Initialize vio_last_values if not present
            if 'vio_last_values' not in dev:
                dev['vio_last_values'] = {}
            # Store values by VIO index - keep a summary of key probes
            summary = []
            for probe in probes_data[:5]:  # Keep first 5 probes for summary
                name = probe.get('name', '')
                val = probe.get('value', '')  # Value is stored in 'value' key
                if name and val and val != '-':
                    # Shorten name if too long
                    short_name = name.split('/')[-1][:12]
                    # Shorten value if too long
                    short_val = val[:10] if len(val) > 10 else val
                    summary.append(f"{short_name}={short_val}")
            dev['vio_last_values'][vio_idx] = summary
            break


def _set_vio_values_for_index(console: VivadoTCLConsole, vio_idx: int, 
                               vio_outputs: dict, force: bool) -> None:
    """Set VIO values for a specific VIO index using config values directly."""
    vio_list = console._get_vio_list()
    if vio_idx < 0 or vio_idx >= len(vio_list):
        log_message(f"  ERROR: Invalid VIO index {vio_idx + 1}")
        return
    
    if not vio_outputs:
        log_message("  ERROR: No VIO outputs configured in config file")
        log_message("  Add 'vio_outputs' section to your config.json")
        return
    
    # Collect values from config that have non-empty values
    values_to_set = []
    for name, cfg in vio_outputs.items():
        value = cfg.get('value', '')
        radix = cfg.get('radix', 'hex')
        width = cfg.get('width', '?')
        
        if value:
            values_to_set.append((name, value, radix, width))
    
    if not values_to_set:
        log_message("  ERROR: No values configured in config file")
        log_message("  Edit config.json and set 'value' fields in vio_outputs")
        return
    
    # Set values (each value is committed immediately)
    for name, value, radix, width in values_to_set:
        console.set_vio_value(name, value, radix, width=width, commit=False, force=True)

    # After setting values, show the updated VIO table (same format as view command),
    # but keep the header as "Set VIO" instead of "VIO".
    last_values = console.print_vio_details(vio_idx, vio_outputs, header_prefix="Set VIO")
    # Store last read values in device database for menu display
    _store_vio_last_values(console, vio_idx, last_values)
    vio_info = vio_list[vio_idx]
    result_message(f"VIO SET COMPLETE - {vio_info['name']} (set {len(values_to_set)} values from config)")


def _set_vio_values_manual(console: VivadoTCLConsole, vio_idx: int) -> None:
    """Interactively set VIO values by hand (hex only) for a specific VIO index."""
    vio_list = console._get_vio_list()
    if vio_idx < 0 or vio_idx >= len(vio_list):
        result_message(f"ERROR: Invalid VIO index {vio_idx + 1}")
        return

    vio_info = vio_list[vio_idx]
    probe_names = vio_info.get("probe_names", [])
    probe_widths = vio_info.get("probe_widths", {})
    probe_directions = vio_info.get("probe_directions", {})

    # Collect output probes
    output_probes = []
    for name in probe_names:
        if probe_directions.get(name) == "output":
            width = probe_widths.get(name)
            width_str = f"[{width-1}:0]" if isinstance(width, int) and width > 1 else "[0]"
            output_probes.append((name, width_str))

    if not output_probes:
        result_message("No output probes available to set")
        return

    # Display available probes (always visible, not just in debug mode)
    print(f"\n--- Set VIO (manual): {vio_info['name']} ---")
    print("Available output probes:")
    for name, width_str in output_probes:
        print(f"  - {name} {width_str}")

    while True:
        probe_name = input("\nEnter probe name to set (or empty to finish): ").strip()
        if not probe_name:
            break
        # Check if probe name is in the list (compare with name from tuple)
        probe_found = None
        for name, _ in output_probes:
            if name == probe_name:
                probe_found = name
                break
        
        if not probe_found:
            print(f"Invalid probe name or not an output probe. Available: {', '.join([n for n, _ in output_probes])}")
            continue

        raw_val = input(f"Enter hex value for {probe_name} (e.g. 0x20 or 20): ").strip()
        if not raw_val:
            print("Empty value, skipped.")
            continue

        # Strip 0x prefix and spaces, validate hex
        v = raw_val.strip()
        if v.lower().startswith("0x"):
            v = v[2:]
        v = v.replace(" ", "")
        try:
            int(v, 16)
        except ValueError:
            print("Invalid hex value, try again.")
            continue

        width = probe_widths.get(probe_name)
        # Use radix 'hex'; set_vio_value will pad and commit, and verify via read-back
        if not console.set_vio_value(probe_name, v, radix="hex", width=width, commit=False, force=True):
            result_message("Failed to set value, see errors above")

    # After manual updates, show updated table with explicit header
    last_values = console.print_vio_details(vio_idx, vio_outputs=None, header_prefix="Set VIO")
    # Store last read values in device database for menu display
    _store_vio_last_values(console, vio_idx, last_values)
    vio_info = vio_list[vio_idx]
    result_message(f"VIO SET COMPLETE - {vio_info['name']} (values set manually)")


def _show_ila_vio_submenu(console: VivadoTCLConsole, vio_outputs: dict = None, 
                          server_ip: str = 'localhost', server_port: str = '3121') -> None:
    """Show submenu after scanning to choose ILA or VIO to read."""
    ila_list = console._get_ila_list()
    vio_list = console._get_vio_list()
    
    # If no ILA or VIO found, don't show submenu
    if not ila_list and not vio_list:
        return
    
    print()
    print("=" * 60)
    print(" SUBMENU: Read ILA/VIO")
    print("=" * 60)
    print()
    
    menu_lines = []
    if ila_list:
        menu_lines.append("ILA cores:")
        for i, ila in enumerate(ila_list):
            idx = i + 1
            menu_lines.append(f"  ila-{idx}  Read ILA {idx}: {ila['name']}")
        menu_lines.append("")
    
    if vio_list:
        menu_lines.append("VIO cores:")
        for i, vio in enumerate(vio_list):
            idx = i + 1
            menu_lines.append(f"  vio-{idx}  Read VIO {idx}: {vio['name']}")
        menu_lines.append("")
    
    menu_lines.append("q.  Back to main menu")
    
    for line in menu_lines:
        print(line)
    
    print("=" * 60)
    print()
    print(" Select an option: ", end="", flush=True)
    
    try:
        sub_choice = input().strip().lower()
        print()
        
        if sub_choice == 'q' or sub_choice == '':
            return
        
        # Handle ILA selection
        if sub_choice.startswith("ila-"):
            try:
                ila_idx = int(sub_choice[len("ila-"):]) - 1
                if 0 <= ila_idx < len(ila_list):
                    console.print_ila_details(ila_idx)
                else:
                    result_message(f"Invalid ILA index: {sub_choice}")
            except ValueError:
                result_message(f"Invalid ILA selection: {sub_choice}")
        
        # Handle VIO selection
        elif sub_choice.startswith("vio-"):
            try:
                vio_idx = int(sub_choice[len("vio-"):]) - 1
                if 0 <= vio_idx < len(vio_list):
                    console.print_vio_details(vio_idx, vio_outputs)
                else:
                    result_message(f"Invalid VIO index: {sub_choice}")
            except ValueError:
                result_message(f"Invalid VIO selection: {sub_choice}")
        else:
            result_message(f"Invalid selection: {sub_choice}")
    
    except (KeyboardInterrupt, EOFError):
        print()
        return


def _verify_checkout_files_intact() -> bool:
    """Verify that checked out files still exist and haven't been modified.
    
    Returns True if all checked out files exist and have the same modification time
    as when they were checked out, False otherwise.
    """
    pulled_files = _menu_db.get('pulled_files', {})
    if not pulled_files:
        return False
    
    for filepath, original_mtime in pulled_files.items():
        if not os.path.exists(filepath):
            return False
        current_mtime = os.path.getmtime(filepath)
        # Allow small tolerance for floating point comparison
        if abs(current_mtime - original_mtime) > 0.01:
            return False
    
    return True


def _get_git_status_info(invoked_cwd: str, file_version: str) -> dict:
    """Get git status information for the release folder.
    
    Returns dict with:
        - 'tag_match': True if file version matches a git tag
        - 'matching_tag': Name of matching tag (if any)
        - 'working_clean': True if release folder has no uncommitted changes
        - 'status_lines': List of status strings
    """
    import subprocess
    
    result = {
        'tag_match': False,
        'matching_tag': '',
        'working_clean': True,
        'status_lines': []
    }
    
    if not invoked_cwd or not os.path.isdir(invoked_cwd):
        result['status_lines'].append("(no folder)")
        return result
    
    try:
        # Find git root
        git_root_result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=invoked_cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if git_root_result.returncode != 0:
            result['status_lines'].append("(not a git repo)")
            return result
        
        git_root = git_root_result.stdout.strip()
        
        # Check if file version matches a git tag
        if file_version:
            # Get all tags
            tags_result = subprocess.run(
                ['git', 'tag', '-l'],
                cwd=git_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if tags_result.returncode == 0:
                tags = tags_result.stdout.strip().split('\n')
                for tag in tags:
                    tag = tag.strip()
                    # Check if tag matches or contains the version
                    if tag == file_version or file_version in tag or tag in file_version:
                        result['tag_match'] = True
                        result['matching_tag'] = tag
                        break
        
        # Check git status for the release folder (uncommitted changes)
        # Get relative path from git root
        rel_path = os.path.relpath(invoked_cwd, git_root)
        
        status_result = subprocess.run(
            ['git', 'status', '--porcelain', '--', rel_path],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        if status_result.returncode == 0:
            status_output = status_result.stdout.strip()
            if status_output:
                result['working_clean'] = False
                # Parse status lines
                for line in status_output.split('\n'):
                    if line.strip():
                        # Format: XY filename
                        status_code = line[:2]
                        filename = os.path.basename(line[3:].strip())
                        if status_code == '??':
                            result['status_lines'].append(f"{filename}: untracked")
                        elif status_code[0] == 'M' or status_code[1] == 'M':
                            result['status_lines'].append(f"{filename}: modified")
                        elif status_code[0] == 'A':
                            result['status_lines'].append(f"{filename}: added")
                        elif status_code[0] == 'D' or status_code[1] == 'D':
                            result['status_lines'].append(f"{filename}: deleted")
                        else:
                            result['status_lines'].append(f"{filename}: {status_code.strip()}")
        
    except subprocess.TimeoutExpired:
        result['status_lines'].append("(git timeout)")
    except Exception as e:
        result['status_lines'].append(f"(git error)")
    
    return result


def _get_pull_status() -> tuple:
    """Check if release folder matches the checked out tag using git diff.
    
    Returns:
        (tag_matches: bool, status_lines: list)
        - tag_matches: True if release folder matches the tag exactly
        - status_lines: List of status strings for differences
    """
    last_pulled_tag = _menu_db.get('last_pulled_tag', '')
    release_dir = _menu_db.get('invoked_cwd', '')
    
    if not last_pulled_tag or not release_dir:
        return False, []
    
    status_lines = []
    
    try:
        # Find git root
        git_root_result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=release_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if git_root_result.returncode != 0:
            return False, ["(git error)"]
        
        git_root = git_root_result.stdout.strip()
        rel_path = os.path.relpath(release_dir, git_root)
        
        # Use git diff to compare release folder against the tag
        diff_result = subprocess.run(
            ['git', 'diff', '--name-only', last_pulled_tag, '--', rel_path],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if diff_result.returncode != 0:
            return False, ["(diff error)"]
        
        diff_output = diff_result.stdout.strip()
        if not diff_output:
            # No differences - tag matches
            return True, []
        
        # Parse diff output
        for line in diff_output.split('\n'):
            if line.strip():
                filename = os.path.basename(line.strip())
                status_lines.append(f"{filename}: modified")
        
        return False, status_lines
        
    except Exception as e:
        return False, [f"(error: {e})"]


def _verify_bitstream_matches_config(bitstream_path: str, config_version: str, config_timestamp: str) -> bool:
    """Verify that bitstream file's USR_ACCESS/USERID match config version/timestamp.
    
    Args:
        bitstream_path: Path to bitstream file
        config_version: Version string from config (e.g., "v1.6.0")
        config_timestamp: Timestamp string from config (e.g., "2026-01-16 14:54")
    
    Returns:
        True if matches or no config values specified, False if mismatch
    """
    # If no config values specified, nothing to verify
    if not config_version and not config_timestamp:
        return True
    
    # Read USR_ACCESS and USERID from bitstream
    try:
        bit_usr_access = _read_usr_access_value(bitstream_path)
        bit_userid = _read_userid_raw(bitstream_path)
    except Exception as e:
        result_message(f"VERIFY WARNING - Could not read bitstream values: {e}")
        return True  # Don't fail if we can't read
    
    all_match = True
    
    # Verify version (USR_ACCESS)
    if config_version and bit_usr_access is not None:
        # Decode USR_ACCESS to version string
        bit_version = _decode_version(bit_usr_access)
        if bit_version != config_version:
            result_message(f"VERIFY MISMATCH - Version: config={config_version}, bitstream={bit_version}")
            all_match = False
        else:
            result_message(f"VERIFY OK - Version: {config_version}")
    
    # Verify timestamp (USERID)
    if config_timestamp and bit_userid is not None:
        # Decode USERID to timestamp string
        bit_timestamp = _decode_timestamp(bit_userid)
        if bit_timestamp != config_timestamp:
            result_message(f"VERIFY MISMATCH - Timestamp: config={config_timestamp}, bitstream={bit_timestamp}")
            all_match = False
        else:
            result_message(f"VERIFY OK - Timestamp: {config_timestamp}")
    
    return all_match


def _scan_config_files(invoked_cwd: str) -> list:
    """Scan for JSON config files in the invoked folder.
    
    Returns list of config file names (relative to invoked_cwd).
    """
    config_files = []
    if invoked_cwd and os.path.isdir(invoked_cwd):
        for f in os.listdir(invoked_cwd):
            if f.endswith('.json') and os.path.isfile(os.path.join(invoked_cwd, f)):
                config_files.append(f)
    return sorted(config_files)


def _get_device_name_by_dna(dna: str, invoked_cwd: str) -> str:
    """Get device name by searching all config files for matching DNA.
    
    The device name is derived from the config filename (without .json extension).
    
    Args:
        dna: Device DNA to search for
        invoked_cwd: Directory containing config files
        
    Returns:
        Config filename (without .json) if DNA match found, empty string otherwise
    """
    if not dna or not invoked_cwd:
        return ""
    
    dna_clean = dna.lstrip('0').upper() or '0'
    
    config_files = _scan_config_files(invoked_cwd)
    for cfg_filename in config_files:
        try:
            cfg_path = os.path.join(invoked_cwd, cfg_filename)
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r') as f:
                    cfg_data = json.load(f)
                
                # Extract DNA from config (supports single-DNA and multi-DNA formats)
                if 'dna' in cfg_data:
                    # Single-DNA format
                    cfg_dna = cfg_data.get('dna', '').lstrip('0').upper() or '0'
                    if dna_clean == cfg_dna:
                        # Return filename without .json extension
                        return cfg_filename[:-5] if cfg_filename.endswith('.json') else cfg_filename
                else:
                    # Multi-DNA format: keys are DNA values
                    for key in cfg_data.keys():
                        if isinstance(cfg_data.get(key), dict) and key not in ['hw_server_host', 'hw_server_port', 'bit_file', 'ltx_file', 'device']:
                            cfg_dna = key.lstrip('0').upper() or '0'
                            if dna_clean == cfg_dna:
                                return cfg_filename[:-5] if cfg_filename.endswith('.json') else cfg_filename
        except (json.JSONDecodeError, IOError):
            pass  # Skip invalid config files
    
    return ""


def _expand_path(path: str, invoked_cwd: str) -> str:
    """Expand environment variables and resolve path relative to invoked_cwd.
    
    Args:
        path: Path string (may contain env vars like $HOME or ${VAR})
        invoked_cwd: Base directory for relative paths
        
    Returns:
        Absolute path with env vars expanded
    """
    # Expand environment variables
    expanded = os.path.expandvars(path)
    expanded = os.path.expanduser(expanded)
    
    # If relative, make absolute relative to invoked_cwd
    if not os.path.isabs(expanded):
        expanded = os.path.join(invoked_cwd, expanded)
    
    return os.path.abspath(expanded)


def _perform_scan(console: VivadoTCLConsole, bitstream: str, probes: str, 
                  server_ip: str = 'localhost', server_port: str = '3121') -> bool:
    """Perform full JTAG scan and update menu database.
    
    Scans JTAG chain, reads DNA and USR_ACCESS/USERID from each device,
    reads USR_ACCESS from bitstream files, and updates _menu_db.
    
    Returns True on success, False on failure.
    """
    global _menu_db
    
    # Ensure console is started and connected
    if not _ensure_console_started(console, server_ip, server_port):
        result_message("SCAN FAILED - Could not connect to hardware server")
        return False
    
    # 1. Scan JTAG chain for devices
    result = console.scan_jtag()
    if not result:
        result_message("SCAN FAILED - JTAG scan failed")
        return False
    
    # 2. Get device list from cache
    device_list = console.device_list_cache
    
    # 3. Loop over each device, read DNA and USR_ACCESS
    scanned_devices = []
    for i, dev in enumerate(device_list):
        dev_dna = dev.get('dna', '')
        target_idx = dev.get('target_idx', 0)
        device_idx = dev.get('device_idx', 0)
        target_name = dev.get('target_name', '')
        dev_name = dev.get('name', '')
        
        # Get device name by searching config files for DNA match
        invoked_cwd = _menu_db.get('invoked_cwd', '')
        device_display_name = _get_device_name_by_dna(dev_dna, invoked_cwd)
        
        # Read USR_ACCESS and USERID from device
        usr_access_value = None
        userid_value = None
        try:
            # Open target and select device to read USR_ACCESS
            console.send_command("set all_targets [get_hw_targets]", timeout=5)
            console.send_command("foreach t $all_targets { if {[get_property IS_OPEN $t]} { close_hw_target $t } }", timeout=5)
            console.send_command("set all_targets [get_hw_targets]", timeout=5)
            console.send_command(f"set target [lindex $all_targets {target_idx}]", timeout=2)
            console.send_command("open_hw_target $target", timeout=10)
            console.send_command("set devices [get_hw_devices]", timeout=5)
            console.send_command(f"set device [lindex $devices {device_idx}]", timeout=2)
            console.send_command("current_hw_device $device", timeout=2)
            console.send_command("refresh_hw_device $device", timeout=10)
            
            # Read USR_ACCESS (version)
            usr_access_value = _read_usr_access_from_device_value(console)
            # Read USERID (timestamp)
            userid_value = _read_userid_from_device_value(console)
        except Exception as e:
            log_message(f"Could not read USR_ACCESS/USERID from device {i}: {e}")
        
        # Format decoded display string
        decoded_str = _format_version_and_timestamp(usr_access_value, userid_value)
        
        scanned_devices.append({
            'dna': dev_dna,
            'name': device_display_name,
            'usr_access': usr_access_value,
            'userid': userid_value,
            'decoded': decoded_str,
            'target_idx': target_idx,
            'device_idx': device_idx,
            'target_name': target_name,
            'dev_name': dev_name,
            'ila_list': [],
            'vio_list': [],
        })
    
    # 4. Read USR_ACCESS and USERID from bitstream files
    scanned_files = []
    if bitstream and os.path.exists(bitstream):
        filename = os.path.basename(bitstream)
        usr_access_value = _read_usr_access_value(bitstream)
        userid_value = _read_userid_raw(bitstream)
        decoded_str = _format_version_and_timestamp(usr_access_value, userid_value)
        scanned_files.append({
            'filename': filename,
            'usr_access': usr_access_value,
            'userid': userid_value,
            'decoded': decoded_str,
            'path': bitstream,
        })
        # Cache for display
        console.bitstream_usr_access = usr_access_value
        console.bitstream_userid = userid_value
    
    if probes and os.path.exists(probes):
        filename = os.path.basename(probes)
        scanned_files.append({
            'filename': filename,
            'usr_access': None,  # .ltx files don't have USR_ACCESS
            'userid': None,
            'decoded': '',
            'path': probes,
        })
    
    # 5. Update menu database
    _menu_db['devices'] = scanned_devices
    _menu_db['files'] = scanned_files
    _menu_db['scanned'] = True
    
    # Update console cache to match menu database
    console.device_list_cache = scanned_devices
    
    result_message(f"SCAN COMPLETE - {len(scanned_devices)} device(s), {len(scanned_files)} file(s)")
    return True


def _draw_menu_table(console: VivadoTCLConsole, vio_outputs: dict = None) -> None:
    """Draw the menu table using prettytable based on _menu_db.
    
    Each column represents a category of information:
    - Program: files in folder with version and timestamps
    - VIO/ILA: list of VIO/ILA actions/commands  
    - JTAG Chain: list of devices
    - Config Files: list of config files
    - Device: opened device
    - HW Server: ip:port
    - Commands: available commands
    """
    global _menu_db
    
    # Scan for config files in invoked folder
    invoked_cwd = _menu_db.get('invoked_cwd', '')
    if invoked_cwd and not _menu_db.get('config_files'):
        _menu_db['config_files'] = _scan_config_files(invoked_cwd)
    
    # Get selected device data
    selected_device = None
    selected_dna = _menu_db.get('selected_dna', '') or (console.selected_device_dna if hasattr(console, 'selected_device_dna') else '')
    if selected_dna:
        for dev in _menu_db.get('devices', []):
            if dev.get('dna') == selected_dna:
                selected_device = dev
                break
    
    # Build ILA options
    ila_list = selected_device.get('ila_list', []) if selected_device else []
    
    # Build VIO options  
    vio_list = selected_device.get('vio_list', []) if selected_device else []
    
    # Get config info
    loaded_config = _menu_db.get('loaded_config', '')
    hw_server_ip = _menu_db.get('hw_server_ip', 'localhost')
    hw_server_port = _menu_db.get('hw_server_port', '3121')
    hw_server_str = f"{hw_server_ip}:{hw_server_port}"
    
    # ===== BUILD COLUMN CONTENT =====
    
    # --- Program File column: .bit and .ltx files in folder ---
    # If no files in menu_db, scan the invoked folder for .bit and .ltx files
    if not _menu_db.get('files') and invoked_cwd and os.path.isdir(invoked_cwd):
        files_in_folder = []
        for f in sorted(os.listdir(invoked_cwd)):
            filepath = os.path.join(invoked_cwd, f)
            if os.path.isfile(filepath) and (f.endswith('.bit') or f.endswith('.ltx')):
                decoded = ''
                if f.endswith('.bit'):
                    try:
                        usr_access = _read_usr_access_value(filepath)
                        userid = _read_userid_raw(filepath)
                        version = _decode_version(usr_access) if usr_access else ''
                        timestamp = _decode_timestamp(userid) if userid else ''
                        if version or timestamp:
                            decoded = f"{version} ({timestamp})" if version and timestamp else (version or timestamp)
                    except:
                        pass
                files_in_folder.append({'filename': f, 'path': filepath, 'decoded': decoded})
        _menu_db['files'] = files_in_folder
    
    program_lines = []
    for f in _menu_db.get('files', []):
        filename = f.get('filename', '')
        filepath = f.get('path', '')
        decoded = f.get('decoded', '')
        
        if filename.endswith('.bit'):
            label = "bit"
        elif filename.endswith('.ltx'):
            label = "ltx"
        else:
            label = "file"
        
        # Check if file exists
        file_exists = filepath and os.path.exists(filepath)
        if not file_exists and invoked_cwd:
            # Try to find in invoked folder
            check_path = os.path.join(invoked_cwd, filename)
            file_exists = os.path.exists(check_path)
        
        if file_exists:
            display = f"{label}: {filename}"
            if decoded:
                display += f"\n     {decoded}"
            else:
                display += "\n     (no ver/time)"
        else:
            display = f"{label}: {filename}\n     (FILE NOT FOUND)"
        
        program_lines.append(display)
    
    # Add verification status: compare config vs bitstream file
    config_version = _menu_db.get('config_version', '')
    config_timestamp = _menu_db.get('config_timestamp', '')
    config_bitstream = _menu_db.get('config_bitstream', '')
    
    if loaded_config:
        # Config is loaded - show verification section
        program_lines.append("---")
        program_lines.append("[Config vs File]")
        
        if (config_version or config_timestamp) and config_bitstream and invoked_cwd:
            bitstream_path = os.path.join(invoked_cwd, config_bitstream)
            if os.path.exists(bitstream_path):
                try:
                    bit_usr_access = _read_usr_access_value(bitstream_path)
                    bit_userid = _read_userid_raw(bitstream_path)
                    verify_lines = []
                    if config_version and bit_usr_access is not None:
                        bit_version = _decode_version(bit_usr_access)
                        if bit_version != config_version:
                            verify_lines.append(f"ver: MISMATCH")
                            verify_lines.append(f"  cfg:  {config_version}")
                            verify_lines.append(f"  file: {bit_version}")
                        else:
                            verify_lines.append(f"ver: OK ({config_version})")
                    if config_timestamp and bit_userid is not None:
                        bit_timestamp = _decode_timestamp(bit_userid)
                        if bit_timestamp != config_timestamp:
                            verify_lines.append(f"time: MISMATCH")
                            verify_lines.append(f"  cfg:  {config_timestamp}")
                            verify_lines.append(f"  file: {bit_timestamp}")
                        else:
                            verify_lines.append(f"time: OK ({config_timestamp})")
                    if verify_lines:
                        program_lines.extend(verify_lines)
                except Exception:
                    program_lines.append("(read error)")
            else:
                program_lines.append("(file not found)")
        else:
            program_lines.append("(no ver/time in config)")
    
    # Add checkout status
    last_pulled_tag = _menu_db.get('last_pulled_tag', '')
    if last_pulled_tag:
        tag_matches, status_lines = _get_pull_status()
        program_lines.append("---")
        if tag_matches:
            program_lines.append(f"tag: {last_pulled_tag}")
        else:
            program_lines.append(f"tag: {last_pulled_tag} (changed)")
            program_lines.extend(status_lines)
    
    # --- VIO/ILA column: show core names and available commands ---
    vio_ila_lines = []
    config_loaded = bool(_menu_db.get('loaded_config', ''))
    
    if ila_list:
        vio_ila_lines.append("ILA:")
        for i, ila in enumerate(ila_list):
            idx = i + 1
            ila_name = ila.get('name', f'ila_{idx}')
            vio_ila_lines.append(f"  {ila_name}")
            vio_ila_lines.append(f"    ila-{idx}")
    if vio_list:
        if vio_ila_lines:
            vio_ila_lines.append("")
        vio_ila_lines.append("VIO:")
        for i, vio in enumerate(vio_list):
            idx = i + 1
            vio_name = vio.get('name', f'vio_{idx}')
            probe_count = vio.get('probe_count', 0)
            vio_ila_lines.append(f"  {vio_name} ({probe_count} probes)")
            vio_ila_lines.append(f"    vio-{idx}          (read)")
            vio_ila_lines.append(f"    vio-{idx}-set-hex  (set manual)")
            if config_loaded:
                vio_ila_lines.append(f"    vio-{idx}-set-from-file")
    
    # --- JTAG Chain column: list of devices ---
    # Build a map of DNA -> config filename by reading each config file
    dna_to_config = {}
    invoked_cwd = _menu_db.get('invoked_cwd', '')
    for cfg_filename in _menu_db.get('config_files', []):
        try:
            cfg_path = os.path.join(invoked_cwd, cfg_filename) if invoked_cwd else cfg_filename
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r') as f:
                    cfg_data = json.load(f)
                # Extract DNA from config (supports single-DNA and multi-DNA formats)
                if 'dna' in cfg_data:
                    # Single-DNA format
                    cfg_dna = cfg_data.get('dna', '').lstrip('0').upper() or '0'
                    dna_to_config[cfg_dna] = cfg_filename
                else:
                    # Multi-DNA format: keys are DNA values
                    for key in cfg_data.keys():
                        if isinstance(cfg_data.get(key), dict) and key not in ['hw_server_host', 'hw_server_port', 'bit_file', 'ltx_file', 'device']:
                            cfg_dna = key.lstrip('0').upper() or '0'
                            dna_to_config[cfg_dna] = cfg_filename
        except (json.JSONDecodeError, IOError):
            pass  # Skip invalid config files
    
    jtag_lines = []
    for dev in _menu_db.get('devices', []):
        dev_dna = dev.get('dna', '')
        decoded = dev.get('decoded', '')
        
        jtag_lines.append(f"dna: {dev_dna}")
        if decoded:
            jtag_lines.append(f"  {decoded}")
        
        # Check if this device's DNA matches any config file
        dev_dna_clean = dev_dna.lstrip('0').upper() or '0'
        if dev_dna_clean in dna_to_config:
            jtag_lines.append(f"  -> {dna_to_config[dev_dna_clean]}")
        
        if _menu_db.get('devices', []).index(dev) < len(_menu_db.get('devices', [])) - 1:
            jtag_lines.append("---")
    
    # --- Config Files column: list of config files with summary ---
    config_lines = []
    invoked_cwd_cfg = _menu_db.get('invoked_cwd', '')
    config_files_list = _menu_db.get('config_files', [])
    for cfg_idx, cfg in enumerate(config_files_list):
        is_loaded = loaded_config and os.path.basename(loaded_config) == cfg
        
        # Read config file to get summary
        cfg_summary = []
        try:
            cfg_path = os.path.join(invoked_cwd_cfg, cfg) if invoked_cwd_cfg else cfg
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r') as f:
                    cfg_data = json.load(f)
                
                # Get DNA
                cfg_dna = cfg_data.get('dna', '')
                if cfg_dna:
                    cfg_summary.append(f"  dna: {cfg_dna}")
                
                # Get HW server
                hw_host = cfg_data.get('hw_server_host', '')
                hw_port = cfg_data.get('hw_server_port', '')
                if hw_host:
                    cfg_summary.append(f"  server: {hw_host}:{hw_port}")
                
                # Get files
                files_cfg = cfg_data.get('files', {})
                bit_file = files_cfg.get('bit_file', '') or cfg_data.get('bit_file', '')
                ltx_file = files_cfg.get('ltx_file', '') or cfg_data.get('ltx_file', '')
                if bit_file:
                    cfg_summary.append(f"  bit: {bit_file}")
                if ltx_file:
                    cfg_summary.append(f"  ltx: {ltx_file}")
                
                # Get version
                cfg_version = cfg_data.get('version', '')
                if cfg_version:
                    cfg_summary.append(f"  ver: {cfg_version}")
                
                # Get VIO outputs with non-empty values
                vio_outputs = cfg_data.get('vio_outputs', {})
                vio_values = []
                for probe_name, probe_cfg in vio_outputs.items():
                    if isinstance(probe_cfg, dict):
                        value = probe_cfg.get('value', '')
                        if value:  # Only show non-empty values
                            vio_values.append(f"{probe_name}={value}")
                if vio_values:
                    cfg_summary.append(f"  vio: {', '.join(vio_values)}")
        except (json.JSONDecodeError, IOError):
            pass
        
        # Add config filename (compact: remove .json extension)
        cfg_display = cfg[:-5] if cfg.endswith('.json') else cfg
        if is_loaded:
            config_lines.append(f"{cfg_display} (loaded)")
        else:
            config_lines.append(f"{cfg_display}")
        
        # Add summary
        if cfg_summary:
            config_lines.extend(cfg_summary)
        
        # Add separator between configs (except after last one)
        if cfg_idx < len(config_files_list) - 1:
            config_lines.append("")
    
    # --- Device column: opened device ---
    device_lines = []
    if selected_device and selected_dna:
        dev_name = selected_device.get('name', '')
        if dev_name:
            device_lines.append(f"name: {dev_name}")
        device_lines.append(f"dna: {selected_dna}")
        decoded = selected_device.get('decoded', '')
        if decoded:
            device_lines.append(f"ver: {decoded}")
    else:
        device_lines.append("(none)")
    
    # --- HW Server column: ip:port ---
    hw_server_lines = [hw_server_str]
    
    # --- Commands column: all available commands ---
    commands_lines = [
        "server   - Set HW server",
        "scan     - Scan JTAG chain",
        "open <dna> - Open device",
        "load <cfg> - Load config",
        "---",
        "file-bit - Set bitstream",
        "file-ltx - Set probes",
        "program  - Program FPGA",
        "clear    - Clear FPGA",
        "checkout - Checkout release",
        "sleep <N> - Wait N seconds",
        "---",
        "q - Exit | m - Menu",
    ]
    
    # ===== CREATE TABLE =====
    table = PrettyTable()
    # Column headers: short names, commands shown in Commands column
    table.field_names = [
        "HW Server",
        "JTAG Chain", 
        "Program Files",
        "Opened Device", 
        "VIO/ILA",
        "Config Files",
        "Commands"
    ]
    table.align = "l"
    table.vrules = 1  # Vertical rules between columns
    
    # Determine VIO/ILA fallback message based on state
    if vio_ila_lines:
        vio_ila_content = "\n".join(vio_ila_lines)
    elif _menu_db.get('selected_dna'):
        # Device is selected but has no VIO/ILA cores
        vio_ila_content = "(none)"
    elif _menu_db.get('scanned') and _menu_db.get('devices'):
        # Scan done, devices found, but no device selected
        vio_ila_content = "(open <dna>)"
    else:
        vio_ila_content = "(scan first)"
    
    # Add single row with all content (order matches field_names)
    table.add_row([
        "\n".join(hw_server_lines),
        "\n".join(jtag_lines) if jtag_lines else "(scan first)",
        "\n".join(program_lines) if program_lines else "(no files)",
        "\n".join(device_lines),
        vio_ila_content,
        "\n".join(config_lines) if config_lines else "(no configs)",
        "\n".join(commands_lines),
    ])
    
    # Print table
    print("=" * 120)
    print(" HW Client Menu")
    print("=" * 120)
    print(table)
    print("=" * 120)
    print(" Select: ", end="", flush=True)


def _print_menu(console: VivadoTCLConsole, bitstream: str, probes: str, vio_outputs: dict = None) -> None:
    """Print the interactive menu using prettytable.
    
    Syncs menu database from console state, then draws the table.
    """
    global _menu_db
    
    # Sync menu database from console state
    # Update selected DNA
    if hasattr(console, 'selected_device_dna') and console.selected_device_dna:
        _menu_db['selected_dna'] = console.selected_device_dna
    
    # Update files if not already populated
    if not _menu_db.get('files'):
        files = []
        if bitstream and os.path.exists(bitstream):
            filename = os.path.basename(bitstream)
            usr_access_value = _read_usr_access_value(bitstream)
            userid_value = _read_userid_raw(bitstream)
            decoded_str = _format_version_and_timestamp(usr_access_value, userid_value)
            files.append({
                'filename': filename, 
                'usr_access': usr_access_value, 
                'userid': userid_value,
                'decoded': decoded_str,
                'path': bitstream
            })
            console.bitstream_usr_access = usr_access_value
            console.bitstream_userid = userid_value
        if probes and os.path.exists(probes):
            filename = os.path.basename(probes)
            files.append({
                'filename': filename, 
                'usr_access': None, 
                'userid': None,
                'decoded': '',
                'path': probes
            })
        _menu_db['files'] = files
    
    # Sync device list from console cache
    if console.device_list_cache and not _menu_db.get('devices'):
        devices = []
        invoked_cwd = _menu_db.get('invoked_cwd', '')
        for dev in console.device_list_cache:
            dev_dna = dev.get('dna', '')
            # Get device name by searching config files for DNA match
            device_display_name = _get_device_name_by_dna(dev_dna, invoked_cwd)
            # Get decoded version/timestamp
            usr_access_val = dev.get('usr_access')
            userid_val = dev.get('userid')
            decoded_str = dev.get('decoded', '') or _format_version_and_timestamp(usr_access_val, userid_val)
            devices.append({
                'dna': dev_dna,
                'name': device_display_name,
                'usr_access': usr_access_val,
                'userid': userid_val,
                'decoded': decoded_str,
                'target_idx': dev.get('target_idx', 0),
                'device_idx': dev.get('device_idx', 0),
                'ila_list': dev.get('ila_list', []),
                'vio_list': dev.get('vio_list', []),
            })
        _menu_db['devices'] = devices
    
    # Draw the table
    _draw_menu_table(console, vio_outputs)


def _print_prompt():
    """Print just the prompt without the menu."""
    print(" Select: ", end="", flush=True)


def _interactive_loop(console: VivadoTCLConsole, bitstream: str, probes: str, 
                      vio_outputs: dict = None, config_path: str = "",
                      server_ip: str = 'localhost', server_port: str = '3121',
                      invoked_cwd: str = None, cmd_buffer: list = None) -> None:
    """Run interactive menu loop. Console starts lazily when needed.
    
    Args:
        cmd_buffer: List of commands to process as if user typed them (from --cmd)
    """
    global _menu_db
    
    # Use lists to allow updates from menu choices (Python doesn't have pass-by-reference for strings)
    state = {
        'bitstream': bitstream,
        'probes': probes,
        'vio_outputs': vio_outputs or {},
        'server_ip': server_ip,
        'server_port': server_port,
        'config_path': config_path
    }
    
    # Store invoked_cwd and hw_server info in menu database
    _menu_db['invoked_cwd'] = invoked_cwd or os.getcwd()
    _menu_db['loaded_config'] = config_path
    _menu_db['hw_server_ip'] = server_ip
    _menu_db['hw_server_port'] = server_port
    _menu_db['config_bitstream'] = os.path.basename(bitstream) if bitstream else ''
    _menu_db['config_probes'] = os.path.basename(probes) if probes else ''
    # Load version/timestamp from config if available
    if config_path and os.path.exists(config_path):
        _, _, _, _, _, _, _, _, _, cfg_version, cfg_timestamp = _load_and_resolve_config(config_path, invoked_cwd, silent=True)
        _menu_db['config_version'] = cfg_version or ''
        _menu_db['config_timestamp'] = cfg_timestamp or ''
    
    # Initialize command buffer from cmd_buffer if provided
    cmd_queue = list(cmd_buffer) if cmd_buffer else []
    
    # Show menu initially
    menu_shown = False
    
    while True:
        # Show menu only initially or when user requests it with 'm' or 'menu'
        if not menu_shown:
            # Reload config before menu display if config_path exists (to pick up changes from checkout)
            if state['config_path'] and os.path.exists(state['config_path']):
                _, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, new_device_dna, _, _, new_version, new_timestamp = _load_and_resolve_config(state['config_path'], invoked_cwd, silent=True)
                if new_device_dna and new_device_dna.strip():
                    console.config_device_dna = new_device_dna
                if new_bitstream:
                    state['bitstream'] = new_bitstream
                    _menu_db['config_bitstream'] = os.path.basename(new_bitstream)
                if new_probes:
                    state['probes'] = new_probes
                    _menu_db['config_probes'] = os.path.basename(new_probes)
                if new_vio_outputs:
                    state['vio_outputs'] = new_vio_outputs
                if new_server_ip:
                    state['server_ip'] = new_server_ip
                    _menu_db['hw_server_ip'] = new_server_ip
                if new_server_port:
                    state['server_port'] = new_server_port
                    _menu_db['hw_server_port'] = new_server_port
                # Always update version/timestamp from config
                _menu_db['config_version'] = new_version or ''
                _menu_db['config_timestamp'] = new_timestamp or ''
            _print_menu(console, state['bitstream'], state['probes'], state['vio_outputs'])
            menu_shown = True
        
        # Get choice from buffer if available, otherwise from user input
        from_cmd_queue = False
        try:
            if cmd_queue:
                # Use command from buffer (simulate user input)
                choice = cmd_queue.pop(0).strip()
                from_cmd_queue = True
                # Print it as if user typed it
                print(choice, flush=True)
            else:
                # Wait for user input
                choice = input().strip()
            display_close_box()
        except (EOFError, KeyboardInterrupt):
            display_close_box()  # Close box even on interrupt
            break
        
        # Check if this is 'q' to exit
        if choice.lower() == 'q':
            break
        
        # Check if this is 'm' or 'menu' to show menu
        if choice.lower() in ('m', 'menu'):
            # Reload config before menu display if config_path exists (to pick up changes from checkout)
            if state['config_path'] and os.path.exists(state['config_path']):
                _, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, new_device_dna, _, _, new_version, new_timestamp = _load_and_resolve_config(state['config_path'], invoked_cwd, silent=True)
                if new_device_dna and new_device_dna.strip():
                    console.config_device_dna = new_device_dna
                if new_bitstream:
                    state['bitstream'] = new_bitstream
                if new_probes:
                    state['probes'] = new_probes
                if new_vio_outputs:
                    state['vio_outputs'] = new_vio_outputs
                if new_server_ip:
                    state['server_ip'] = new_server_ip
                if new_server_port:
                    state['server_port'] = new_server_port
            _print_menu(console, state['bitstream'], state['probes'], state['vio_outputs'])
            menu_shown = True  # Mark menu as shown again
            continue  # Loop back to get next input
        
        if not _execute_menu_choice(console, choice, state['bitstream'], state['probes'], state['vio_outputs'], 
                                   force=False, server_ip=state['server_ip'], server_port=state['server_port'], 
                                   invoked_cwd=invoked_cwd, config_path=state['config_path'],
                                   cmd_queue=cmd_queue):
            break
        
        # In batch mode (--cmd), exit immediately if command failed
        if from_cmd_queue and _last_command_failed:
            break
        
        # After device scan, selection, checkout, clear, or load, always reprint the full menu
        # - "load <file>" command loads new config
        # - "scan" command scans and shows device list
        # - "open <dna>" command selects and shows VIO/ILA options
        # - "checkout" command checks out release and re-scans
        # - "clear" command clears device and re-scans
        should_reprint_menu = (
            choice.lower().startswith("load ") or  # load <file>
            choice.lower().startswith("server") or  # server [ip:port]
            choice.lower().startswith("file-bit") or  # file-bit [path]
            choice.lower().startswith("file-ltx") or  # file-ltx [path]
            choice.startswith("open ") or  # open <dna>
            choice in ("2", "jt", "jtag", "scan", "scan_jtag") or  # device scan
            choice in ("5", "co", "checkout", "checkout_release") or  # checkout
            choice in ("6", "cl", "clear", "clear_fpga")  # clear
        )
        
        # If load command was executed, update state from menu database
        if choice.lower().startswith("load ") and _menu_db.get('loaded_config'):
            loaded_config = _menu_db['loaded_config']
            _, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, _, _, _, new_version, new_timestamp = _load_and_resolve_config(loaded_config, invoked_cwd, silent=True)
            state['config_path'] = loaded_config
            if new_bitstream:
                state['bitstream'] = new_bitstream
            if new_probes:
                state['probes'] = new_probes
            if new_vio_outputs:
                state['vio_outputs'] = new_vio_outputs
            if new_server_ip:
                state['server_ip'] = new_server_ip
            if new_server_port:
                state['server_port'] = new_server_port
        
        if should_reprint_menu:
            # Reload config before menu display if config_path exists (to pick up changes)
            if state['config_path'] and os.path.exists(state['config_path']):
                _, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, new_device_dna, _, _, new_version, new_timestamp = _load_and_resolve_config(state['config_path'], invoked_cwd, silent=True)
                if new_device_dna and new_device_dna.strip():
                    console.config_device_dna = new_device_dna
                if new_bitstream:
                    state['bitstream'] = new_bitstream
                    _menu_db['config_bitstream'] = os.path.basename(new_bitstream)
                if new_probes:
                    state['probes'] = new_probes
                    _menu_db['config_probes'] = os.path.basename(new_probes)
                if new_vio_outputs:
                    state['vio_outputs'] = new_vio_outputs
                if new_server_ip:
                    state['server_ip'] = new_server_ip
                    _menu_db['hw_server_ip'] = new_server_ip
                if new_server_port:
                    state['server_port'] = new_server_port
                    _menu_db['hw_server_port'] = new_server_port
                # Always update version/timestamp from config
                _menu_db['config_version'] = new_version or ''
                _menu_db['config_timestamp'] = new_timestamp or ''
            _print_menu(console, state['bitstream'], state['probes'], state['vio_outputs'])
            menu_shown = True
        else:
            # After other operations, reprint just the prompt (not the full menu)
            _print_prompt()


def _read_usr_access_value(bitfile: str) -> Optional[int]:
    """Read USR_ACCESS value from bitstream file. Returns value or None."""
    try:
        with open(bitfile, 'rb') as f:
            data = f.read()
        
        # USR_ACCESS register write command patterns in Xilinx bitstreams
        cmd1 = bytes([0x30, 0x01, 0xA0, 0x01])
        cmd2 = bytes([0x30, 0x01, 0x60, 0x01])
        cmd3 = bytes([0x30, 0x02, 0x60, 0x01])
        
        value = None
        
        # Try pattern 1 first
        pos1 = data.find(cmd1)
        if pos1 != -1 and pos1 + 8 <= len(data):
            value_bytes = data[pos1 + 4:pos1 + 8]
            value = struct.unpack('>I', value_bytes)[0]
        
        # Try pattern 2
        if value is None:
            pos2 = data.find(cmd2)
            if pos2 != -1 and pos2 + 8 <= len(data):
                value_bytes = data[pos2 + 4:pos2 + 8]
                value = struct.unpack('>I', value_bytes)[0]
        
        # Try pattern 3
        if value is None:
            pos3 = data.find(cmd3)
            if pos3 != -1 and pos3 + 8 <= len(data):
                value_bytes = data[pos3 + 4:pos3 + 8]
                value = struct.unpack('>I', value_bytes)[0]
        
        return value
        
    except Exception:
        return None


def _read_userid_value(bitfile: str) -> Optional[int]:
    """Read USERID (timestamp) value from bitstream file. Returns value or None.
    
    The USERID is stored in the ASCII header of Xilinx bitstreams as 'UserID=XXXXXXXX'.
    Returns the first value found that looks like a valid Unix timestamp.
    If no valid timestamp found, returns None.
    """
    try:
        with open(bitfile, 'rb') as f:
            # Read header (first 1024 bytes should be enough)
            header = f.read(1024)
        
        # Search for UserID=XXXXXXXX pattern in header
        import re
        match = re.search(b'UserID=([0-9A-Fa-f]{8})', header)
        if match:
            userid_hex = match.group(1).decode('ascii')
            candidate = int(userid_hex, 16)
            # Valid range: 2020-01-01 to 2040-01-01 (1577836800 to 2208988800)
            if 1577836800 <= candidate <= 2208988800:
                return candidate
        
        return None
        
    except Exception:
        return None


def _read_userid_raw(bitfile: str) -> Optional[int]:
    """Read raw USERID value from bitstream file (no timestamp validation).
    
    The USERID is stored in the ASCII header of Xilinx bitstreams as 'UserID=XXXXXXXX'.
    """
    try:
        with open(bitfile, 'rb') as f:
            # Read header (first 1024 bytes should be enough)
            header = f.read(1024)
        
        # Search for UserID=XXXXXXXX pattern in header
        import re
        match = re.search(b'UserID=([0-9A-Fa-f]{8})', header)
        if match:
            userid_hex = match.group(1).decode('ascii')
            return int(userid_hex, 16)
        
        return None
        
    except Exception:
        return None


def _format_userid(userid: Optional[int]) -> str:
    """Format USERID as human-readable timestamp."""
    if userid is None:
        return "N/A"
    try:
        from datetime import datetime
        # Check if it's a valid Unix timestamp
        if 1577836800 <= userid <= 2208988800:
            dt = datetime.fromtimestamp(userid)
            return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} (0x{userid:08X})"
        else:
            return f"0x{userid:08X} (not a timestamp)"
    except Exception:
        return f"0x{userid:08X}"


def _decode_version(usr_access: int) -> str:
    """Decode USR_ACCESS value as version string (major.minor.patch).
    
    Format: 0xMMmmpppp where:
    - MM = major version (byte 2-3)
    - mm = minor version (byte 1)  
    - pppp = patch/build (byte 0)
    
    Example: 0x00010600 -> v1.6.0
    """
    if usr_access is None:
        return ""
    try:
        major = (usr_access >> 16) & 0xFFFF
        minor = (usr_access >> 8) & 0xFF
        patch = usr_access & 0xFF
        return f"v{major}.{minor}.{patch}"
    except Exception:
        return ""


def _decode_timestamp(userid: int) -> str:
    """Decode USERID value as timestamp if it's a valid Unix timestamp.
    
    Returns formatted date/time string or empty string if not a valid timestamp.
    """
    if userid is None:
        return ""
    try:
        from datetime import datetime
        # Check if it's a valid Unix timestamp (2020-01-01 to 2040-01-01)
        if 1577836800 <= userid <= 2208988800:
            dt = datetime.fromtimestamp(userid)
            return dt.strftime('%Y-%m-%d %H:%M')
        return ""
    except Exception:
        return ""


def _format_version_and_timestamp(usr_access: Optional[int], userid: Optional[int] = None) -> str:
    """Format USR_ACCESS and USERID as version and timestamp.
    
    Returns string like "v1.6.0" or "v1.6.0 (2024-01-20 15:30)"
    """
    parts = []
    
    if usr_access is not None:
        version = _decode_version(usr_access)
        if version:
            parts.append(version)
    
    if userid is not None:
        timestamp = _decode_timestamp(userid)
        if timestamp:
            parts.append(f"({timestamp})")
    
    return " ".join(parts) if parts else ""


def _read_userid_from_device_value(console) -> Optional[int]:
    """Read USERID value from device. Returns value or None."""
    try:
        if not console.connected:
            return None
        
        device = console.device
        if not device:
            return None
        
        # Refresh device to ensure current state
        console.send_command("refresh_hw_device $device", timeout=5)
        console.send_command("current_hw_device $device", timeout=2)
        
        value = None
        
        # Try USERID/USERCODE properties
        userid_properties = [
            "REGISTER.USERCODE.SLR0",   # UltraScale+ (reads BITSTREAM.CONFIG.USERID)
            "REGISTER.USERCODE",        # Other device families
            "BITSTREAM.CONFIG.USERID",  # Direct property (may not be readable from device)
        ]
        
        import re
        for prop_name in userid_properties:
            try:
                output = console.send_command(f"get_property {prop_name} $device", timeout=5)
                match = re.search(r'0x([0-9A-Fa-f]+)', output, re.IGNORECASE)
                if match:
                    value = int(match.group(1), 16)
                    break
            except:
                pass
        
        return value
        
    except Exception:
        return None


def _read_usr_access_from_device_value(console) -> Optional[int]:
    """Read USR_ACCESS value from device. Returns value or None."""
    try:
        if not console.connected:
            return None
        
        device = console.device
        if not device:
            return None
        
        # Refresh device to ensure current state
        console.send_command("refresh_hw_device $device", timeout=5)
        console.send_command("current_hw_device $device", timeout=2)
        
        value = None
        property_used = None
        
        # Try SLR-specific properties first (for UltraScale+)
        slr_properties = [
            "REGISTER.USR_ACCESS.SLR0",
            "REGISTER.USR_ACCESS.SLR1",
            "REGISTER.USR_ACCESS.SLR2",
            "REGISTER.USR_ACCESS.SLR3",
        ]
        
        for prop_name in slr_properties:
            try:
                output = console.send_command(f"get_property {prop_name} $device", timeout=5)
                import re
                match = re.search(r'0x([0-9A-Fa-f]+)', output, re.IGNORECASE)
                if match:
                    value = int(match.group(1), 16)
                    property_used = prop_name
                    break
            except:
                pass
        
        # Fallback to generic property
        if value is None:
            try:
                output = console.send_command("get_property REGISTER.USR_ACCESS $device", timeout=5)
                import re
                match = re.search(r'0x([0-9A-Fa-f]+)', output, re.IGNORECASE)
                if match:
                    value = int(match.group(1), 16)
                    property_used = "REGISTER.USR_ACCESS"
            except:
                pass
        
        # Alternative method: Access raw output before cleaning
        if value is None:
            try:
                import re
                import select
                import time
                
                for prop_name in ["REGISTER.USR_ACCESS.SLR0", "REGISTER.USR_ACCESS"]:
                    cmd = f"get_property {prop_name} $device"
                    os.write(console.master_fd, (cmd + '\n').encode())
                    
                    raw_output = ""
                    start_time = time.time()
                    while time.time() - start_time < 5:
                        ready, _, _ = select.select([console.master_fd], [], [], 0.1)
                        if ready and console.master_fd in ready:
                            try:
                                data = os.read(console.master_fd, 4096).decode('utf-8', errors='replace')
                                if data:
                                    raw_output += data
                                    if console.prompt in raw_output:
                                        break
                            except:
                                pass
                    
                    match = re.search(r'0x([0-9A-Fa-f]{1,8})', raw_output, re.IGNORECASE)
                    if match:
                        value = int(match.group(1), 16)
                        property_used = f"{prop_name} (raw TCL)"
                        break
            except:
                pass
        
        return value
        
    except Exception:
        return None


def _read_usr_access_from_device(console) -> bool:
    """Read USR_ACCESS and USERID values from the programmed FPGA device."""
    
    if not console.connected:
        log_message("[!x!] Not connected to hardware server")
        return False
    
    try:
        # Use selected device if available, otherwise find it
        if console.device:
            # Set device variable in TCL from selected device name
            device_name = console.device
            # Find the device object by name
            console.send_command("set devices [get_hw_devices]", timeout=2)
            console.send_command(f'set device [lindex [lsearch -all -inline $devices "*{device_name}*"] 0]', timeout=2)
            # If that didn't work, try finding by exact match
            console.send_command("set device_found 0", timeout=1)
            console.send_command("foreach d $devices { if {[get_property NAME $d] == \"$device_name\"} { set device $d; set device_found 1; break } }", timeout=3)
            # Fallback: use first device if exact match failed
            console.send_command("if {!$device_found} { set device [lindex $devices 0] }", timeout=2)
        else:
            # No device selected, use first device
            console.send_command("set devices [get_hw_devices]", timeout=2)
            console.send_command("set device [lindex $devices 0]", timeout=2)
            device_name = console.get_property_value("NAME", "$device", timeout=2)
            console.device = device_name
        
        # Ensure device is current and refreshed
        console.send_command("current_hw_device $device", timeout=2)
        console.send_command("refresh_hw_device $device", timeout=5)
        device = console.device or device_name or "xcvu9p_0"
        
        # Try multiple property names for USR_ACCESS
        # For UltraScale+ devices, USR_ACCESS is per SLR (Super Logic Region)
        property_names = [
            "REGISTER.USR_ACCESS.SLR0",  # Primary SLR for UltraScale+
            "REGISTER.USR_ACCESS.SLR1",
            "REGISTER.USR_ACCESS.SLR2",
            "REGISTER.USR_ACCESS.SLR3",
            "REGISTER.USR_ACCESS",  # Fallback for other device families
            "REGISTER.CONFIG.USR_ACCESS",
            "BITSTREAM.CONFIG.USR_ACCESS",
            "PROGRAM.USR_ACCESS"
        ]
        
        value = None
        property_used = None
        
        # First try using get_property_value helper
        for prop_name in property_names:
            try:
                result = console.get_property_value(prop_name, "$device", timeout=5)
                if result and not result.startswith("ERROR") and result.strip():
                    # Try to parse as hex or decimal
                    result_clean = result.strip()
                    if result_clean.startswith("0x"):
                        value = int(result_clean[2:], 16)
                    else:
                        try:
                            value = int(result_clean, 10)
                        except:
                            try:
                                value = int(result_clean, 16)
                            except:
                                pass
                    
                    if value is not None:
                        property_used = prop_name
                        break
            except:
                continue
        
        # Alternative method: Access raw output before cleaning
        # We need to bypass the output cleaning that filters out get_property results
        if value is None:
            try:
                import re
                import select
                import time
                
                for prop_name in property_names:
                    # Send command directly to get raw output
                    cmd = f"get_property {prop_name} $device"
                    if console.debug:
                        log_message(f"  [DEBUG] Sending raw command: {cmd}")
                    
                    # Write command directly
                    os.write(console.master_fd, (cmd + '\n').encode())
                    
                    # Read raw output before cleaning
                    raw_output = ""
                    start_time = time.time()
                    while time.time() - start_time < 5:
                        ready, _, _ = select.select([console.master_fd], [], [], 0.1)
                        if ready and console.master_fd in ready:
                            try:
                                data = os.read(console.master_fd, 4096).decode('utf-8', errors='replace')
                                if data:
                                    raw_output += data
                                    if console.prompt in raw_output:
                                        break
                            except:
                                pass
                    
                    if console.debug:
                        log_message(f"  [DEBUG] Raw output for {prop_name}: {repr(raw_output)}")
                    
                    # Parse raw output for hex value
                    match = re.search(r'0x([0-9A-Fa-f]{1,8})', raw_output, re.IGNORECASE)
                    if match:
                        value = int(match.group(1), 16)
                        property_used = f"{prop_name} (raw TCL)"
                        break
                    
                    # Also try decimal
                    matches = re.findall(r'\b([1-9]\d{0,9}|0)\b', raw_output)
                    for match_str in matches:
                        try:
                            test_val = int(match_str)
                            if 0 < test_val <= 0xFFFFFFFF:
                                value = test_val
                                property_used = f"{prop_name} (raw TCL decimal)"
                                break
                        except:
                            pass
                    if value is not None:
                        break
            except Exception as e:
                if console.debug:
                    log_message(f"  [DEBUG] Exception in raw TCL parsing: {e}")
                import traceback
                if console.debug:
                    traceback.print_exc()
                pass
        
        # Last resort: Try reading via scan_jtag method (some devices expose USR_ACCESS via JTAG)
        if value is None:
            try:
                # Some devices may need to read via JTAG USERCODE instruction
                # This is a fallback that might work for some FPGA families
                # Use selected device or first device
                if console.device:
                    console.send_command("set devices [get_hw_devices]", timeout=2)
                    console.send_command(f'set device [lindex [lsearch -all -inline $devices "*{console.device}*"] 0]', timeout=2)
                    console.send_command("if {![info exists device] || $device == \"\"} { set device [lindex $devices 0] }", timeout=2)
                else:
                    console.send_command("set device [lindex [get_hw_devices] 0]", timeout=2)
                output = console.send_command("puts [get_property REGISTER.USR_ACCESS $device]", timeout=5)
                import re
                match = re.search(r'0x([0-9A-Fa-f]+)', output, re.IGNORECASE)
                if match:
                    value = int(match.group(1), 16)
                    property_used = "REGISTER.USR_ACCESS (direct)"
            except:
                pass
        
        # Also read USERID from device
        userid_value = _read_userid_from_device_value(console)
        
        # Build RESULT message with both values (always show, even if None)
        if value is not None:
            major = (value >> 16) & 0xFF
            minor = (value >> 8) & 0xFF
            patch = value & 0xFF
            result_message(f"USR_ACCESS: V{major}.{minor}.{patch} (0x{value:08X})")
        else:
            result_message("USR_ACCESS: N/A (could not read from device)")
        
        if userid_value is not None:
            result_message(f"USERID: {_format_userid(userid_value)}")
        else:
            result_message("USERID: N/A (could not read from device)")
        
        # Return True if at least one value was read, False if both failed
        if value is None and userid_value is None:
            return False
        return True
            
    except Exception as e:
        result_message(f"READ FAILED - Error reading USR_ACCESS from device: {str(e)}")
        import traceback
        if console.debug:
            traceback.print_exc()
        return False


def _read_usr_access(bitfile: str) -> bool:
    """Read USR_ACCESS (version) and USERID (timestamp) from Xilinx .bit file."""
    log_message(f"Bitstream: {bitfile}")
    
    try:
        with open(bitfile, 'rb') as f:
            data = f.read()
        
        # USR_ACCESS register write command patterns in Xilinx bitstreams
        # Pattern 1: 0x30 0x01 0xA0 0x01 followed by 32-bit value (big-endian)
        cmd1 = bytes([0x30, 0x01, 0xA0, 0x01])
        cmd2 = bytes([0x30, 0x01, 0x60, 0x01])
        cmd3 = bytes([0x30, 0x02, 0x60, 0x01])
        
        usr_access_value = None
        usr_access_pattern = None
        usr_access_pos = None
        
        # Try USR_ACCESS patterns
        for cmd, pattern_name in [(cmd1, "0x3001A001"), (cmd2, "0x30016001"), (cmd3, "0x30026001")]:
            pos = data.find(cmd)
            if pos != -1 and pos + 8 <= len(data):
                value_bytes = data[pos + 4:pos + 8]
                usr_access_value = struct.unpack('>I', value_bytes)[0]
                usr_access_pattern = pattern_name
                usr_access_pos = pos
                break
        
        # Read USERID (timestamp)
        userid_value = _read_userid_value(bitfile)
        userid_raw = _read_userid_raw(bitfile) if userid_value is None else None
        
        # Display results - always show important data
        print()
        if usr_access_value is not None:
            major = (usr_access_value >> 16) & 0xFF
            minor = (usr_access_value >> 8) & 0xFF
            patch = usr_access_value & 0xFF
            result_message(f"USR_ACCESS: V{major}.{minor}.{patch} (0x{usr_access_value:08X})")
            log_message(f"  Pattern: {usr_access_pattern} at position {usr_access_pos}")
        else:
            result_message("USR_ACCESS: N/A")
        
        print()
        if userid_value is not None:
            result_message(f"USERID: {_format_userid(userid_value)}")
        elif userid_raw is not None:
            result_message(f"USERID: 0x{userid_raw:08X} (not a valid timestamp)")
        else:
            result_message("USERID: N/A")
        
        return usr_access_value is not None
        
    except FileNotFoundError:
        log_message(f"[!x!] Bitstream file not found: {bitfile}")
        result_message("BITSTREAM READ FAILED - File not found")
        return False
    except Exception as e:
        log_message(f"[!x!] Error reading bitstream: {e}")
        import traceback
        traceback.print_exc()
        result_message("BITSTREAM READ FAILED - Error reading file")
        return False


def _get_git_repo_root(project_dir: Path) -> Path:
    """Get git repo root from REPO_TOP environment variable (set by update_repo_path)."""
    # REPO_TOP must be set by update_repo_path
    repo_top = os.environ.get('REPO_TOP')
    if not repo_top:
        log_message("[!x!] REPO_TOP not set. Run 'update_repo_path' first.")
        sys.exit(1)
    
    # REPO_TOP may use ~ notation, expand it
    return Path(os.path.expanduser(repo_top))


def _get_project_paths(invoked_cwd: str) -> tuple:
    """Get project paths based on invoked directory."""
    # Try to find project root by looking for release/ directory
    current = Path(invoked_cwd).resolve()
    while current != current.parent:
        release_dir = current / "release"
        if release_dir.exists() and release_dir.is_dir():
            project_dir = current
            git_repo_root = _get_git_repo_root(project_dir)
            release_config = release_dir / "collect" / "release_config.json"
            hw_config = release_dir / "config.json"
            return project_dir, release_dir, git_repo_root, release_config, hw_config
        current = current.parent
    
    # Fallback: assume invoked_cwd is project root
    project_dir = Path(invoked_cwd)
    release_dir = project_dir / "release"
    git_repo_root = _get_git_repo_root(project_dir)
    release_config = release_dir / "collect" / "release_config.json"
    hw_config = release_dir / "config.json"
    return project_dir, release_dir, git_repo_root, release_config, hw_config


def _show_available_releases(project_dir: Path) -> List[str]:
    """Show available release tags and return list of tags."""
    print()
    print("=" * 80)
    print(" Available Release Tags")
    print("=" * 80)
    
    # Get list of version tags (V*)
    result = subprocess.run(
        ["git", "-C", str(project_dir), "tag", "-l", "V*", "--sort=-version:refname"],
        capture_output=True,
        text=True
    )
    
    tags = [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]
    
    if not tags:
        print("  No release tags found.")
        print("=" * 80)
        return []
    
    # Create table using PrettyTable
    table = PrettyTable()
    table.field_names = ["Tag", "Commit", "Date", "Message"]
    table.align = "l"
    
    for tag in tags:
        commit_result = subprocess.run(
            ["git", "-C", str(project_dir), "rev-list", "-n", "1", tag],
            capture_output=True,
            text=True
        )
        commit = commit_result.stdout.strip()[:12] if commit_result.returncode == 0 else "unknown"
        
        date_result = subprocess.run(
            ["git", "-C", str(project_dir), "log", "-1", "--format=%ci", tag],
            capture_output=True,
            text=True
        )
        date = " ".join(date_result.stdout.strip().split()[:2]) if date_result.returncode == 0 else "unknown"
        
        message_result = subprocess.run(
            ["git", "-C", str(project_dir), "tag", "-l", "--format=%(contents:subject)", tag],
            capture_output=True,
            text=True
        )
        message = message_result.stdout.strip()[:50] if message_result.returncode == 0 else "unknown"
        
        table.add_row([tag, commit, date, message])
    
    print(table)
    print("=" * 80)
    print()
    return tags


def _select_release_tag(project_dir: Path, cmd_queue: list = None) -> Optional[str]:
    """Select a release tag interactively or from command queue.
    
    Args:
        project_dir: Project directory
        cmd_queue: Optional list of commands to consume (if provided, pops from queue instead of input)
        
    Selection must be a valid tag name (e.g., "V1.5"). Case-insensitive matching is supported.
    """
    tags = _show_available_releases(project_dir)
    
    if not tags:
        return None
    
    try:
        # Use command from queue if available, otherwise prompt user
        if cmd_queue:
            selection = cmd_queue.pop(0).strip()
            print(f"Enter tag name (or 'q' to quit): {selection}", flush=True)
        else:
            selection = input("Enter tag name (or 'q' to quit): ").strip()
        
        if selection.lower() == 'q':
            log_message("Cancelled.")
            return None
        
        # Check if selection is a valid tag name (exact match)
        if selection in tags:
            return selection
        
        # Check case-insensitive match
        for tag in tags:
            if tag.lower() == selection.lower():
                return tag
        
        # Invalid tag name - show error with available tags
        log_message(f"[!x!] Error: '{selection}' is not a valid tag name.")
        log_message(f"Available tags: {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}")
        return None
            
    except KeyboardInterrupt:
        log_message("Cancelled.")
        return None


def _validate_ref(project_dir: Path, ref: str) -> bool:
    """Validate that a ref (tag or commit) exists."""
    result = subprocess.run(
        ["git", "-C", str(project_dir), "rev-parse", "--verify", ref],
        capture_output=True,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def _pull_release_to_folder(project_dir: Path, release_dir: Path, git_repo_root: Path,
                            release_config: Path, hw_config: Path, ref: str) -> bool:
    """Checkout entire release folder recursively from a tag/commit (overwrites existing files).
    
    Uses git checkout to restore the entire release folder from the specified tag/ref.
    This ensures all files in the release folder match exactly what's in the tag.
    
    Order of operations:
    1. Fetch LFS objects for the ref (to ensure large files are available)
    2. Use git checkout to restore the entire release folder from the ref
    """
    log_message(f"Pulling ONLY release folder from tag: {ref}")
    log_message(f"Destination: {release_dir}")
    log_message("Note: Only files in the release folder are updated, other project files are unchanged")
    
    # Get release folder path relative to git root
    release_rel_path = release_dir.relative_to(git_repo_root)
    
    # Step 1: Fetch the ref from origin to ensure it's available locally
    log_message(f"Fetching ref {ref} from origin...")
    fetch_result = subprocess.run(
        ["git", "-C", str(git_repo_root), "fetch", "origin", ref],
        capture_output=True,
        text=True
    )
    if fetch_result.returncode != 0:
        # Try fetching all tags if specific ref fetch fails
        log_message(f"Specific fetch failed, trying to fetch all tags...")
        subprocess.run(
            ["git", "-C", str(git_repo_root), "fetch", "--tags", "origin"],
            capture_output=True,
            text=True
        )
    
    # Step 2: Fetch LFS objects for the ref
    log_message(f"Fetching LFS objects for {ref}...")
    lfs_result = subprocess.run(
        ["git", "-C", str(git_repo_root), "lfs", "fetch", "origin", ref],
        capture_output=True,
        text=True
    )
    if lfs_result.returncode != 0:
        log_message(f"[!x!] Warning: LFS fetch failed: {lfs_result.stderr.strip()}")
    else:
        log_message("LFS objects fetched successfully")
    
    # Step 3: Use git checkout to restore the entire release folder from the ref
    # This command checks out the release folder from the specified ref, overwriting local files
    log_message(f"Checking out release folder from {ref}...")
    
    try:
        # First, verify the ref exists and the release folder is in it
        verify_result = subprocess.run(
            ["git", "-C", str(git_repo_root), "ls-tree", "-r", "--name-only", ref, str(release_rel_path)],
            capture_output=True,
            text=True
        )
        if verify_result.returncode != 0:
            log_message(f"[!x!] Error: Could not find release folder in ref {ref}")
            log_message(f"    stderr: {verify_result.stderr.strip()}")
            return False
        
        files_in_ref = verify_result.stdout.strip().split('\n')
        files_in_ref = [f for f in files_in_ref if f]  # Remove empty strings
        
        if not files_in_ref:
            log_message(f"[!x!] Error: No files found in {release_rel_path} for ref {ref}")
            return False
        
        log_message(f"Found {len(files_in_ref)} files to checkout")
        
        # Checkout the entire release folder from the ref
        # Using -- to separate ref from path
        checkout_result = subprocess.run(
            ["git", "-C", str(git_repo_root), "checkout", ref, "--", str(release_rel_path)],
            capture_output=True,
            text=True
        )
        
        if checkout_result.returncode != 0:
            log_message(f"[!x!] Error: git checkout failed")
            log_message(f"    stderr: {checkout_result.stderr.strip()}")
            return False
        
        # Step 4: Run LFS checkout to ensure LFS files are properly smudged
        log_message("Running LFS checkout to resolve large files...")
        lfs_checkout_result = subprocess.run(
            ["git", "-C", str(git_repo_root), "lfs", "checkout", str(release_rel_path)],
            capture_output=True,
            text=True
        )
        if lfs_checkout_result.returncode != 0:
            log_message(f"[!x!] Warning: LFS checkout had issues: {lfs_checkout_result.stderr.strip()}")
        
        # Check if config file exists (optional - checkout works without it)
        config_exists = hw_config.exists()
        log_message(f"Config file: {'OK' if config_exists else 'not present (optional)'}")
        
        # List files that were checked out
        log_message(f"Checkout complete. Files restored:")
        for f in files_in_ref[:10]:  # Show first 10 files
            file_path = git_repo_root / f
            if file_path.exists():
                size = file_path.stat().st_size
                log_message(f"  {f} ({size} bytes)")
            else:
                log_message(f"  {f} (missing)")
        if len(files_in_ref) > 10:
            log_message(f"  ... and {len(files_in_ref) - 10} more files")
        
        return True
        
    except Exception as e:
        log_message(f"[!x!] Error during checkout: {e}")
        return False


def _load_config(config_path: str) -> Dict:
    """Load configuration from JSON file. Error if not exists."""
    if not os.path.exists(config_path):
        # Error out - don't create default
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Expand paths
        if "bit_file" in config and config["bit_file"]:
            config["bit_file"] = os.path.expanduser(config["bit_file"])
        if "ltx_file" in config and config["ltx_file"]:
            config["ltx_file"] = os.path.expanduser(config["ltx_file"])
        
        return config
    except (json.JSONDecodeError, IOError) as e:
        log_message(f"[!x!] Failed to load config from {config_path}: {e}")
        return {}


def _load_and_resolve_config(config_path: str, invoked_cwd: str = None, silent: bool = False) -> tuple:
    """
    Central function to load config and resolve all paths.
    
    Args:
        config_path: Path to config file
        invoked_cwd: Working directory for relative path resolution
        silent: If True, don't log config details (used for silent reloads)
    
    Returns:
        (config_dict, server_ip, server_port, bitstream, probes, vio_outputs, config_path_resolved)
        All paths are resolved to absolute paths.
    """
    if not invoked_cwd:
        invoked_cwd = os.getcwd()
    
    # Resolve config path
    config_path_resolved = os.path.expanduser(config_path)
    if not os.path.isabs(config_path_resolved):
        config_path_resolved = os.path.join(invoked_cwd, config_path_resolved)
    
    # Load config
    config = _load_config(config_path_resolved)
    if not config:
        return {}, '', '', '', '', {}, '', config_path_resolved, {}, '', ''
    
    # Config format detection:
    # 1. Single-DNA format: { "dna": "...", "hw_server_host": "...", ... }
    # 2. Multi-DNA format: { "DNA_VALUE": { "hw_server_host": "...", ... }, "DNA_VALUE2": {...} }
    # 3. Old format: { "device": "...", "hw_server_host": "...", ... }
    # Note: device_name is NO LONGER used - filename is used as device name instead
    device_dna = ''
    device_config = config
    
    config_keys = list(config.keys())
    
    # Check for single-DNA format (dna as top-level field)
    if 'dna' in config:
        # Single-DNA format: dna is a top-level field
        device_dna = config.get('dna', '')
        device_config = config
    elif config_keys and not any(k in config_keys for k in ['hw_server_host', 'hw_server_port', 'bit_file', 'ltx_file', 'device']):
        # Multi-DNA format: first key is the DNA, value is the device config
        device_dna = config_keys[0]
        device_config = config.get(device_dna, {})
    else:
        # Old format: direct config with 'device' field
        device_dna = config.get('device', '') if isinstance(config.get('device'), str) else ''
    
    # Extract values from device config
    server_ip = device_config.get('hw_server_host', 'localhost')
    server_port = str(device_config.get('hw_server_port', '3121'))
    vio_outputs = device_config.get('vio_outputs', {})
    
    # Extract files - support both old format (bit_file, ltx_file at top level)
    # and new format (files: {bit_file, ltx_file})
    files_config = device_config.get('files', {})
    if files_config:
        # New format: files are under "files" record
        bitstream = files_config.get('bit_file', '')
        probes = files_config.get('ltx_file', '')
    else:
        # Old format: files at top level
        bitstream = device_config.get('bit_file', '')
        probes = device_config.get('ltx_file', '')
    
    # Extract version and timestamp from config (if specified)
    config_version = device_config.get('version', '')
    config_timestamp = device_config.get('timestamp', '')
    
    # Resolve bitstream path
    if bitstream:
        if not os.path.isabs(bitstream) and not bitstream.startswith('~'):
            # Try relative to config file directory first, then invoked_cwd
            config_dir = os.path.dirname(config_path_resolved)
            bitstream_candidate = os.path.join(config_dir, bitstream)
            if os.path.exists(bitstream_candidate):
                bitstream = bitstream_candidate
            else:
                bitstream = os.path.join(invoked_cwd, bitstream)
        bitstream = os.path.expanduser(bitstream)
        bitstream = os.path.abspath(bitstream)
    
    # Resolve probes path
    if probes:
        if not os.path.isabs(probes) and not probes.startswith('~'):
            # Try relative to config file directory first, then invoked_cwd
            config_dir = os.path.dirname(config_path_resolved)
            probes_candidate = os.path.join(config_dir, probes)
            if os.path.exists(probes_candidate):
                probes = probes_candidate
            else:
                probes = os.path.join(invoked_cwd, probes)
        probes = os.path.expanduser(probes)
        probes = os.path.abspath(probes)
    
    # Log config content for debugging (unless silent mode)
    if not silent:
        log_message(f"Config loaded from: {config_path_resolved}")
        log_message(f"  Server: {server_ip}:{server_port}")
        if bitstream:
            log_message(f"  Bitstream: {bitstream} {'(exists)' if os.path.exists(bitstream) else '(not found)'}")
        if probes:
            log_message(f"  Probes: {probes} {'(exists)' if os.path.exists(probes) else '(not found)'}")
    
    # Return empty dict for device_names (no longer used - filename is the device name now)
    return config, server_ip, server_port, bitstream, probes, vio_outputs, device_dna, config_path_resolved, {}, config_version, config_timestamp


def help_hw_server():
    """Show detailed help for HW Server tool."""
    print("=" * 80)
    print("HDLFORGE HW_SERVER - Interactive FPGA Hardware Manager")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Interactive FPGA hardware manager with persistent Vivado console:")
    print("    - Program FPGA with bitstream files")
    print("    - Scan and interact with ILA/VIO debug cores")
    print("    - Set/commit VIO output values")
    print("    - Scan JTAG targets and read device DNA")
    print()
    print("USAGE:")
    print("  hdlforge --tool hw_server --cmd <command> [options]")
    print("  hdlforge --tool hw_server -c config.json -i        # Interactive with config")
    print("  hdlforge --tool hw_server -c config.json -ic 2 v1  # Chain commands")
    print("  hdlforge --tool hw_server -c config.json --cmd 1 --cmd 2  # Multiple menu selections")
    print()
    print("COMMANDS:")
    print("  program          Program FPGA with bitstream file")
    print("  scan_ila         Scan for ILA/VIO debug cores")
    print("  scan_jtag        Scan JTAG targets and read chip DNA")
    print("  read_usr_access        Read USR_ACCESS value from bitstream file")
    print("  read_usr_access_device Read USR_ACCESS value from FPGA device")
    print()
    print("OPTIONS:")
    print("  -c, --hw-config <FILE>   Config file (required, must exist)")
    print("  -i, --interactive        Interactive mode (keep console open with menu)")
    print("  -ic <cmd1> <cmd2> ...    Run commands then exit (e.g., -ic device scan vio-1)")
    print("  --cmd <value>            Menu selection (can be used multiple times)")
    print("                           Each --cmd is executed as a menu choice")
    print("                           After all commands, stays in interactive mode")
    print("                           Use --cmd q to exit after commands")
    print("                           Quoted strings supported: --cmd 'text example'")
    print("  --server_ip <IP>         Hardware server IP (default: localhost)")
    print("  --bitstream <PATH>       Path to bitstream file (.bit)")
    print("  --probes <PATH>          Path to probes file (.ltx)")
    print()
    print("CONFIG FILE (-c config.json):")
    print("  Create a JSON file with these fields:")
    print('  {')
    print('    "hw_server_host": "localhost",')
    print('    "hw_server_port": "3121",')
    print('    "bit_file": "/path/to/design.bit",')
    print('    "ltx_file": "/path/to/design.ltx",')
    print('    "vio_outputs": {')
    print('      "ip_address[0]": {"value": "", "width": 32, "radix": "ip"},')
    print('      "mac_address[0]": {"value": "", "width": 48, "radix": "mac"},')
    print('      "config_port": {"value": "", "width": 16, "radix": "hex"},')
    print('      "enable_flag": {"value": "", "width": 1, "radix": "bin"}')
    print('    }')
    print('  }')
    print()
    print("VIO OUTPUT RADIX OPTIONS:")
    print("  hex   - Hexadecimal (default)")
    print("  dec   - Decimal")
    print("  bin   - Binary (0/1)")
    print("  ip    - IP address format (192.168.1.1)")
    print("  mac   - MAC address format (aa:bb:cc:dd:ee:ff)")
    print()
    print("EXAMPLES:")
    print("  # Quick start")
    print("  hdlforge --tool hw_server -c config.json --cmd scan_jtag")
    print()
    print("  # Interactive mode with config")
    print("  hdlforge --tool hw_server -c config.json -i")
    print()
    print("  # View VIO with output display formats")
    print("  hdlforge --tool hw_server -c config.json -ic device scan vio-1")
    print()
    print("  # Execute multiple menu selections, then stay interactive")
    print("  hdlforge --tool hw_server -c config.json --cmd 1 --cmd 2")
    print("  # (Executes menu option 1, then 2, then waits for user input)")
    print()
    print("  # Execute commands and exit")
    print("  hdlforge --tool hw_server -c config.json --cmd 1 --cmd 2 --cmd q")
    print("  # (Executes menu option 1, then 2, then exits)")
    print()
    print("  # Use quoted strings for values with spaces")
    print("  hdlforge --tool hw_server -c config.json --cmd 'text example'")
    print("  # (Passes 'text example' as a single menu selection)")
    print()
    print("INTERACTIVE COMMANDS:")
    print("  1                  Program FPGA")
    print("  2                  Scan ILA/VIO cores")
    print("  3                  Scan JTAG / Read DNA")
    print("  4                  Read USR_ACCESS/USERID from bitstream file")
    print("  5                  Read USR_ACCESS/USERID from FPGA device")
    print("  5                  Checkout release (restore files from git tag)")
    print("  q                  Exit")
    print()
    print("  ila-<n>            Read ILA (ila-1, ila-2, ...)")
    print("  ila-<n>-save-ila    Save ILA as .ila")
    print("  ila-<n>-save-vcd    Save ILA as .vcd")
    print("  ila-<n>-save-csv    Save ILA as .csv")
    print()
    print("  vio-<n>            Read VIO (vio-1, vio-2, ...)")
    print("  vio-<n>-set-from-file  Set VIO from config.json")
    print("  vio-<n>-set-hex    Set VIO manually (hex only)")
    print()
    print("  device-<n>         Select device (device-1, device-2, ...)")
    print()
    print("  sleep <N>          Wait N seconds (e.g., sleep 1, sleep 0.5)")
    print()
    print("VIO VALUES:")
    print("  <- = Input (read from FPGA)")
    print("  -> = Output (write to FPGA)")
    print("  Values shown are from hardware after refresh")
    print()
    print("=" * 80)
