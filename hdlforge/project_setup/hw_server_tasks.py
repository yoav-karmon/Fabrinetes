#!/usr/bin/env python3
"""
HW Server task handler for HDLForge
Interactive FPGA programming and debugging with persistent Vivado console
"""

import json
import os
import sys
from typing import Dict, Optional, List

from hw_server_console import VivadoTCLConsole


def hw_server(c, cmd: str = None, **kwargs):
    """
    HW Server command handler - Interactive FPGA programming and debugging.
    
    Args:
        c: Invoke context
        cmd: Command to execute (program, scan_ila, scan_jtag, etc.)
        **kwargs: Additional arguments
    """
    # Get configuration from kwargs
    server_ip = kwargs.get('server_ip', '')
    server_port = kwargs.get('server_port', '')
    bitstream = kwargs.get('bitstream', '')
    probes = kwargs.get('probes', '')
    config_file = kwargs.get('config_file', '')  # Only use if explicitly provided with -c
    interactive = kwargs.get('interactive', False)  # -i flag
    chain_commands = kwargs.get('chain_commands', [])  # -ic commands
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
            print(f"[!x!] Config file not found or invalid: {config_path}")
            sys.exit(1)
        print(f"Loaded config from: {config_path}")
    
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
    valid_cmds = ['program', 'scan_ila', 'scan_jtag', 'read_dna']
    if cmd and cmd not in valid_cmds:
        print(f"[!x!] Unknown command: {cmd}")
        print(f"[i] Valid commands: {', '.join(valid_cmds)}")
        sys.exit(1)
    
    # If no command and not interactive mode, show help
    if not cmd and not interactive and not chain_commands:
        help_hw_server()
        return
    
    # Print header
    print("=" * 60, flush=True)
    print("HW Server - Interactive FPGA Tools", flush=True)
    print("=" * 60, flush=True)
    print(f"  Server:    {server_ip}:{server_port}", flush=True)
    print(f"  Work dir:  {invoked_cwd}", flush=True)
    if bitstream:
        print(f"  Bitstream: {os.path.basename(bitstream)}", flush=True)
    if probes:
        print(f"  Probes:    {os.path.basename(probes)}", flush=True)
    
    # Start Vivado console (from invoked location for logs)
    console = VivadoTCLConsole(working_dir=invoked_cwd, debug=debug)
    
    try:
        print("\nInitializing Vivado TCL console...", flush=True)
        if not console.start():
            print("[!x!] Failed to start Vivado")
            sys.exit(1)
        
        print("Connecting to hardware server...", flush=True)
        if not console.connect_hw_server(server_ip, server_port):
            print("[!x!] Failed to connect to hardware server")
            sys.exit(1)
        
        print(f"Connected successfully!", flush=True)
        print(f"Target: {console.target}", flush=True)
        print(f"Device: {console.device}", flush=True)
        
        # Execute single command if provided
        if cmd:
            _execute_command(console, cmd, bitstream, probes)
        
        # Execute chain commands if provided (-ic)
        if chain_commands:
            print("\n" + "=" * 60, flush=True)
            print("[BATCH MODE] Command Chain", flush=True)
            print("=" * 60, flush=True)
            # Also show descriptions next to each command
            described = []
            for cmd_token in chain_commands:
                desc = _describe_chain_command(cmd_token)
                if desc:
                    described.append(f"{cmd_token} ({desc})")
                else:
                    described.append(cmd_token)
            print(f"Commands: {'  '.join(described)}", flush=True)
            total = len(chain_commands)
            for idx, chain_cmd in enumerate(chain_commands, start=1):
                label = chain_cmd
                desc = _describe_chain_command(chain_cmd)
                if desc:
                    label = f"{chain_cmd} ({desc})"
                print("\n" + "-" * 60, flush=True)
                print(f"[BATCH MODE] Executing ({idx}/{total}): {label}", flush=True)
                print("-" * 60, flush=True)
                ok = _execute_menu_choice(console, chain_cmd, bitstream, probes, vio_outputs, force_commit)
                status = "COMPLETED" if ok else "FAILED or EXIT REQUESTED"
                print(f"[BATCH MODE] Completed ({idx}/{total}): {label}  -> {status}", flush=True)
                if not ok:
                    break
        
        # Interactive mode (-i)
        if interactive:
            _interactive_loop(console, bitstream, probes, vio_outputs, config_path)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\n[!x!] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        console.close()
        print("\nVivado console closed.")


