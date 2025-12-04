#!/usr/bin/env python

import os
import sys
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
from vivado_tasks import vivado, VivadoStep
from verilator_tasks import Verilator
from network_tasks import network
from vcd_analyzer_tasks import vcd_analyzer
from tshark_wrapper_tasks import tshark_wrapper, help_tshark_wrapper

# Import project loader (single source of truth for project data)
from project_file import ProjectFile


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


def help(c):
    """
    Show HDLForge help information
    
    This task provides comprehensive help for HDLForge usage.
    """
    print("=" * 80)
    print("HDLFORGE - Hardware Description Language Development Tool")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  HDLForge is a unified command-line tool for FPGA development workflows.")
    print("  It provides seamless integration between Vivado synthesis and Verilator simulation.")
    print()
    print("AVAILABLE TASKS:")
    print()
    
    tasks_info = [
        ("vivado", "FPGA Development Tasks", [
            "Create and manage Xilinx Vivado projects",
            "Run synthesis, implementation, and bitstream generation",
            "Supports multiple build flows and configurations"
        ]),
        ("Verilator", "Simulation Tasks", [
            "Compile and run Verilog/SystemVerilog simulations",
            "Uses Verilator compiler with cocotb testbenches",
            "Supports multiple simulation targets and environments"
        ]),
        ("tool", "Utility Tools", [
            "Network utilities: send raw packets (ARP, ICMP, UDP)",
            "VCD analyzer: analyze waveform files",
            "tshark wrapper: wrapper for tshark commands",
            "Use --network, --vcd_analyzer, or --tsharkWrapper to select tool"
        ]),
        ("projects", "Project Management", [
            "Manage HDL project configurations",
            "Set active project and list available projects"
        ])
    ]
    
    for task_name, description, features in tasks_info:
        print(f"  {task_name:<12} - {description}")
        for feature in features:
            print(f"    • {feature}")
        print()
    
    print("QUICK START:")
    print("  1. Set up your project: hdlforge --tool projects")
    print("  2. Generate project with external TCL: hdlforge --tool vivado --generate_prj_with_external_tcl")
    print("  3. Run synthesis: hdlforge --tool vivado --syn <synth_run_name>")
    print("  4. Run simulation: hdlforge --tool Verilator --step build --step sim --SimTargetName <target>")
    print()
    print("GETTING HELP:")
    print("  hdlforge                          # Show this help")
    print("  hdlforge --help                   # Show this help")
    print("  hdlforge --tool <tool> --help      # Show detailed help for specific tool")
    print()
    print("PROJECT CONFIGURATION:")
    print("  Projects are configured using *.hdlforge.json (or *.hdlforge.toml) files in your working directory.")
    print("  The tool automatically detects project files or you can specify them explicitly.")
    print()
    print("DOCUMENTATION:")
    print("  • HDLForge_Documentation.toml - Comprehensive documentation and examples")
    print("  • Contains detailed command structures, build processes, and best practices")
    print("  • Includes troubleshooting guides and configuration examples")
    print()
    print("ENVIRONMENT REQUIREMENTS:")
    print("  • REPO_TOP environment variable must be set")
    print("  • Vivado installation (for FPGA tasks)")
    print("  • Verilator installation (for simulation tasks)")
    print("  • Python packages: invoke, cocotb, tabulate")
    print()
    print("=" * 80)


def help_vivado():
    """
    Show detailed help for Vivado tool
    """
    print("=" * 80)
    print("HDLFORGE VIVADO - FPGA Development Tasks")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Manage Xilinx Vivado projects, run synthesis, implementation, and bitstream generation.")
    print()
    print("USAGE:")
    print("  hdlforge --tool vivado <--arg1> <value1> <--arg2> <value2> ...")
    print()
    print("AVAILABLE STEPS:")
    print()
    print("  Project Management:")
    print("    --generate_prj_with_external_tcl    Generate Vivado project using external TCL script")
    print("    --write_tcl                         Export Vivado project to TCL")
    print("    --list_runs                         List all Vivado runs")
    print()
    print("  Build Steps (require RUN_NAME):")
    print("    --syn <RUN_NAME>                    Run synthesis")
    print("    --impl <RUN_NAME>                   Run implementation")
    print("    --bit <RUN_NAME>                    Generate bitstream")
    print("    --all <RUN_NAME>                    Run synthesis, implementation and bitstream generation")
    print("    --reset_run <RUN_NAME>               Reset a Vivado synth run and all its child impl runs")
    print()
    print("  File Management (require --file_path):")
    print("    --file_add --file_path <PATH>        Add a file to the Vivado project")
    print("    --file_remove --file_path <PATH>     Remove a file from the Vivado project")
    print()
    print("  Other:")
    print("    --lint                               Run lint")
    print("    --clean                              Clean build directory")
    print("    --verbose                            Enable verbose output")
    print("    -f, --force                          Skip confirmation prompts")
    print()
    print("OPTIONS:")
    print("    --project <PATH>                     Specify project file path (optional)")
    print()
    print("=" * 80)


