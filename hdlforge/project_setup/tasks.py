#!/usr/bin/env python

import os
from contextlib import redirect_stdout
import sys
import subprocess
from pathlib import Path
import inspect
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import Timer
from tabulate import tabulate


from pyparsing import Union
import argparse
import invoke
from invoke import run, Context

from typing import List, Dict, Any,Tuple
import warnings
import re
# Import task handlers
from verilator_tasks import Verilator
from network_tasks import network
from vcd_analyzer_tasks import vcd_analyzer
from tshark_wrapper_tasks import tshark_wrapper, help_tshark_wrapper
from hw_server_tasks import hw_server, help_hw_server

# Import project loader (single source of truth for project data)
from project_file import ProjectFile
from hdlforge_command_tree import help_text, parse
from vivado_console import project_console
import vivado_build
import vivado_build_tools


def normalize_cli_args(argv: List[str]) -> List[str]:
    normalized = []
    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--flags" and idx + 1 < len(argv):
            normalized.append(f"--flags={argv[idx + 1]}")
            idx += 2
            continue
        normalized.append(arg)
        idx += 1
    return normalized


def _load_help_project(project: str | None) -> ProjectFile | None:
    if project is None:
        root_folder = Path(os.environ.get("ROOT_FOLDER", os.getcwd()))
        project_files = sorted(root_folder.glob("*.hdlforge.json"))
        project_files.extend(sorted(root_folder.glob("*.hdlforge.toml")))
        if len(project_files) != 1:
            return None
        project = str(project_files[0])

    try:
        return ProjectFile(project)
    except SystemExit:
        return None


def _as_token_list(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(value) for value in raw_value]
    return [str(raw_value)]


def _print_token_table(tokens: List[str]) -> None:
    for index, token in enumerate(tokens, start=1):
        print(f"    {index:3d}. {token}")


def print_verilator_project_flag_help(project: str | None, sim_target_name: str | None) -> None:
    project_file = _load_help_project(project)
    if project_file is None:
        return

    build_args = project_file.verilator_config.get("build_args", {})
    flag_tokens = _as_token_list(
        build_args.get("verilator_flags") if isinstance(build_args, dict) else build_args
    )

    print("PROJECT BUILD_ARGS FLAG CATALOG:")
    print(f"  Project: {project_file.project_file_path}")
    print("  JSON:    verilator.config.build_args.verilator_flags")
    print(f"  Count:   {len(flag_tokens)}")
    if flag_tokens:
        _print_token_table(flag_tokens)
    else:
        print("    (none)")
    print()

    if not sim_target_name:
        return

    sim_target = project_file.get_sim_target(sim_target_name)
    target_tokens = _as_token_list((sim_target or {}).get("build_args"))
    print("ACTIVE SIM TARGET BUILD_ARGS:")
    print(f"  Target: {sim_target_name}")
    print(f"  Count:  {len(target_tokens)}")
    if target_tokens:
        _print_token_table(target_tokens)
    else:
        print("    (none)")
    print()


def projects(c, set_project=None, list_projects=False):
    """
    List available projects recursively from the current directory.
    
    Args:
        c: Invoke context
        set_project: Optional project to set (not currently used)
        list_projects: If True, recursively search and list all projects. If False, show single detected project.
    """
    ROOT_FOLDER = Path(os.environ.get("ROOT_FOLDER", os.getcwd()))
    
    if list_projects:
        # Recursively search for all project files
        json_files = list(ROOT_FOLDER.rglob("*.hdlforge.json"))
        toml_files = list(ROOT_FOLDER.rglob("*.hdlforge.toml"))
        project_files = json_files + toml_files
        
        if len(project_files) == 0:
            print("❌ No .hdlforge.json or .hdlforge.toml files found recursively from current directory")
            print(f"  Searched from: {ROOT_FOLDER}")
            return
        
        # Collect project information
        projects_data = []
        for project_file_path in project_files:
            try:
                # Temporarily set ROOT_FOLDER to project file directory for ProjectFile to work
                original_root = os.environ.get("ROOT_FOLDER")
                os.environ["ROOT_FOLDER"] = str(project_file_path.parent)
                
                project_file = ProjectFile(project_file_path)
                projects_data.append({
                    'file': project_file_path.name,
                    'name': project_file.project_name or '(unnamed)',
                    'path': str(project_file_path),
                    'working_path': str(project_file.working_path)
                })
                
                # Restore original ROOT_FOLDER
                if original_root:
                    os.environ["ROOT_FOLDER"] = original_root
                else:
                    os.environ.pop("ROOT_FOLDER", None)
            except (SystemExit, Exception) as e:
                # If we can't load the project, still show the file
                projects_data.append({
                    'file': project_file_path.name,
                    'name': '(error loading)',
                    'path': str(project_file_path),
                    'working_path': str(project_file_path.parent)
                })
        
        # Display in formatted table
        if projects_data:
            print(f"Found {len(projects_data)} project(s) recursively from {ROOT_FOLDER}:\n")
            headers = ['Project File', 'Project Name', 'Path', 'Working Directory']
            rows = []
            for proj in projects_data:
                rows.append([
                    proj['file'],
                    proj['name'],
                    proj['path'],
                    proj['working_path']
                ])
            print(tabulate(rows, headers=headers, tablefmt='grid'))
    else:
        # Show single detected project (current behavior)
        try:
            project_file = ProjectFile(None)
            print(f"Found project: {project_file.project_file_path.name}")
            print(f"  Path: {project_file.project_file_path}")
            print(f"  Project Name: {project_file.project_name}")
            print(f"  Working Path: {project_file.working_path}")
        except SystemExit:
            # ProjectFile will handle error messages
            pass