def _execute_command(console: VivadoTCLConsole, cmd: str, bitstream: str, probes: str) -> bool:
    """Execute a single command."""
    if cmd == 'program':
        if not bitstream:
            print("[!x!] Bitstream file must be specified with --bitstream or in config file")
            return False
        return console.program_fpga(bitstream, probes)
    
    elif cmd == 'scan_ila':
        if not probes:
            print("[!x!] Probes file must be specified with --probes or in config file")
            return False
        return console.scan_ila_vio(probes)
    
    elif cmd == 'scan_jtag' or cmd == 'read_dna':
        return console.scan_jtag()
    
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


def _execute_menu_choice(console: VivadoTCLConsole, choice: str, 
                         bitstream: str, probes: str, 
                         vio_outputs: dict = None, force: bool = False) -> bool:
    """Execute a menu choice. Returns False if should exit."""
    choice = choice.lower().strip()
    
    if choice == "1" or choice == "program":
        return _execute_command(console, 'program', bitstream, probes)
    elif choice == "2" or choice == "scan_ila":
        return _execute_command(console, 'scan_ila', bitstream, probes)
    elif choice == "3" or choice == "scan_jtag":
        return _execute_command(console, 'scan_jtag', bitstream, probes)
    elif choice in ("q", "quit", "exit"):
        return False
    # ILA view/save commands
    # New names:
    #   ila-v-1          -> view ILA 1
    #   ila-save-ila-1   -> save ILA 1 as .ila
    #   ila-save-vcd-1   -> save ILA 1 as .vcd
    #   ila-save-csv-1   -> save ILA 1 as .csv
    if choice.startswith("ila-v-"):
        try:
            ila_idx = int(choice[len("ila-v-"):]) - 1
            console.print_ila_details(ila_idx)
        except ValueError:
            print(f"Invalid ILA selection: {choice}")
    elif choice.startswith("ila-save-ila-"):
        try:
            ila_idx = int(choice[len("ila-save-ila-"):]) - 1
            console.save_ila_data(ila_idx, fmt="ila")
        except ValueError:
            print(f"Invalid ILA save selection: {choice}")
    elif choice.startswith("ila-save-vcd-"):
        try:
            ila_idx = int(choice[len("ila-save-vcd-"):]) - 1
            console.save_ila_data(ila_idx, fmt="vcd")
        except ValueError:
            print(f"Invalid VCD save selection: {choice}")
    elif choice.startswith("ila-save-csv-"):
        try:
            ila_idx = int(choice[len("ila-save-csv-"):]) - 1
            console.save_ila_data(ila_idx, fmt="csv")
        except ValueError:
            print(f"Invalid CSV save selection: {choice}")
    # Backwards-compatible short ILA commands (i1, is1, iw1, ic1)
    elif choice.startswith("i") and len(choice) > 1 and not choice.startswith("is"):
        try:
            ila_idx = int(choice[1:]) - 1
            console.print_ila_details(ila_idx)
        except ValueError:
            print(f"Invalid ILA selection: {choice}")
    elif choice.startswith("is") and len(choice) > 2:
        try:
            ila_idx = int(choice[2:]) - 1
            console.save_ila_data(ila_idx, fmt="ila")
        except ValueError:
            print(f"Invalid ILA save selection: {choice}")
    elif choice.startswith("iw") and len(choice) > 2:
        try:
            ila_idx = int(choice[2:]) - 1
            console.save_ila_data(ila_idx, fmt="vcd")
        except ValueError:
            print(f"Invalid VCD save selection: {choice}")
    elif choice.startswith("ic") and len(choice) > 2:
        try:
            ila_idx = int(choice[2:]) - 1
            console.save_ila_data(ila_idx, fmt="csv")
        except ValueError:
            print(f"Invalid CSV save selection: {choice}")

    # VIO view/set commands
    # New names:
    #   vio-v-1        -> view VIO 1
    #   vio-set-f-1    -> set from config for VIO 1
    #   vio-set-hex-1  -> set manually (hex) for VIO 1
    elif choice.startswith("vio-v-"):
        try:
            vio_idx = int(choice[len("vio-v-"):]) - 1
            console.print_vio_details(vio_idx, vio_outputs)
        except ValueError:
            print(f"Invalid VIO selection: {choice}")
    elif choice.startswith("vio-set-f-"):
        try:
            vio_idx = int(choice[len("vio-set-f-"):]) - 1
            _set_vio_values_for_index(console, vio_idx, vio_outputs, force)
        except ValueError:
            print(f"Invalid VIO set selection: {choice}")
    elif choice.startswith("vio-set-hex-"):
        try:
            vio_idx = int(choice[len("vio-set-hex-"):]) - 1
            _set_vio_values_manual(console, vio_idx)
        except ValueError:
            print(f"Invalid manual VIO set selection: {choice}")

    # Backwards-compatible short VIO commands (v1, sv1, vh1)
    elif choice.startswith("v") and len(choice) > 1 and not choice.startswith("sv") and not choice.startswith("vh"):
        try:
            vio_idx = int(choice[1:]) - 1
            console.print_vio_details(vio_idx, vio_outputs)
        except ValueError:
            print(f"Invalid VIO selection: {choice}")
    elif choice.startswith("sv") and len(choice) > 2:
        try:
            vio_idx = int(choice[2:]) - 1
            _set_vio_values_for_index(console, vio_idx, vio_outputs, force)
        except ValueError:
            print(f"Invalid VIO set selection: {choice}")
    elif choice.startswith("vh") and len(choice) > 2:
        try:
            vio_idx = int(choice[2:]) - 1
            _set_vio_values_manual(console, vio_idx)
        except ValueError:
            print(f"Invalid manual VIO set selection: {choice}")
    else:
        print(f"\nInvalid option: {choice}")
    
    return True