def help_verilator():
    """
    Show detailed help for Verilator tool
    """
    print("=" * 80)
    print("HDLFORGE VERILATOR - Simulation Tasks")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Compile and run Verilog/SystemVerilog simulations using Verilator compiler with cocotb testbenches.")
    print()
    print("USAGE:")
    print("  hdlforge --tool Verilator <--arg1> <value1> <--arg2> <value2> ...")
    print()
    print("REQUIRED ARGUMENTS:")
    print("    --SimTargetName <TARGET>            Simulation target name (must match target in project config)")
    print()
    print("AVAILABLE STEPS:")
    print("    --step build                         Compile SystemVerilog files to C++ executable")
    print("    --step sim                           Run Python Cocotb testbench simulation")
    print()
    print("OPTIONS:")
    print("    --project <PATH>                     Specify project file path (optional)")
    print("    --clean                              Clean build directory before running")
    print("    --flags <FLAGS>                      Additional Verilator compilation flags")
    print("    --extra-env <KEY=VAL,KEY2=VAL2>      Additional environment variables")
    print()
    print("NOTES:")
    print("  • SimTargetName must be defined in your project's verilator_settings.sim_targets")
    print("  • Multiple --step flags can be provided to run multiple steps in sequence")
    print("  • Build step must be run before sim step")
    print()
    print("=" * 80)


def help_network():
    """
    Show detailed help for Network tool
    """
    print("=" * 80)
    print("HDLFORGE NETWORK - Network Utilities")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Network utilities for sending raw packets (ARP, ICMP, UDP).")
    print()
    print("USAGE:")
    print("  hdlforge --tool network --cmd <command> [--arg1] [<value1>] [--arg2] [<value2>] ...")
    print()
    print("AVAILABLE TOOLS:")
    print()
    print("  --network:")
    print("    Network utilities for sending raw packets")
    print()
    print("    send_raw:")
    print("      Send raw bytes to network interface")
    print("      --interface <IFACE>                  Network interface (required)")
    print("      --data <HEX_STRING>                  Raw data as hex string (required)")
    print("      --verbose                            Enable verbose output")
    print()
    print("    send_arp:")
    print("      Send ARP packet")
    print("      --interface <IFACE>                  Network interface (required)")
    print("      --arp_op <1|2>                       ARP operation: 1=request, 2=reply (default: 1)")
    print("      --eth_dst_mac <MAC>                  Ethernet destination MAC (default: FF:FF:FF:FF:FF:FF for requests)")
    print("      --eth_src_mac <MAC>                  Ethernet source MAC (default: interface MAC)")
    print("      --src_mac <MAC>                      ARP source MAC address (default: 00:00:00:00:00:00)")
    print("      --src_ip <IP>                        Source IP address (default: 192.168.1.1)")
    print("      --dst_mac <MAC>                      ARP destination MAC address (default: 00:00:00:00:00:00)")
    print("      --dst_ip <IP>                        Destination IP address (default: 192.168.1.2)")
    print("      --verbose                            Enable verbose output")
    print()
    print("    send_icmp:")
    print("      Send ICMP packet (ping)")
    print("      --interface <IFACE>                  Network interface (required)")
    print("      --eth_dst_mac <MAC>                  Ethernet destination MAC (default: FF:FF:FF:FF:FF:FF)")
    print("      --eth_src_mac <MAC>                  Ethernet source MAC (default: interface MAC)")
    print("      --src_ip <IP>                        Source IP address (default: 192.168.1.1)")
    print("      --dst_ip <IP>                        Destination IP address (default: 192.168.1.2)")
    print("      --icmp_type <TYPE>                   ICMP type: 8=echo request, 0=echo reply (default: 8)")
    print("      --icmp_code <CODE>                   ICMP code (default: 0)")
    print("      --identifier <ID>                    ICMP identifier (default: 0)")
    print("      --sequence <SEQ>                     ICMP sequence number (default: 0)")
    print("      --data <HEX_STRING>                   ICMP data payload as hex string")
    print("      --verbose                            Enable verbose output")
    print()
    print("    send_udp:")
    print("      Send UDP packet")
    print("      --interface <IFACE>                  Network interface (required)")
    print("      --eth_dst_mac <MAC>                  Ethernet destination MAC (default: FF:FF:FF:FF:FF:FF)")
    print("      --eth_src_mac <MAC>                  Ethernet source MAC (default: interface MAC)")
    print("      --src_ip <IP>                        Source IP address (default: 192.168.1.1)")
    print("      --dst_ip <IP>                        Destination IP address (default: 192.168.1.2)")
    print("      --src_port <PORT>                    Source UDP port (default: 12345)")
    print("      --dst_port <PORT>                    Destination UDP port (default: 53)")
    print("      --data <HEX_STRING>                   UDP payload as hex string")
    print("      --verbose                            Enable verbose output")
    print()
    print("NOTES:")
    print("  • Network tools require root privileges (use sudo)")
    print("  • Use tcpdump to capture packets: sudo tcpdump -i <interface> -w capture.pcap")
    print("  • View pcap file: tcpdump -r capture.pcap -X")
    print()
    print("=" * 80)