def _show_command_help(command: str) -> None:
    print(help_text(parse([command] if command else [], Path.cwd())))


def help(c):
    _show_command_help('')


def help_vivado():
    _show_command_help('vivado')


def help_verilator(project: str | None = None, sim_target_name: str | None = None):
    _show_command_help('Verilator')
    print_verilator_project_flag_help(project, sim_target_name)


def help_network():
    _show_command_help('network')


def help_vcd_analyzer():
    _show_command_help('vcd_analyzer')


def help_projects():
    _show_command_help('projects')


if __name__ == "__main__":
    # Get original CWD from environment (set by hdlforge bash script) or fallback to current dir
    ORIGINAL_CWD = os.environ.get('HDLFORGE_ORIG_DIR', os.getcwd())

    # Console arguments belong to its own parser; keep --cmd and --help intact.
    console_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    console_parser.add_argument('--tool')
    console_parser.add_argument('--project')
    console_parser.add_argument('--get_xpr_path', action='store_true')
    console_parser.add_argument('--project_console')
    console_parser.add_argument('--monitor', nargs='?', const='help')
    console_parser.add_argument('--build', nargs='?', const='')
    console_parser.add_argument('--create')
    console_parser.add_argument('--init_build_example', action='store_true')
    console_parser.add_argument('--init_build')
    console_parser.add_argument('--build_status', action='store_true')
    console_parser.add_argument('--build_status_all', action='store_true')
    console_parser.add_argument('--build_stop_all', action='store_true')
    console_parser.add_argument('--build_find_all_user_runs', action='store_true')
    console_parser.add_argument('--build_clean_ignore_artifacts', action='store_true')
    console_parser.add_argument('--dry-run', action='store_true')
    console_parser.add_argument('--build_create')
    console_parser.add_argument('--build_lint', action='store_true')
    console_args, console_tail = console_parser.parse_known_args(sys.argv[1:])
    if console_args.dry_run:
        cleanup = console_args.build_clean_ignore_artifacts or (
            console_args.build is not None and '--clean_ignore_artifacts' in console_tail)
        other_actions = any(getattr(console_args, flag) for flag in (
            'build_stop_all', 'build_find_all_user_runs', 'build_create',
            'build_status', 'build_status_all', 'create', 'monitor',
            'project_console', 'get_xpr_path', 'init_build', 'init_build_example', 'build_lint'))
        if console_args.tool != 'vivado' or not cleanup or other_actions:
            console_parser.error('Native --dry-run supports artifact cleanup only; no action was executed')
        console_tail.append('--dry-run')
    management = [flag for flag in ('build_stop_all', 'build_find_all_user_runs', 'build_clean_ignore_artifacts', 'build_create') if getattr(console_args, flag)]
    if console_args.tool == 'vivado' and management:
        os.chdir(ORIGINAL_CWD)
        if len(management) != 1 or console_args.build is not None or console_args.build_status or console_args.build_status_all or console_args.create or console_args.monitor or console_args.project_console or console_args.get_xpr_path or console_args.init_build or console_args.init_build_example or console_args.build_lint:
            console_parser.error('Choose one build management action without --build')
        action = management[0]
        mapped = {'build_stop_all': '--stopall', 'build_find_all_user_runs': '--find_all_user_runs', 'build_clean_ignore_artifacts': '--clean_ignore_artifacts'}
        action_argv = ['--create', console_args.build_create] if action == 'build_create' else [mapped[action]]
        if console_args.project:
            action_argv.extend(['--project', console_args.project])
        runner = vivado_build_tools if action == 'build_create' else vivado_build
        sys.exit(runner.main(action_argv + console_tail))
    if console_args.tool == 'vivado' and (console_args.build_status or console_args.build_status_all):
        os.chdir(ORIGINAL_CWD)
        if (console_args.build_status and console_args.build_status_all) or console_args.build is not None or console_args.create or console_args.monitor or console_args.project_console or console_args.get_xpr_path or console_args.init_build_example or console_args.init_build or console_args.build_lint:
            console_parser.error('Choose --build_status or --build_status_all without other Vivado actions')
        status_argv = ['--build_status_all' if console_args.build_status_all else '--build_status']
        if console_args.project:
            status_argv.extend(['--project', console_args.project])
        sys.exit(vivado_build.main(status_argv + console_tail))
    if console_args.tool == 'vivado' and console_args.create is not None:
        os.chdir(ORIGINAL_CWD)
        if console_args.build != '' or console_args.monitor or console_args.project_console or console_args.get_xpr_path or console_args.init_build_example or console_args.build_lint:
            console_parser.error('--create requires --build without a run selector or other action')
        config_argv = ['--create', console_args.create]
        if console_args.project:
            config_argv.extend(['--project', console_args.project])
        sys.exit(vivado_build_tools.main(config_argv + console_tail))
    if console_args.tool == 'vivado' and (console_args.init_build_example or console_args.init_build or console_args.build_lint):
        os.chdir(ORIGINAL_CWD)
        if console_args.build is not None or console_args.monitor or console_args.project_console or console_args.get_xpr_path:
            console_parser.error('Build configuration actions cannot be combined with other Vivado actions')
        config_argv = []
        if console_args.init_build:
            config_argv.extend(['--init_build', console_args.init_build])
        if console_args.init_build_example:
            config_argv.append('--init_build_example')
        if console_args.build_lint:
            config_argv.append('--build_lint')
        if console_args.project:
            config_argv.extend(['--project', console_args.project])
        sys.exit(vivado_build_tools.main(config_argv + console_tail))
    if console_args.tool == 'vivado' and console_args.build is not None:
        os.chdir(ORIGINAL_CWD)
        if console_args.monitor or console_args.project_console or console_args.get_xpr_path:
            console_parser.error('--build cannot be combined with other Vivado actions')
        build_argv = ['--build']
        if console_args.build:
            build_argv.append(console_args.build)
        if console_args.project:
            build_argv.extend(['--project', console_args.project])
        sys.exit(vivado_build.main(build_argv + console_tail))
    if console_args.tool == 'vivado' and console_args.monitor:
        os.chdir(ORIGINAL_CWD)
        if console_args.project_console or console_args.get_xpr_path:
            console_parser.error('--monitor cannot be combined with project management actions')
        monitor_script = Path(os.environ.get('REPO_TOP', ORIGINAL_CWD)) / 'tools/vivado_monitor/vivado_monitor.py'
        if not monitor_script.is_file():
            console_parser.error(f'Monitor is not installed in this repository: {monitor_script}')
        action = console_args.monitor
        if action in {'help', 'help-slack', 'help-verbose'}:
            action = '-' + action
        monitor_argv = [sys.executable, str(monitor_script)]
        if console_args.project:
            monitor_argv.extend(['--project', console_args.project])
        sys.exit(subprocess.call([*monitor_argv, action, *console_tail]))
    if console_args.tool == 'vivado' and (console_args.get_xpr_path or console_args.project_console):
        os.chdir(ORIGINAL_CWD)
        if console_args.get_xpr_path and console_args.project_console:
            console_parser.error('--get_xpr_path and --project_console are separate actions')
        if console_args.get_xpr_path:
            if console_tail:
                console_parser.error('--get_xpr_path takes no additional options')
            with redirect_stdout(sys.stderr):
                selected_project = ProjectFile(console_args.project)
                selected_project.require_vivado_project_name()
            print(selected_project.vivado_project_xpr_path.resolve())
            sys.exit(0)
        console_argv = [console_args.project_console]
        if console_args.project:
            console_argv.extend(['--project-json', console_args.project])
        sys.exit(project_console.main(console_argv + console_tail))
    
    parser = argparse.ArgumentParser(
        description='HDLForge - Hardware Development Tool',
        allow_abbrev=console_args.tool != 'vivado',
        add_help=False  # We'll handle help manually
    )
    parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    parser.add_argument('--project', required=False, help='Project file path')
    parser.add_argument('--tool', required=False, choices=['vivado', 'Verilator', 'network', 'vcd_analyzer', 'tsharkWrapper', 'hw_server', 'projects'], 
                       help='Tool to execute: vivado, Verilator, network, vcd_analyzer, tsharkWrapper, hw_server, or projects (required)')
    
    # Common arguments for all tools
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    # Verilator arguments
    parser.add_argument('--step', action='append', help='Verilator step (build, sim, lint)')
    parser.add_argument('--SimTargetName', help='Simulation target name')
    parser.add_argument('--clean', action='store_true', help='Clean before building')
    parser.add_argument('--flags', action='append', help='Additional Verilator flags; may be repeated')
    parser.add_argument('--file', dest='project_lint_file', action='append', help='Project-relative Verilator source file(s) for dependency-aware lint')
    parser.add_argument('--lint-file', action='append', help='Project-relative Verilator source file(s) for raw selected-file lint')
    parser.add_argument('--extra-env', help='Extra environment variables')
    
    parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation prompts')

    # Network, hw_manager, and hw_server tool arguments (shared --cmd)
    # For hw_server, --cmd can be used multiple times and accepts any string (menu selections)
    # For other tools, it's a single command from the choices list
    parser.add_argument('--cmd', type=str, action='append',
                       help='Command: network (send_raw, send_arp, send_icmp, send_udp), hw_manager (program, read_dna, read_ila), or hw_server (any menu selection, can be used multiple times)')
    parser.add_argument('--interface', type=str, help='Network interface name')
    parser.add_argument('--data', type=str, help='Raw data as hex string')
    # ARP arguments
    parser.add_argument('--arp_op', type=int, help='ARP operation: 1=request, 2=reply')
    parser.add_argument('--eth_dst_mac', type=str, help='Ethernet destination MAC address (default: FF:FF:FF:FF:FF:FF for requests)')
    parser.add_argument('--eth_src_mac', type=str, help='Ethernet source MAC address')
    parser.add_argument('--src_mac', type=str, help='ARP source MAC address')
    parser.add_argument('--dst_mac', type=str, help='ARP destination MAC address')
    parser.add_argument('--src_ip', type=str, help='Source IP address')
    parser.add_argument('--dst_ip', type=str, help='Destination IP address')
    # ICMP arguments
    parser.add_argument('--icmp_type', type=int, help='ICMP type: 8=echo request, 0=echo reply')
    parser.add_argument('--icmp_code', type=int, help='ICMP code')
    parser.add_argument('--identifier', type=int, help='ICMP identifier')
    parser.add_argument('--sequence', type=int, help='ICMP sequence number')
    # UDP arguments
    parser.add_argument('--src_port', type=int, help='Source UDP port')
    parser.add_argument('--dst_port', type=int, help='Destination UDP port')
    
    # VCD analyzer arguments
    parser.add_argument('--vcdfilename', type=str, help='VCD file to analyze')
    parser.add_argument('--get_modules_list', action='store_true', help='List all modules in the design')
    parser.add_argument('--get_values_pins', type=str, help='Module path to list value changes for pins only (excludes sub-modules)')
    parser.add_argument('--get_values_all', type=str, help='Module path to list value changes for all signals (excludes sub-modules)')
    parser.add_argument('--human', action='store_true', help='Human-readable output format with padding (for --get_values_pins or --get_values_all)')
    
    # tshark wrapper arguments
    parser.add_argument('--pcap', type=str, help='PCAP file to analyze')
    parser.add_argument('--format', type=str, choices=['to_plain_text'], default='to_plain_text',
                       help='Output format (default: to_plain_text)')
    parser.add_argument('--frame', type=int, help='Display only this frame number')
    parser.add_argument('--frame_start', type=int, help='Start frame number for range (requires --frame_end)')
    parser.add_argument('--frame_end', type=int, help='End frame number for range (requires --frame_start)')
    parser.add_argument('--frame_list', type=str, help='Comma-separated list of frame numbers to display')
    parser.add_argument('--count', type=int, help='Number of packets to display (use with --skip for pagination)')
    parser.add_argument('--skip', type=int, help='Skip this many packets before displaying')
    parser.add_argument('--tsharkArgsAppend', type=str, help='Additional raw tshark arguments to append')
    parser.add_argument('--disable_heuristics', action='store_true', help='Disable UDP heuristic protocol dissectors')
    parser.add_argument('--disable_protocols', type=str, help='Comma-separated list of protocols to disable (e.g., mndp,ssdp)')
    
    parser.add_argument('--action', type=str, choices=['write', 'read', 'write-all', 'read-all'], help='Config reg action: write, read, write-all, read-all')
    
    # hw_server arguments (--cmd is shared with network tool above)
    parser.add_argument('--server_ip', '--server-ip', dest='server_ip', type=str, help='Hardware server IP (default: localhost)')
    parser.add_argument('--bitstream', type=str, help='Path to bitstream file (.bit file)')
    parser.add_argument('--probes', type=str, help='Path to probes file (.ltx file)')
    parser.add_argument('-c', '--hw-config', '--config-file', dest='hw_config', type=str, help='Config JSON file for hw_server (auto-detected from invoke location if not provided)')
    parser.add_argument('-i', '--interactive', dest='hw_interactive', action='store_true', help='Interactive mode for hw_server (keep console open)')
    parser.add_argument('-ic', '--interactive-chain', dest='hw_chain', nargs='*', help='Run commands then exit for hw_server (e.g., -ic 2 i1)')
    parser.add_argument('-d', '--debug', dest='hw_debug', action='store_true', help='Enable debug output showing TCL commands and inputs')
    
    # Projects tool arguments
    parser.add_argument('--list', action='store_true', help='List all available projects recursively from current directory')
    
    # Use parse_known_args to detect extra arguments for better error messages
    args, unknown = parser.parse_known_args(normalize_cli_args(sys.argv[1:]))
    
    # Check for common mistakes with vcd_analyzer
    if args.tool == 'vcd_analyzer' and args.get_modules_list and unknown:
        print("[!x!] Error: --get_modules_list does not accept arguments", file=sys.stderr)
        print(f"[i] Unrecognized arguments: {' '.join(unknown)}", file=sys.stderr)
        print("[i] Note: --get_modules_list is a flag (no arguments). If you want to filter modules:", file=sys.stderr)
        print("[i]   Use grep: hdlforge vcd_analyzer.modules --vcdfilename <file> | grep 'pattern'", file=sys.stderr)
        print("[i]   Or quote wildcards to prevent shell expansion when typing the command", file=sys.stderr)
        sys.exit(1)
    
    # For other cases with unknown arguments, show standard argparse error
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    
    # Create invoke Context manually
    c = Context()
    
    # Handle help at top level
    if args.help:
        if args.tool:
            # Show tool-specific help
            if args.tool == 'vivado':
                help_vivado()
            elif args.tool == 'Verilator':
                help_verilator(args.project, args.SimTargetName)
            elif args.tool == 'network':
                help_network()
            elif args.tool == 'vcd_analyzer':
                help_vcd_analyzer()
            elif args.tool == 'tsharkWrapper':
                help_tshark_wrapper()
            elif args.tool == 'hw_server':
                help_hw_server()
            elif args.tool == 'projects':
                help_projects()
            sys.exit(0)
        else:
            help(c)
            sys.exit(0)
    
    # Handle no tool provided - show main help and exit
    if not args.tool:
        print("[!x!] Error: --tool is required")
        print()
        help(c)
        sys.exit(1)
    
    # Handle command dispatch based on --tool
    if args.tool == 'Verilator':
        if not args.step and (args.lint_file or args.project_lint_file):
            args.step = ["lint"]
        # Check if required arguments are missing - show help
        steps = args.step or []
        targetless_file_lint = (
            steps
            and all(step == "lint" for step in steps)
            and bool(args.lint_file or args.project_lint_file)
        )
        if not args.SimTargetName and not args.help and not targetless_file_lint:
            help_verilator(args.project, args.SimTargetName)
            sys.exit(0)
        Verilator(
            c,
            args.project,
            args.step,
            args.clean,
            args.SimTargetName,
            args.flags,
            args.extra_env,
            args.lint_file,
            args.project_lint_file,
        )
    elif args.tool == 'vivado':
        help_vivado()
    elif args.tool == 'network':
        # Network tool selected
        cmd_list = args.cmd if args.cmd else []
        if not cmd_list:
            help_network()
            sys.exit(0)
        # For network tool, only allow single command
        if len(cmd_list) > 1:
            parser.error("--cmd can only be used once for network tool")
        cmd_value = cmd_list[0]
        # Validate cmd is a network command
        if cmd_value not in ['send_raw', 'send_arp', 'send_icmp', 'send_udp']:
            print(f"[!x!] Invalid command for network tool: {cmd_value}")
            print("[i] Network commands: send_raw, send_arp, send_icmp, send_udp")
            help_network()
            sys.exit(1)
        # Prepare kwargs from args
        kwargs = {
            'interface': args.interface,
            'data': args.data,
            'verbose': args.verbose,
            'arp_op': args.arp_op,
            'eth_dst_mac': args.eth_dst_mac,
            'eth_src_mac': args.eth_src_mac,
            'src_mac': args.src_mac,
            'dst_mac': args.dst_mac,
            'src_ip': args.src_ip,
            'dst_ip': args.dst_ip,
            'icmp_type': args.icmp_type,
            'icmp_code': args.icmp_code,
            'identifier': args.identifier,
            'sequence': args.sequence,
            'src_port': args.src_port,
            'dst_port': args.dst_port,
            'fpga_ip': args.fpga_ip,
            'fpga_port': args.fpga_port,
            'server_port': args.server_port,
            'server_ip': args.server_ip,
            'reg': args.reg,
            'value': args.value,
            'subcmd': args.action  # Use --action for the subcommand (write, read, etc.)
        }
        network(c, cmd_value, **kwargs)
    elif args.tool == 'vcd_analyzer':
        # VCD analyzer tool selected
        kwargs = {
            'vcd': args.vcdfilename,
            'get_modules_list': args.get_modules_list,
            'list_value_changes_in_module': args.get_values_pins or args.get_values_all,  # Use whichever is provided
            'all': args.get_values_all is not None,  # True if --get_values_all was provided, False if --get_values_pins
            'human': args.human,
        }
        vcd_analyzer(c, **kwargs)
    elif args.tool == 'tsharkWrapper':
        # tshark wrapper tool
        if not args.pcap:
            help_tshark_wrapper()
            sys.exit(0)
        
        # Parse frame_list if provided
        frame_list = None
        if args.frame_list:
            frame_list = [int(x.strip()) for x in args.frame_list.split(',')]
        
        tshark_wrapper(c, 
                       pcap_file=args.pcap,
                       output_format=args.format,
                       frame_number=args.frame,
                       frame_start=args.frame_start,
                       frame_end=args.frame_end,
                       frame_list=frame_list,
                       count=args.count,
                       skip=args.skip,
                       tshark_args_append=args.tsharkArgsAppend,
                       disable_heuristics=args.disable_heuristics,
                       disable_protocols=args.disable_protocols,
                       verbose=args.verbose)
    elif args.tool == 'hw_server':
        # hw_server tool - interactive FPGA programming and debugging
        # For hw_server, --cmd can be a list (multiple --cmd arguments)
        cmd_list = args.cmd if args.cmd else []
        
        hw_server(c, 
                  cmd=None,  # Single cmd not used for hw_server when cmd_list is provided
                  cmd_list=cmd_list,  # List of cmds for hw_server (menu selections)
                  server_ip=args.server_ip,
                  server_port=getattr(args, 'server_port', '3121'),
                  bitstream=args.bitstream,
                  probes=args.probes,
                  config_file=getattr(args, 'hw_config', ''),
                  interactive=getattr(args, 'hw_interactive', False),
                  chain_commands=getattr(args, 'hw_chain', []),
                  debug=getattr(args, 'hw_debug', False),
                  original_cwd=ORIGINAL_CWD)
    elif args.tool == 'projects':
        # Projects tool requires --list option
        if not getattr(args, 'list', False):
            help_projects()
            sys.exit(0)
        projects(c, getattr(args, 'set_project', None), list_projects=True)
