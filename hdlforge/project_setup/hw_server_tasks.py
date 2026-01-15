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
from pathlib import Path
from typing import Dict, Optional, List

from hw_server_console import VivadoTCLConsole


def log_message(text: str) -> None:
    """Output a log message with [LOG]: prefix."""
    print(f"[LOG]: {text}", flush=True)


def result_message(text: str) -> None:
    """Output a result message with [RESULT]: prefix."""
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
    print("=" * 60)


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
    
    # Use original CWD from where user invoked hdlforge (for Vivado logs and relative paths)
    invoked_cwd = kwargs.get('original_cwd', os.getcwd())
    
    # Load config file ONLY if -c is explicitly provided
    config = {}
    config_path = ""
    if config_file:
        config_path = os.path.expanduser(config_file)
        if not os.path.isabs(config_path):
            config_path = os.path.join(invoked_cwd, config_path)
        config = _load_config(config_path)
        if not config:
            log_message(f"[!x!] Config file not found or invalid: {config_path}")
            sys.exit(1)
        log_message(f"Loaded config from: {config_path}")
    
    # Apply config values (only if not overridden by command line)
    if not server_ip:
        server_ip = config.get('hw_server_host', 'localhost')
    if not server_port:
        server_port = str(config.get('hw_server_port', '3121'))
    if not bitstream:
        bitstream = config.get('bit_file', '')
    if not probes:
        probes = config.get('ltx_file', '')
    
    # Resolve relative paths from config relative to invoked directory
    if bitstream and not os.path.isabs(bitstream) and not bitstream.startswith('~'):
        bitstream = os.path.join(invoked_cwd, bitstream)
    if probes and not os.path.isabs(probes) and not probes.startswith('~'):
        probes = os.path.join(invoked_cwd, probes)
    
    # Get VIO outputs from config
    vio_outputs = config.get('vio_outputs', {})
    
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
        log_message("OPERATION: Step 1/3 - Reading USR_ACCESS from bitstream file")
        usr_access_value = _read_usr_access_value(bitstream)
        if usr_access_value is not None:
            log_message(f"USR_ACCESS Value: 0x{usr_access_value:08X}")
        else:
            log_message("Warning: Could not read USR_ACCESS from bitstream file")
        
        # Step 2: Program FPGA
        log_message("OPERATION: Step 2/3 - Programming FPGA")
        log_message("[start of output from Vivado TCL]")
        success = console.program_fpga(bitstream, probes)
        log_message("[end of output from Vivado TCL]")
        
        if not success:
            result_message("PROGRAMMING FAILED")
            return False
        
        # Step 3: Verify USR_ACCESS from device
        log_message("OPERATION: Step 3/3 - Verifying USR_ACCESS from device")
        log_message("[start of output from Vivado TCL]")
        device_value = _read_usr_access_from_device_value(console)
        log_message("[end of output from Vivado TCL]")
        
        if device_value is not None:
            log_message(f"Device USR_ACCESS: 0x{device_value:08X}")
            if usr_access_value is not None:
                if usr_access_value == device_value:
                    log_message("Verification PASSED: USR_ACCESS values match")
                    result_message("PROGRAMMING SUCCESS - USR_ACCESS verified")
                else:
                    log_message(f"Verification FAILED: Values do not match (bitstream: 0x{usr_access_value:08X}, device: 0x{device_value:08X})")
                    result_message("PROGRAMMING SUCCESS - USR_ACCESS mismatch warning")
            else:
                result_message("PROGRAMMING SUCCESS")
        else:
            log_message("Warning: Could not read USR_ACCESS from device")
            result_message("PROGRAMMING SUCCESS - USR_ACCESS not verified")
        
        return success
    
    elif cmd == 'scan_ila':
        if not probes:
            log_message("[!x!] Probes file must be specified with --probes or in config file")
            return False
        log_message("[start of output from Vivado TCL]")
        scan_result = console.scan_ila_vio(probes)
        log_message("[end of output from Vivado TCL]")
        if scan_result:
            result_message("SCAN COMPLETE")
        else:
            result_message("SCAN FAILED")
        return scan_result
    
    elif cmd == 'scan_jtag' or cmd == 'read_dna':
        log_message("[start of output from Vivado TCL]")
        jtag_result = console.scan_jtag()
        log_message("[end of output from Vivado TCL]")
        if jtag_result:
            result_message("JTAG SCAN COMPLETE")
        else:
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
    if c in ("1", "program"):
        return "Program FPGA"
    if c in ("2", "scan_ila"):
        return "Scan ILA/VIO cores"
    if c in ("3", "scan_jtag", "read_dna"):
        return "Scan JTAG / Read DNA"
    if c in ("4", "read_usr_access"):
        return "Read USR_ACCESS/USERID from bitstream file"
    if c in ("5", "read_usr_access_device"):
        return "Read USR_ACCESS/USERID from FPGA device"
    if c in ("q", "quit", "exit"):
        return "Exit"

    # New ILA commands
    if c.startswith("ila-v-"):
        idx = c[len("ila-v-"):]
        return f"View ILA {idx}"
    if c.startswith("ila-save-ila-"):
        idx = c[len("ila-save-ila-"):]
        return f"Save ILA {idx} as .ila"
    if c.startswith("ila-save-vcd-"):
        idx = c[len("ila-save-vcd-"):]
        return f"Save ILA {idx} as .vcd"
    if c.startswith("ila-save-csv-"):
        idx = c[len("ila-save-csv-"):]
        return f"Save ILA {idx} as .csv"

    # Backwards-compatible short ILA commands
    if c.startswith("i") and len(c) > 1 and not c.startswith("is"):
        idx = c[1:]
        return f"View ILA {idx}"
    if c.startswith("is") and len(c) > 2:
        idx = c[2:]
        return f"Save ILA {idx} as .ila"
    if c.startswith("iw") and len(c) > 2:
        idx = c[2:]
        return f"Save ILA {idx} as .vcd"
    if c.startswith("ic") and len(c) > 2:
        idx = c[2:]
        return f"Save ILA {idx} as .csv"

    # New VIO commands
    if c.startswith("vio-v-"):
        idx = c[len("vio-v-"):]
        return f"View VIO {idx}"
    if c.startswith("vio-set-f-"):
        idx = c[len("vio-set-f-"):]
        return f"Set VIO {idx} from config"
    if c.startswith("vio-set-hex-"):
        idx = c[len("vio-set-hex-"):]
        return f"Set VIO {idx} manually (hex)"

    # Backwards-compatible short VIO commands
    if c.startswith("v") and len(c) > 1 and not c.startswith("sv") and not c.startswith("vh"):
        idx = c[1:]
        return f"View VIO {idx}"
    if c.startswith("sv") and len(c) > 2:
        idx = c[2:]
        return f"Set VIO {idx} from config"
    if c.startswith("vh") and len(c) > 2:
        idx = c[2:]
        return f"Set VIO {idx} manually (hex)"

    return ""