def help_vcd_analyzer():
    """
    Show detailed help for VCD Analyzer tool
    """
    print("=" * 80)
    print("HDLFORGE VCD_ANALYZER - VCD Waveform Analysis")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Professional VCD waveform analysis tool with signal hierarchy support.")
    print()
    print("USAGE:")
    print("  hdlforge --tool vcd_analyzer [--arg1] [<value1>] [--arg2] [<value2>] ...")
    print()
    print("ARGUMENTS:")
    print("    --vcdfilename <FILE>                   VCD file to analyze (required)")
    print("    --timestamps                           List all timestamps")
    print("    --find_signal_names [PATTERN]                List signal names (optionally filter with wildcard pattern)")
    print("    --signal <SIGNAL>                      Signal name (supports wildcards)")
    print("    --time <TIMESTAMP> [TIMESTAMP ...]     Filter signal results by timestamp(s)")
    print("    --edge [N]                             Show signal edges after --time timestamp (optional N limits edges)")
    print("    --count <N>                            Show N values starting from --time timestamp")
    print("    --verbose                              Show all VCD data including var_id and signal definition")
    print("    --radix <hex|int|bin>                  Output format for calc_value")
    print()
    print("EXAMPLES:")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --timestamps")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --find_signal_names")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --signal 'top.signal' --time 1000")
    print()
    print("=" * 80)