def _set_vio_values_for_index(console: VivadoTCLConsole, vio_idx: int, 
                               vio_outputs: dict, force: bool) -> None:
    """Set VIO values for a specific VIO index using config values directly."""
    vio_list = console._get_vio_list()
    if vio_idx < 0 or vio_idx >= len(vio_list):
        print(f"  ERROR: Invalid VIO index {vio_idx + 1}")
        return
    
    if not vio_outputs:
        print("  ERROR: No VIO outputs configured in config file")
        print("  Add 'vio_outputs' section to your config.json")
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
        print("\n  ERROR: No values configured in config file")
        print("  Edit config.json and set 'value' fields in vio_outputs")
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
        print(f"  ERROR: Invalid VIO index {vio_idx + 1}")
        return

    vio_info = vio_list[vio_idx]
    probe_names = vio_info.get("probe_names", [])
    probe_widths = vio_info.get("probe_widths", {})
    probe_directions = vio_info.get("probe_directions", {})

    print(f"\n--- Set VIO (manual): {vio_info['name']} ---")
    print("  Output probes (hex only):")

    output_probes = []
    for name in probe_names:
        if probe_directions.get(name) == "output":
            width = probe_widths.get(name)
            width_str = f"[{width-1}:0]" if isinstance(width, int) and width > 1 else "[0]"
            print(f"    - {name} {width_str}")
            output_probes.append(name)

    if not output_probes:
        print("  No output probes available to set.")
        return

    while True:
        probe_name = input("\n  Enter probe name to set (or empty to finish): ").strip()
        if not probe_name:
            break
        if probe_name not in output_probes:
            print("  Invalid probe name or not an output probe.")
            continue

        raw_val = input(f"  Enter hex value for {probe_name} (e.g. 0x20 or 20): ").strip()
        if not raw_val:
            print("  Empty value, skipped.")
            continue

        # Strip 0x prefix and spaces, validate hex
        v = raw_val.strip()
        if v.lower().startswith("0x"):
            v = v[2:]
        v = v.replace(" ", "")
        try:
            int(v, 16)
        except ValueError:
            print("  Invalid hex value, try again.")
            continue

        width = probe_widths.get(probe_name)
        # Use radix 'hex'; set_vio_value will pad and commit, and verify via read-back
        if not console.set_vio_value(probe_name, v, radix="hex", width=width, commit=False, force=True):
            print("  Failed to set value, see errors above.")

    # After manual updates, show updated table with explicit header
    console.print_vio_details(vio_idx, vio_outputs=None, header_prefix="Set VIO")