def _ensure_console_started(console: VivadoTCLConsole, server_ip: str, server_port: str) -> bool:
    """Ensure console is started and connected. Returns True if successful."""
    if console.process and console.connected:
        return True
    
    if not console.process:
        log_message("Initializing Vivado TCL console...")
        if not console.start():
            log_message("[!x!] Failed to start Vivado")
            return False
    
    if not console.connected:
        log_message("Connecting to hardware server...")
        if not console.connect_hw_server(server_ip, server_port):
            log_message("[!x!] Failed to connect to hardware server")
            return False
        
        log_message("Connected successfully!")
        log_message(f"Target: {console.target}")
        log_message(f"Device: {console.device}")
    
    return True


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
    choice = choice.lower().strip()
    
    if choice == "1" or choice == "program":
        # Reload config if available to get latest bitstream/probes paths
        current_bitstream = bitstream
        current_probes = probes
        if config_path and os.path.exists(config_path):
            _, _, _, current_bitstream, current_probes, _, _ = _load_and_resolve_config(config_path, invoked_cwd)
            if not current_bitstream:
                current_bitstream = bitstream  # Fallback to original
            if not current_probes:
                current_probes = probes  # Fallback to original
        
        if not current_bitstream:
            log_message("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return True
        
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        result = _execute_command(console, 'program', current_bitstream, current_probes)
        return result
    elif choice == "2" or choice == "scan_ila":
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        result = _execute_command(console, 'scan_ila', bitstream, probes)
        return result
    elif choice == "3" or choice == "scan_jtag":
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        result = _execute_command(console, 'scan_jtag', bitstream, probes)
        return result
    elif choice == "4" or choice == "read_usr_access":
        # Option 4 doesn't need console - reads from bitstream file directly
        if not bitstream:
            log_message("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return True
        return _read_usr_access(bitstream)
    
    elif choice == "5" or choice == "read_usr_access_device":
        # Option 5 needs console - start it now
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        result = _read_usr_access_from_device(console)
        return result
    elif choice == "6" or choice == "pull_and_program" or choice == "pull":
        # Option 6: Pull release (fetch files from git tag)
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
            log_message("Closing Vivado console before pull...")
            console.close()
        
        # Pull files to release folder (overwrites existing)
        if not _pull_release_to_folder(project_dir, release_dir, git_repo_root, release_config, hw_config, tag_arg):
            result_message("PULL FAILED - Could not fetch release files")
            return True
        
        # Reload config after pull using central function
        if hw_config.exists():
            log_message("Reloading config after pull...")
            new_config, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, new_config_path = _load_and_resolve_config(str(hw_config), invoked_cwd)
            
            if new_config:
                # Update the values for subsequent operations
                bitstream = new_bitstream
                probes = new_probes
                vio_outputs = new_vio_outputs
                server_ip = new_server_ip
                server_port = new_server_port
                config_path = new_config_path
                print()
                log_message("Use option 1 to program FPGA with pulled files.")
                print()
                result_message(f"PULL SUCCESS - Tag {tag_arg} pulled to release folder")
            else:
                result_message("PULL FAILED - Could not reload config after pull")
                return True
        else:
            result_message("PULL FAILED - Config file not found after pull")
            return True
        
        return True  # Continue with menu (pull only, no programming)
    elif choice in ("q", "quit", "exit"):
        return False
    # ILA view/save commands - need console
    # New names:
    #   ila-v-1          -> view ILA 1
    #   ila-save-ila-1   -> save ILA 1 as .ila
    #   ila-save-vcd-1   -> save ILA 1 as .vcd
    #   ila-save-csv-1   -> save ILA 1 as .csv
    if choice.startswith("ila-v-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[len("ila-v-"):]) - 1
            console.print_ila_details(ila_idx)
        except ValueError:
            log_message(f"Invalid ILA selection: {choice}")
    elif choice.startswith("ila-save-ila-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[len("ila-save-ila-"):]) - 1
            console.save_ila_data(ila_idx, fmt="ila")
        except ValueError:
            log_message(f"Invalid ILA save selection: {choice}")
    elif choice.startswith("ila-save-vcd-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[len("ila-save-vcd-"):]) - 1
            console.save_ila_data(ila_idx, fmt="vcd")
        except ValueError:
            log_message(f"Invalid VCD save selection: {choice}")
    elif choice.startswith("ila-save-csv-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[len("ila-save-csv-"):]) - 1
            console.save_ila_data(ila_idx, fmt="csv")
        except ValueError:
            log_message(f"Invalid CSV save selection: {choice}")
    # Backwards-compatible short ILA commands (i1, is1, iw1, ic1)
    elif choice.startswith("i") and len(choice) > 1 and not choice.startswith("is"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[1:]) - 1
            console.print_ila_details(ila_idx)
        except ValueError:
            log_message(f"Invalid ILA selection: {choice}")
    elif choice.startswith("is") and len(choice) > 2:
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[2:]) - 1
            console.save_ila_data(ila_idx, fmt="ila")
        except ValueError:
            log_message(f"Invalid ILA save selection: {choice}")
    elif choice.startswith("iw") and len(choice) > 2:
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[2:]) - 1
            console.save_ila_data(ila_idx, fmt="vcd")
        except ValueError:
            log_message(f"Invalid VCD save selection: {choice}")
    elif choice.startswith("ic") and len(choice) > 2:
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            ila_idx = int(choice[2:]) - 1
            console.save_ila_data(ila_idx, fmt="csv")
        except ValueError:
            log_message(f"Invalid CSV save selection: {choice}")

    # VIO view/set commands - need console
    # New names:
    #   vio-v-1        -> view VIO 1
    #   vio-set-f-1    -> set from config for VIO 1
    #   vio-set-hex-1  -> set manually (hex) for VIO 1
    elif choice.startswith("vio-v-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            vio_idx = int(choice[len("vio-v-"):]) - 1
            console.print_vio_details(vio_idx, vio_outputs)
        except ValueError:
            log_message(f"Invalid VIO selection: {choice}")
    elif choice.startswith("vio-set-f-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            vio_idx = int(choice[len("vio-set-f-"):]) - 1
            _set_vio_values_for_index(console, vio_idx, vio_outputs, force)
        except ValueError:
            log_message(f"Invalid VIO set selection: {choice}")
    elif choice.startswith("vio-set-hex-"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            vio_idx = int(choice[len("vio-set-hex-"):]) - 1
            _set_vio_values_manual(console, vio_idx)
        except ValueError:
            log_message(f"Invalid manual VIO set selection: {choice}")

    # Backwards-compatible short VIO commands (v1, sv1, vh1)
    elif choice.startswith("v") and len(choice) > 1 and not choice.startswith("sv") and not choice.startswith("vh"):
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            vio_idx = int(choice[1:]) - 1
            console.print_vio_details(vio_idx, vio_outputs)
        except ValueError:
            log_message(f"Invalid VIO selection: {choice}")
    elif choice.startswith("sv") and len(choice) > 2:
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            vio_idx = int(choice[2:]) - 1
            _set_vio_values_for_index(console, vio_idx, vio_outputs, force)
        except ValueError:
            log_message(f"Invalid VIO set selection: {choice}")
    elif choice.startswith("vh") and len(choice) > 2:
        if not _ensure_console_started(console, server_ip, server_port):
            return True
        try:
            vio_idx = int(choice[2:]) - 1
            _set_vio_values_manual(console, vio_idx)
        except ValueError:
            log_message(f"Invalid manual VIO set selection: {choice}")
    else:
        log_message(f"Invalid option: {choice}")
    
    return True


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
    console.print_vio_details(vio_idx, vio_outputs, header_prefix="Set VIO")


def _set_vio_values_manual(console: VivadoTCLConsole, vio_idx: int) -> None:
    """Interactively set VIO values by hand (hex only) for a specific VIO index."""
    vio_list = console._get_vio_list()
    if vio_idx < 0 or vio_idx >= len(vio_list):
        log_message(f"  ERROR: Invalid VIO index {vio_idx + 1}")
        return

    vio_info = vio_list[vio_idx]
    probe_names = vio_info.get("probe_names", [])
    probe_widths = vio_info.get("probe_widths", {})
    probe_directions = vio_info.get("probe_directions", {})

    log_message(f"--- Set VIO (manual): {vio_info['name']} ---")
    log_message("  Output probes (hex only):")

    output_probes = []
    for name in probe_names:
        if probe_directions.get(name) == "output":
            width = probe_widths.get(name)
            width_str = f"[{width-1}:0]" if isinstance(width, int) and width > 1 else "[0]"
            log_message(f"    - {name} {width_str}")
            output_probes.append(name)

    if not output_probes:
        log_message("  No output probes available to set.")
        return

    while True:
        probe_name = input("\n  Enter probe name to set (or empty to finish): ").strip()
        if not probe_name:
            break
        if probe_name not in output_probes:
            log_message("  Invalid probe name or not an output probe.")
            continue

        raw_val = input(f"  Enter hex value for {probe_name} (e.g. 0x20 or 20): ").strip()
        if not raw_val:
            log_message("  Empty value, skipped.")
            continue

        # Strip 0x prefix and spaces, validate hex
        v = raw_val.strip()
        if v.lower().startswith("0x"):
            v = v[2:]
        v = v.replace(" ", "")
        try:
            int(v, 16)
        except ValueError:
            log_message("  Invalid hex value, try again.")
            continue

        width = probe_widths.get(probe_name)
        # Use radix 'hex'; set_vio_value will pad and commit, and verify via read-back
        if not console.set_vio_value(probe_name, v, radix="hex", width=width, commit=False, force=True):
            log_message("  Failed to set value, see errors above.")

    # After manual updates, show updated table with explicit header
    console.print_vio_details(vio_idx, vio_outputs=None, header_prefix="Set VIO")



def _print_menu(console: VivadoTCLConsole, bitstream: str, probes: str, vio_outputs: dict = None) -> None:
    """Print the interactive menu."""
    menu_lines = []
    
    if bitstream:
        menu_lines.append("1. Program FPGA (requires hardware connection)")
    else:
        menu_lines.append("1. Program FPGA (requires --bitstream or -c config, requires hardware connection)")
    
    if probes:
        menu_lines.append("2. Scan ILA/VIO (requires hardware connection)")
    else:
        menu_lines.append("2. Scan ILA/VIO (requires --probes or -c config, requires hardware connection)")
    
    menu_lines.append("3. Scan JTAG Targets (requires hardware connection)")
    
    if bitstream:
        menu_lines.append("4. Read USR_ACCESS/USERID from bitstream file")
    else:
        menu_lines.append("4. Read USR_ACCESS/USERID from bitstream file (requires --bitstream or -c config)")
    
    menu_lines.append("5. Read USR_ACCESS/USERID from FPGA device (requires hardware connection)")
    menu_lines.append("6. Pull release (fetch files from git tag)")
    
    # Dynamic ILA options
    ila_list = console._get_ila_list()
    if console.scanned and ila_list:
        menu_lines.append("-" * 40)
        menu_lines.append("ILA:")
        for i, ila in enumerate(ila_list):
            idx = i + 1
            menu_lines.append(
                f"  ila-v-{idx}  View"
                f"    | ila-save-ila-{idx} Save .ila"
                f"    | ila-save-vcd-{idx} Save .vcd"
                f"    | ila-save-csv-{idx} Save .csv"
            )
    
    # Dynamic VIO options
    vio_list = console._get_vio_list()
    if console.scanned and vio_list:
        menu_lines.append("-" * 40)
        menu_lines.append("VIO:")
        for i, vio in enumerate(vio_list):
            idx = i + 1
            line = f"  vio-v-{idx}  View"
            if vio_outputs:
                line += f"    | vio-set-f-{idx} Set from config"
            line += f"    | vio-set-hex-{idx} Set manual (hex)"
            menu_lines.append(line)
    
    menu_lines.append("-" * 40)
    menu_lines.append("q. Exit")
    
    # Display menu in a single box (don't auto-close, will close after input)
    display_box("MENU: HW Server Menu", menu_lines, auto_close=False)
    # Print "Select an option: " without newline, then get input on same line
    print(" Select an option: ", end="", flush=True)


def _interactive_loop(console: VivadoTCLConsole, bitstream: str, probes: str, 
                      vio_outputs: dict = None, config_path: str = "",
                      server_ip: str = 'localhost', server_port: str = '3121',
                      invoked_cwd: str = None, cmd_buffer: list = None) -> None:
    """Run interactive menu loop. Console starts lazily when needed.
    
    Args:
        cmd_buffer: List of commands to process as if user typed them (from --cmd)
    """
    # Use lists to allow updates from menu choices (Python doesn't have pass-by-reference for strings)
    state = {
        'bitstream': bitstream,
        'probes': probes,
        'vio_outputs': vio_outputs or {},
        'server_ip': server_ip,
        'server_port': server_port,
        'config_path': config_path
    }
    
    # Initialize command buffer from cmd_buffer if provided
    cmd_queue = list(cmd_buffer) if cmd_buffer else []
    
    while True:
        # Reload config before each menu display if config_path exists (to pick up changes from pull)
        # Use silent=True to avoid duplicate logging
        if state['config_path'] and os.path.exists(state['config_path']):
            _, new_server_ip, new_server_port, new_bitstream, new_probes, new_vio_outputs, _ = _load_and_resolve_config(state['config_path'], invoked_cwd, silent=True)
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
        
        # Get choice from buffer if available, otherwise from user input
        try:
            if cmd_queue:
                # Use command from buffer (simulate user input)
                choice = cmd_queue.pop(0).strip()
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
        
        if not _execute_menu_choice(console, choice, state['bitstream'], state['probes'], state['vio_outputs'], 
                                   force=False, server_ip=state['server_ip'], server_port=state['server_port'], 
                                   invoked_cwd=invoked_cwd, config_path=state['config_path'],
                                   cmd_queue=cmd_queue):
            break


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
    log_message("OPERATION: Reading USR_ACCESS and USERID from FPGA Device")
    
    if not console.connected:
        log_message("[!x!] Not connected to hardware server")
        return False
    
    try:
        device = console.device or "xcvu9p_0"
        
        # Set device variable in TCL using lindex approach (more reliable)
        console.send_command("set device [lindex [get_hw_devices] 0]", timeout=2)
        # Ensure device is current and refreshed
        console.send_command("current_hw_device $device", timeout=2)
        console.send_command("refresh_hw_device $device", timeout=5)
        
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
                output = console.send_command("puts [get_property REGISTER.USR_ACCESS [lindex [get_hw_devices] 0]]", timeout=5)
                import re
                match = re.search(r'0x([0-9A-Fa-f]+)', output, re.IGNORECASE)
                if match:
                    value = int(match.group(1), 16)
                    property_used = "REGISTER.USR_ACCESS (direct)"
            except:
                pass
        
        # Also read USERID from device
        userid_value = _read_userid_from_device_value(console)
        
        print()
        log_message(f"Device: {device}")
        print()
        
        if value is not None:
            # Format as version: 0x00MMNNPP -> vMM.NN.PP
            major = (value >> 16) & 0xFF
            minor = (value >> 8) & 0xFF
            patch = value & 0xFF
            
            log_message(f"USR_ACCESS (Version): 0x{value:08X}")
            log_message(f"  Property: {property_used}")
            log_message(f"  Version: V{major}.{minor}.{patch}")
        else:
            log_message("[!x!] USR_ACCESS: Could not read from device")
        
        print()
        if userid_value is not None:
            log_message(f"USERID (Timestamp): {_format_userid(userid_value)}")
        else:
            log_message("USERID: Could not read from device (may not be exposed via TCL)")
        
        print()
        if value is None and userid_value is None:
            log_message("Note: Use option 4 to read values from the bitstream file instead.")
            result_message("DEVICE READ FAILED - No values found")
            return False
        
        if value is not None:
            major = (value >> 16) & 0xFF
            minor = (value >> 8) & 0xFF
            patch = value & 0xFF
            result_message(f"DEVICE READ COMPLETE - Version: V{major}.{minor}.{patch}")
        else:
            result_message("DEVICE READ COMPLETE - USERID only")
        
        return True
            
    except Exception as e:
        log_message(f"[!x!] Error reading USR_ACCESS from device: {e}")
        import traceback
        traceback.print_exc()
        result_message("DEVICE READ FAILED - Error reading from device")
        return False


def _read_usr_access(bitfile: str) -> bool:
    """Read USR_ACCESS (version) and USERID (timestamp) from Xilinx .bit file."""
    log_message("OPERATION: Reading USR_ACCESS and USERID from Bitstream File")
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
        
        # Display results
        print()
        if usr_access_value is not None:
            major = (usr_access_value >> 16) & 0xFF
            minor = (usr_access_value >> 8) & 0xFF
            patch = usr_access_value & 0xFF
            
            log_message(f"USR_ACCESS (Version): 0x{usr_access_value:08X}")
            log_message(f"  Pattern: {usr_access_pattern} at position {usr_access_pos}")
            log_message(f"  Version: V{major}.{minor}.{patch}")
        else:
            log_message("[!x!] USR_ACCESS not found in bitstream")
        
        print()
        if userid_value is not None:
            log_message(f"USERID (Timestamp): {_format_userid(userid_value)}")
        elif userid_raw is not None:
            log_message(f"USERID (Raw): 0x{userid_raw:08X} (not a valid timestamp)")
        else:
            log_message("USERID: N/A (not found in bitstream)")
        
        print()
        if usr_access_value is not None:
            major = (usr_access_value >> 16) & 0xFF
            minor = (usr_access_value >> 8) & 0xFF
            patch = usr_access_value & 0xFF
            result_message(f"BITSTREAM READ COMPLETE - Version: V{major}.{minor}.{patch}")
        else:
            result_message("BITSTREAM READ FAILED - USR_ACCESS not found")
        
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
    result_message("Available Release Tags:")
    
    # Get list of version tags (V*)
    result = subprocess.run(
        ["git", "-C", str(project_dir), "tag", "-l", "V*", "--sort=-version:refname"],
        capture_output=True,
        text=True
    )
    
    tags = [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]
    
    if not tags:
        result_message("No release tags found.")
        return []
    
    result_message(f"{'Tag':<10} {'Commit':<14} {'Date':<20} {'Message'}")
    result_message(f"{'----------':<10} {'--------------':<14} {'--------------------':<20} {'-------'}")
    
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
        message = message_result.stdout.strip()[:40] if message_result.returncode == 0 else "unknown"
        
        result_message(f"{tag:<10} {commit:<14} {date:<20} {message}")
    
    result_message("")
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
    """Pull release files from a tag/commit directly to release folder (overwrites existing files).
    
    Order of operations:
    1. First fetch config.json from the tag (hardcoded entry point)
    2. Read bit_file and ltx_file from config.json
    3. Fetch those files (bit, ltx)
    """
    log_message(f"Pulling release files from: {ref}")
    log_message(f"Destination: {release_dir}")
    
    # Step 1: Fetch config.json from the tag (hardcoded entry point)
    config_rel_path = hw_config.relative_to(git_repo_root)
    
    print(f"[LOG]:   Fetching config.json... ", end="", flush=True)
    try:
        result = subprocess.run(
            ["git", "-C", str(git_repo_root), "show", f"{ref}:{config_rel_path}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True
        )
        # Ensure parent directory exists
        hw_config.parent.mkdir(parents=True, exist_ok=True)
        with open(hw_config, 'wb') as f:
            f.write(result.stdout)
        size = hw_config.stat().st_size
        log_message(f"OK ({size} bytes)")
    except subprocess.CalledProcessError:
        log_message("FAILED (config.json not in tag)")
        return False
    
    # Step 2: Read the fetched config.json to get the file list
    try:
        with open(hw_config, 'r') as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        log_message(f"[!x!] Error: Failed to parse config.json: {e}")
        return False
    
    # Get files to fetch from config.json (bit_file and ltx_file)
    files = []
    bit_file = config.get("bit_file", "")
    ltx_file = config.get("ltx_file", "")
    
    if bit_file:
        files.append({"dest": bit_file, "use_lfs": True})
    if ltx_file:
        files.append({"dest": ltx_file, "use_lfs": True})
    
    # Check if any files use LFS - if so, fetch LFS objects first
    has_lfs_files = any(f.get("use_lfs", False) for f in files)
    if has_lfs_files:
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
    
    # Track success/failure for each file
    fetch_results = {}
    has_critical_failure = False
    
    for file_info in files:
        dest_file = file_info.get("dest", "")
        use_lfs = file_info.get("use_lfs", False)
        file_path = release_dir / dest_file
        rel_path = file_path.relative_to(git_repo_root)
        
        # Bit files are critical - must succeed
        is_critical = dest_file.endswith('.bit')
        
        print(f"[LOG]:   Fetching {dest_file}... ", end="", flush=True)
        
        fetch_success = False
        
        # Try to get file from ref (tag or commit)
        if use_lfs:
            # For LFS files, use git show piped through git lfs smudge
            try:
                git_show = subprocess.Popen(
                    ["git", "-C", str(git_repo_root), "show", f"{ref}:{rel_path}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                lfs_smudge = subprocess.Popen(
                    ["git", "-C", str(git_repo_root), "lfs", "smudge"],
                    stdin=git_show.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                git_show.stdout.close()
                
                # Ensure parent directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(lfs_smudge.stdout, f)
                
                # Read any remaining stderr before wait
                lfs_stderr = lfs_smudge.stderr.read().decode('utf-8', errors='ignore').strip()
                git_stderr = git_show.stderr.read().decode('utf-8', errors='ignore').strip()
                
                lfs_smudge.wait()
                git_show.wait()
                
                if lfs_smudge.returncode == 0 and git_show.returncode == 0:
                    size = file_path.stat().st_size
                    # Check if file is valid (LFS pointer files are small, ~130 bytes)
                    if size > 200:
                        log_message(f"OK ({size} bytes, LFS)")
                        fetch_success = True
                    else:
                        log_message(f"FAILED (LFS pointer not resolved, {size} bytes)")
                else:
                    err_msg = lfs_stderr or git_stderr or "unknown error"
                    log_message(f"FAILED (git={git_show.returncode}, lfs={lfs_smudge.returncode}: {err_msg})")
            except Exception as e:
                log_message(f"FAILED (LFS error: {e})")
        else:
            # For regular files, use git show directly
            try:
                result = subprocess.run(
                    ["git", "-C", str(git_repo_root), "show", f"{ref}:{rel_path}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                # Ensure parent directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(result.stdout)
                size = file_path.stat().st_size
                log_message(f"OK ({size} bytes)")
                fetch_success = True
            except subprocess.CalledProcessError:
                log_message("FAILED (not in ref)")
        
        fetch_results[dest_file] = fetch_success
        if is_critical and not fetch_success:
            has_critical_failure = True
    
    # Return False if any critical file (bit file) failed to fetch
    if has_critical_failure:
        log_message("[!x!] Critical file(s) failed to fetch")
        return False
    
    return True


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
        return {}, '', '', '', '', {}, config_path_resolved
    
    # Extract values
    server_ip = config.get('hw_server_host', 'localhost')
    server_port = str(config.get('hw_server_port', '3121'))
    bitstream = config.get('bit_file', '')
    probes = config.get('ltx_file', '')
    vio_outputs = config.get('vio_outputs', {})
    
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
    
    return config, server_ip, server_port, bitstream, probes, vio_outputs, config_path_resolved


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
    print("  -ic <cmd1> <cmd2> ...    Run commands then exit (e.g., -ic 2 v1)")
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
    print("  hdlforge --tool hw_server -c config.json -ic 2 v1")
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
    print("  6                  Pull release (fetch files from git tag)")
    print("  q                  Exit")
    print()
    print("  ila-v-<n>          View ILA (ila-v-1, ila-v-2, ...)")
    print("  ila-save-ila-<n>   Save ILA as .ila")
    print("  ila-save-vcd-<n>   Save ILA as .vcd")
    print("  ila-save-csv-<n>   Save ILA as .csv")
    print()
    print("  vio-v-<n>          View VIO (vio-v-1, vio-v-2, ...)")
    print("  vio-set-f-<n>      Set VIO from config.json")
    print("  vio-set-hex-<n>    Set VIO manually (hex only)")
    print()
    print("VIO VALUES:")
    print("  <- = Input (read from FPGA)")
    print("  -> = Output (write to FPGA)")
    print("  Values shown are from hardware after refresh")
    print()
    print("=" * 80)
