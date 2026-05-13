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
from hw_server_tasks import hw_server, help_hw_server

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
        ("network", "Network Utilities", [
            "Send raw packets (ARP, ICMP, UDP)",
            "Use --tool network --cmd <command>"
        ]),
        ("vcd_analyzer", "VCD Analyzer", [
            "Analyze waveform files",
            "Use --tool vcd_analyzer"
        ]),
        ("tsharkWrapper", "Tshark Wrapper", [
            "Wrapper for tshark commands",
            "Use --tool tsharkWrapper"
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
    print("  Build Steps (require RUN_NAME or RUN_NAME[,RUN_NAME2,...]):")
    print("    --syn <RUN_NAME[,RUN_NAME2,...]>    Run synthesis")
    print("    --impl <RUN_NAME[,RUN_NAME2,...]>   Run implementation")
    print("    --bit <RUN_NAME[,RUN_NAME2,...]>    Generate bitstream")
    print("    --all <RUN_NAME[,RUN_NAME2,...]>    Run synthesis, implementation and bitstream generation")
    print("    --reset_run <RUN_NAME>              Reset a Vivado synth run and all its child impl runs")
    print()
    print("  File Management (require --file_path):")
    print("    --file_add --file_path <PATH>        Add a file to the Vivado project")
    print("    --file_remove --file_path <PATH>     Remove a file from the Vivado project")
    print()
    print("  Static Project Tcl Edits (require JSON text, JSON file, or project JSON reference):")
    print("    --add_file_to_project_tcl            Add file sections to exported project Tcl")
    print("    --remove_file_from_project_tcl        Remove file sections from exported project Tcl")
    print("    --add_run_to_project_tcl             Add synth/implementation run sections")
    print("    --remove_run_from_project_tcl         Remove synth/implementation run sections")
    print("    --project_tcl_json <JSON>             Inline edit JSON")
    print("    --project_tcl_json_file <PATH>        Edit JSON file")
    print()
    print("  Other:")
    print("    --lint                               Run lint")
    print("    --clean                              Clean the Vivado project directory under the build directory")
    print("    --clean_logs                         Clean Vivado log files from current directory")
    print("                                         (vivado.log, vivado.jou, vivado_*.backup.*)")
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
    print("EXAMPLES:")
    print("  # Send ARP request")
    print("  sudo hdlforge --tool network --cmd send_arp --interface eth0 --src_ip 192.168.1.100")
    print()
    print("  # Send UDP packet")
    print("  sudo hdlforge --tool network --cmd send_udp --interface eth0 --src_ip 192.168.1.1 \\")
    print("       --dst_ip 192.168.1.100 --dst_port 5678 --data 'deadbeef'")
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
    print("    --get_modules_list                     List all modules in the design")
    print("    --get_values_pins <PATH>               Module path to list value changes for pins only (excludes sub-modules)")
    print("    --get_values_all <PATH>                Module path to list value changes for all signals (excludes sub-modules)")
    print("    --human                                Human-readable output format with padding")
    print()
    print("EXAMPLES:")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --get_modules_list")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --get_values_pins 'top.module_inst'")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --get_values_all 'top.module_inst'")
    print("  hdlforge --tool vcd_analyzer --vcdfilename waveform.vcd --get_values_pins 'top.module_inst' --human")
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
    # Get original CWD from environment (set by hdlforge bash script) or fallback to current dir
    ORIGINAL_CWD = os.environ.get('HDLFORGE_ORIG_DIR', os.getcwd())
    
    parser = argparse.ArgumentParser(
        description='HDLForge - Hardware Development Tool',
        add_help=False  # We'll handle help manually
    )
    parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    parser.add_argument('--project', required=False, help='Project file path')
    parser.add_argument('--tool', required=False, choices=['vivado', 'Verilator', 'network', 'vcd_analyzer', 'tsharkWrapper', 'hw_server', 'projects'], 
                       help='Tool to execute: vivado, Verilator, network, vcd_analyzer, tsharkWrapper, hw_server, or projects (required)')
    
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
    parser.add_argument('--syn', type=str, metavar='RUN_NAME[,RUN_NAME2,...]', help='Run synthesis')
    parser.add_argument('--impl', type=str, metavar='RUN_NAME[,RUN_NAME2,...]', help='Run implementation')
    parser.add_argument('--bit', type=str, metavar='RUN_NAME[,RUN_NAME2,...]', help='Generate bitstream')
    parser.add_argument('--lint', action='store_true', help='Run lint')
    parser.add_argument('--all', type=str, metavar='RUN_NAME[,RUN_NAME2,...]', help='Run synthesis, implementation and bitstream generation')
    parser.add_argument('--generate_prj_with_external_tcl', action='store_true', help='Generate Vivado project using external TCL script')
    parser.add_argument('--write_tcl', action='store_true', help='Export Vivado project to TCL')
    parser.add_argument('--file_remove', action='store_true', help='Remove a file from the Vivado project')
    parser.add_argument('--file_add', action='store_true', help='Add a file to the Vivado project')
    parser.add_argument('--file_path', type=str, help='File path (required for file_remove and file_add)')
    parser.add_argument('--add_file_to_project_tcl', action='store_true', help='Add file sections to the exported Vivado project Tcl')
    parser.add_argument('--remove_file_from_project_tcl', '--remove_file_fom_project_tcl', dest='remove_file_from_project_tcl', action='store_true', help='Remove file sections from the exported Vivado project Tcl')
    parser.add_argument('--add_run_to_project_tcl', '--add_rrun_to_project_tcl', '--add_run_fom_project_tcl', '--add_rrun_fom_project_tcl', dest='add_run_to_project_tcl', action='store_true', help='Add synth/implementation run sections to the exported Vivado project Tcl')
    parser.add_argument('--remove_run_from_project_tcl', '--remove_rrun_fom_project_tcl', '--remove_run_fom_project_tcl', dest='remove_run_from_project_tcl', action='store_true', help='Remove synth/implementation run sections from the exported Vivado project Tcl')
    parser.add_argument('--project_tcl_json', type=str, help='Inline JSON dictionary for project Tcl edits')
    parser.add_argument('--project_tcl_json_file', type=str, help='JSON file for project Tcl edits')
    parser.add_argument('--clean_logs', action='store_true', help='Clean Vivado log files from current directory')
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
    args, unknown = parser.parse_known_args()
    
    # Check for common mistakes with vcd_analyzer
    if args.tool == 'vcd_analyzer' and args.get_modules_list and unknown:
        print("[!x!] Error: --get_modules_list does not accept arguments", file=sys.stderr)
        print(f"[i] Unrecognized arguments: {' '.join(unknown)}", file=sys.stderr)
        print("[i] Note: --get_modules_list is a flag (no arguments). If you want to filter modules:", file=sys.stderr)
        print("[i]   Use grep: hdlforge --tool vcd_analyzer --vcdfilename <file> --get_modules_list | grep 'pattern'", file=sys.stderr)
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
                help_verilator()
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
            print("    --syn <RUN_NAME[,RUN_NAME2,...]>     Run synthesis")
            print("    --impl <RUN_NAME[,RUN_NAME2,...]>    Run implementation")
            print("    --bit <RUN_NAME[,RUN_NAME2,...]>     Generate bitstream")
            print("    --all <RUN_NAME[,RUN_NAME2,...]>     Run all steps")
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
        if args.add_file_to_project_tcl:
            steps_from_flags.append('project_tcl_file_add')
        if args.remove_file_from_project_tcl:
            steps_from_flags.append('project_tcl_file_remove')
        if args.add_run_to_project_tcl:
            steps_from_flags.append('project_tcl_run_add')
        if args.remove_run_from_project_tcl:
            steps_from_flags.append('project_tcl_run_remove')
        if args.clean_logs:
            steps_from_flags.append('clean_logs')
        
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
            print("    hdlforge --tool vivado --syn <synth_run_name[,synth_run_name2,...]>")
            print("    hdlforge --tool vivado --impl <synth_run_name[,synth_run_name2,...]>")
            print("    hdlforge --tool vivado --bit <synth_run_name[,synth_run_name2,...]>")
            print("    hdlforge --tool vivado --all <synth_run_name[,synth_run_name2,...]>")
            exit(1)
        
        # Validate that file_path is provided when needed
        requires_file_path = any(step in ['file_remove', 'file_add'] for step in final_steps)
        if requires_file_path and not args.file_path:
            print("[!x!] File path is required for file_remove and file_add commands")
            print("[i] Usage examples:")
            print("    hdlforge --tool vivado --file_remove --file_path <file_path>")
            print("    hdlforge --tool vivado --file_add --file_path <file_path>")
            exit(1)
        
        vivado(
            c,
            args.project,
            args.verbose,
            final_steps,
            args.clean,
            args.force,
            run_name,
            args.file_path,
            args.project_tcl_json,
            args.project_tcl_json_file,
        )
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