def _print_menu(console: VivadoTCLConsole, bitstream: str, probes: str, vio_outputs: dict = None) -> None:
    """Print the interactive menu."""
    print("\n" + "=" * 60)
    print("HW Server Menu")
    print("=" * 60)
    
    if bitstream:
        print("1. Program FPGA")
    else:
        print("1. Program FPGA (requires --bitstream or -c config)")
    
    if probes:
        print("2. Scan ILA/VIO")
    else:
        print("2. Scan ILA/VIO (requires --probes or -c config)")
    
    print("3. Scan JTAG Targets")
    
    # Dynamic ILA options
    ila_list = console._get_ila_list()
    if console.scanned and ila_list:
        print("-" * 40)
        print("ILA:")
        for i, ila in enumerate(ila_list):
            idx = i + 1
            print(
                f"  ila-v-{idx}  View"
                f"    | ila-save-ila-{idx} Save .ila"
                f"    | ila-save-vcd-{idx} Save .vcd"
                f"    | ila-save-csv-{idx} Save .csv"
            )
    
    # Dynamic VIO options
    vio_list = console._get_vio_list()
    if console.scanned and vio_list:
        print("-" * 40)
        print("VIO:")
        for i, vio in enumerate(vio_list):
            idx = i + 1
            line = f"  vio-v-{idx}  View"
            if vio_outputs:
                line += f"    | vio-set-f-{idx} Set from config"
            line += f"    | vio-set-hex-{idx} Set manual (hex)"
            print(line)
    
    print("-" * 40)
    print("q. Exit")
    print("=" * 60)


def _interactive_loop(console: VivadoTCLConsole, bitstream: str, probes: str, 
                      vio_outputs: dict = None, config_path: str = "") -> None:
    """Run interactive menu loop."""
    while True:
        _print_menu(console, bitstream, probes, vio_outputs)
        try:
            choice = input("\nSelect an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not _execute_menu_choice(console, choice, bitstream, probes, vio_outputs, force=False):
            break


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
        print(f"[!x!] Failed to load config from {config_path}: {e}")
        return {}


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
    print()
    print("COMMANDS:")
    print("  program      Program FPGA with bitstream file")
    print("  scan_ila     Scan for ILA/VIO debug cores")
    print("  scan_jtag    Scan JTAG targets and read chip DNA")
    print()
    print("OPTIONS:")
    print("  -c, --hw-config <FILE>   Config file (required, must exist)")
    print("  -i, --interactive        Interactive mode (keep console open with menu)")
    print("  -ic <cmd1> <cmd2> ...    Run commands then exit (e.g., -ic 2 v1)")
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
    print("INTERACTIVE COMMANDS:")
    print("  1                  Program FPGA")
    print("  2                  Scan ILA/VIO cores")
    print("  3                  Scan JTAG / Read DNA")
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