def help_projects():
    """
    Show detailed help for Projects tool
    """
    print("=" * 80)
    print("HDLFORGE PROJECTS - Project Management")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  List all HDL project configurations recursively from the current directory.")
    print()
    print("USAGE:")
    print("  hdlforge --tool projects --list")
    print()
    print("OPTIONS:")
    print("    --list                                 List all available projects recursively from current directory")
    print("    --verbose                              Enable verbose output")
    print()
    print("EXAMPLES:")
    print("  hdlforge --tool projects --list          List all projects recursively from current directory")
    print()
    print("NOTES:")
    print("  • Searches recursively for all *.hdlforge.json and *.hdlforge.toml files")
    print("  • Displays results in a formatted table with project file, name, and path")
    print("  • Projects are configured using *.hdlforge.json or *.hdlforge.toml files")
    print()
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='HDLForge - Hardware Development Tool',
        add_help=False  # We'll handle help manually
    )
    parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    parser.add_argument('--project', required=False, help='Project file path')
    parser.add_argument('--tool', required=False, choices=['vivado', 'Verilator', 'network', 'vcd_analyzer', 'tsharkWrapper', 'projects'], 
                       help='Tool to execute: vivado, Verilator, network, vcd_analyzer, tsharkWrapper, or projects (required)')
    
    # Common arguments for all tools
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    # Verilator arguments
    parser.add_argument('--step', action='append', help='Verilator step (build, sim)')
    parser.add_argument('--SimTargetName', help='Simulation target name')
    parser.add_argument('--clean', action='store_true', help='Clean before building')
    parser.add_argument('--flags', help='Additional flags')
    parser.add_argument('--extra-env', help='Extra environment variables')
    
    # Vivado arguments
    parser.add_argument('--list_runs', action='store_true', help='List all Vivado runs')
    parser.add_argument('--reset_run', type=str, metavar='RUN_NAME', help='Reset a Vivado synth run and all its child impl runs')
    parser.add_argument('--syn', type=str, metavar='RUN_NAME', help='Run synthesis')
    parser.add_argument('--impl', type=str, metavar='RUN_NAME', help='Run implementation')
    parser.add_argument('--bit', type=str, metavar='RUN_NAME', help='Generate bitstream')
    parser.add_argument('--lint', action='store_true', help='Run lint')
    parser.add_argument('--all', type=str, metavar='RUN_NAME', help='Run synthesis, implementation and bitstream generation')
    parser.add_argument('--generate_prj_with_external_tcl', action='store_true', help='Generate Vivado project using external TCL script')
    parser.add_argument('--write_tcl', action='store_true', help='Export Vivado project to TCL')
    parser.add_argument('--file_remove', action='store_true', help='Remove a file from the Vivado project')
    parser.add_argument('--file_add', action='store_true', help='Add a file to the Vivado project')
    parser.add_argument('--file_path', type=str, help='File path (required for file_remove and file_add)')
    parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation prompts')
    
    # Network tool arguments
    parser.add_argument('--cmd', type=str, choices=['send_raw', 'send_arp', 'send_icmp', 'send_udp'], 
                       help='Network command: send_raw, send_arp, send_icmp, send_udp')
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
    parser.add_argument('--timestamps', action='store_true', help='List all timestamps')
    parser.add_argument('--find_signal_names', nargs='?', const='*', help='List signal names (optionally filter with wildcard pattern)')
    parser.add_argument('--signal', type=str, help='Signal name (supports wildcards)')
    parser.add_argument('--time', nargs='+', help='Filter signal results by timestamp(s)')
    parser.add_argument('--edge', nargs='?', const=True, type=int, help='Show signal edges after --time timestamp')
    parser.add_argument('--radix', choices=['hex', 'int', 'bin'], help='Output format for calc_value')
    parser.add_argument('--count', type=int, help='Show count number of values starting from --time timestamp')
    
    # tshark wrapper arguments
    parser.add_argument('--pcap', type=str, help='PCAP file to analyze')
    parser.add_argument('--format', type=str, choices=['to_plain_text'], default='to_plain_text',
                       help='Output format (default: to_plain_text)')
    parser.add_argument('--frame', type=int, help='Display only this frame number')
    parser.add_argument('--frame_start', type=int, help='Start frame number for range (requires --frame_end)')
    parser.add_argument('--frame_end', type=int, help='End frame number for range (requires --frame_start)')
    parser.add_argument('--frame_list', type=str, help='Comma-separated list of frame numbers to display')
    parser.add_argument('--skip', type=int, help='Skip this many packets before displaying')
    parser.add_argument('--tsharkArgsAppend', type=str, help='Additional raw tshark arguments to append')
    
    # Projects tool arguments
    parser.add_argument('--list', action='store_true', help='List all available projects recursively from current directory')
    
    args = parser.parse_args()
    
    # Create invoke Context manually
    c = Context()
    
    # Handle help at top level
    if args.help:
        if args.tool:
            # Show tool-specific help
            if args.tool == 'vivado':
                help_vivado()
            elif args.tool == 'Verilator':
                help_verilator()
            elif args.tool == 'network':
                help_network()
            elif args.tool == 'vcd_analyzer':
                help_vcd_analyzer()
            elif args.tool == 'tsharkWrapper':
                help_tshark_wrapper()
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
        # Check if required arguments are missing - show help
        if not args.SimTargetName and not args.help:
            help_verilator()
            sys.exit(0)
        Verilator(c, args.project, args.step, args.clean, args.SimTargetName, args.flags, args.extra_env)
    elif args.tool == 'vivado':
        # Check if deprecated --step is used with vivado
        if args.step:
            print("[!x!] Error: --step is deprecated for vivado tool")
            print("[i] Use direct flags instead:")
            print("    --syn <RUN_NAME>     Run synthesis")
            print("    --impl <RUN_NAME>    Run implementation")
            print("    --bit <RUN_NAME>     Generate bitstream")
            print("    --all <RUN_NAME>     Run all steps")
            print("    --lint               Run lint")
            print("    --list_runs          List all runs")
            print()
            help_vivado()
            sys.exit(1)
        
        # Collect steps from direct flags and extract run_name
        steps_from_flags = []
        run_name = None
        
        if args.list_runs:
            steps_from_flags.append('list_runs')
        if args.reset_run:
            steps_from_flags.append('reset_run')
            run_name = args.reset_run
        if args.syn:
            steps_from_flags.append('syn')
            run_name = args.syn
        if args.impl:
            steps_from_flags.append('impl')
            run_name = args.impl
        if args.bit:
            steps_from_flags.append('bit')
            run_name = args.bit
        if args.lint:
            steps_from_flags.append('lint')
        if args.all:
            steps_from_flags.append('all')
            run_name = args.all
        if args.generate_prj_with_external_tcl:
            steps_from_flags.append('generate_prj_with_external_tcl')
        if args.write_tcl:
            steps_from_flags.append('write_tcl')
        if args.file_remove:
            steps_from_flags.append('file_remove')
        if args.file_add:
            steps_from_flags.append('file_add')
        
        final_steps = steps_from_flags
        
        # Check if no steps are provided - show help
        if not final_steps:
            help_vivado()
            sys.exit(0)
        
        # Validate that run_name is provided when needed
        requires_run_name = any(step in ['reset_run', 'syn', 'impl', 'bit', 'all'] for step in final_steps)
        if requires_run_name and not run_name:
            print("[!x!] Run name is required for reset_run, syn, impl, bit, or all commands")
            print("[i] Usage examples:")
            print("    hdlforge --tool vivado --reset_run <synth_run_name>")
            print("    hdlforge --tool vivado --syn <synth_run_name>")
            print("    hdlforge --tool vivado --impl <synth_run_name>")
            print("    hdlforge --tool vivado --bit <synth_run_name>")
            print("    hdlforge --tool vivado --all <synth_run_name>")
            exit(1)
        
        # Validate that file_path is provided when needed
        requires_file_path = any(step in ['file_remove', 'file_add'] for step in final_steps)
        if requires_file_path and not args.file_path:
            print("[!x!] File path is required for file_remove and file_add commands")
            print("[i] Usage examples:")
            print("    hdlforge --tool vivado --file_remove --file_path <file_path>")
            print("    hdlforge --tool vivado --file_add --file_path <file_path>")
            exit(1)
        
        vivado(c, args.project, args.verbose, final_steps, args.clean, args.force, run_name, args.file_path)
    elif args.tool == 'network':
        # Network tool selected
        if not args.cmd:
            help_network()
            sys.exit(0)
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
        }
        network(c, args.cmd, **kwargs)
    elif args.tool == 'vcd_analyzer':
        # VCD analyzer tool selected
        kwargs = {
            'vcd': args.vcdfilename,
            'timestamps': args.timestamps,
            'find_signal_names': args.find_signal_names,
            'signal': args.signal,
            'time': args.time,
            'edge': args.edge,
            'verbose': args.verbose,
            'radix': args.radix,
            'count': args.count,
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
                       verbose=args.verbose)
    elif args.tool == 'projects':
        # Projects tool requires --list option
        if not getattr(args, 'list', False):
            help_projects()
            sys.exit(0)
        projects(c, getattr(args, 'set_project', None), list_projects=True)


            'edge': args.edge,
            'verbose': args.verbose,
            'radix': args.radix,
            'count': args.count,
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
                       verbose=args.verbose)
    elif args.tool == 'projects':
        # Projects tool requires --list option
        if not getattr(args, 'list', False):
            help_projects()
            sys.exit(0)
        projects(c, getattr(args, 'set_project', None), list_projects=True)

