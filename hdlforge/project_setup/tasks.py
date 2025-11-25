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
from toolbox_tasks import toolbox

# Import project loader (single source of truth for project data)
from project_file import ProjectFile


def projects(c, set_project=None):
    """List available projects in the current directory."""
    # Use ProjectFile to detect project files
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
        ("toolbox", "Network Utilities", [
            "Send raw network packets",
            "Support for ARP, ICMP, UDP protocols",
            "Direct interface access for testing"
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
    print("  1. Set up your project: hdlforge projects")
    print("  2. Generate project with external TCL: hdlforge vivado --generate_prj_with_external_tcl")
    print("  3. Run synthesis: hdlforge vivado --syn <synth_run_name>")
    print("  4. Run simulation: hdlforge Verilator --step build --step sim --SimTargetName <target>")
    print()
    print("GETTING HELP:")
    print("  hdlforge                          # Show this help")
    print("  hdlforge --help                   # Show this help")
    print("  hdlforge <tool>                   # Show help for specific tool")
    print("  hdlforge <tool> --help             # Show detailed help for specific tool")
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
    print("  hdlforge vivado <--arg1> <value1> <--arg2> <value2> ...")
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
    print("    --step <STEP>                        DEPRECATED: Use direct step flags instead")
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
    print("  hdlforge Verilator <--arg1> <value1> <--arg2> <value2> ...")
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


def help_toolbox():
    """
    Show detailed help for Toolbox tool
    """
    print("=" * 80)
    print("HDLFORGE TOOLBOX - Network Utilities")
    print("=" * 80)
    print()
    print("DESCRIPTION:")
    print("  Send raw network packets for testing and debugging. Supports ARP, ICMP, and UDP protocols.")
    print()
    print("USAGE:")
    print("  hdlforge toolbox <tool> [--arg1] [<value1>] [--arg2] [<value2>] ...")
    print()
    print("AVAILABLE TOOLS:")
    print()
    print("  send_raw:")
    print("    Send raw bytes to network interface")
    print("    --interface <IFACE>                  Network interface (required)")
    print("    --data <HEX_STRING>                  Raw data as hex string (required)")
    print("    --verbose                            Enable verbose output")
    print()
    print("  send_arp:")
    print("    Send ARP packet")
    print("    --interface <IFACE>                  Network interface (required)")
    print("    --arp_op <1|2>                       ARP operation: 1=request, 2=reply (default: 1)")
    print("    --eth_dst_mac <MAC>                  Ethernet destination MAC (default: FF:FF:FF:FF:FF:FF for requests)")
    print("    --eth_src_mac <MAC>                  Ethernet source MAC (default: same as ARP src_mac)")
    print("    --src_mac <MAC>                      ARP source MAC address (default: 00:00:00:00:00:00)")
    print("    --src_ip <IP>                        Source IP address (default: 192.168.1.1)")
    print("    --dst_mac <MAC>                      ARP destination MAC address (default: 00:00:00:00:00:00)")
    print("    --dst_ip <IP>                        Destination IP address (default: 192.168.1.2)")
    print("    --verbose                            Enable verbose output")
    print()
    print("  send_icmp:")
    print("    Send ICMP packet (ping)")
    print("    --interface <IFACE>                  Network interface (required)")
    print("    --src_mac <MAC>                      Source MAC address (default: 00:00:00:00:00:00)")
    print("    --dst_mac <MAC>                      Destination MAC address (default: ff:ff:ff:ff:ff:ff)")
    print("    --src_ip <IP>                        Source IP address (default: 192.168.1.1)")
    print("    --dst_ip <IP>                        Destination IP address (default: 192.168.1.2)")
    print("    --icmp_type <TYPE>                   ICMP type: 8=echo request, 0=echo reply (default: 8)")
    print("    --icmp_code <CODE>                   ICMP code (default: 0)")
    print("    --identifier <ID>                    ICMP identifier (default: 0)")
    print("    --sequence <SEQ>                     ICMP sequence number (default: 0)")
    print("    --data <HEX_STRING>                   ICMP data payload as hex string")
    print("    --verbose                            Enable verbose output")
    print()
    print("  send_udp:")
    print("    Send UDP packet")
    print("    --interface <IFACE>                  Network interface (required)")
    print("    --src_mac <MAC>                      Source MAC address (default: 00:00:00:00:00:00)")
    print("    --dst_mac <MAC>                      Destination MAC address (default: ff:ff:ff:ff:ff:ff)")
    print("    --src_ip <IP>                        Source IP address (default: 192.168.1.1)")
    print("    --dst_ip <IP>                        Destination IP address (default: 192.168.1.2)")
    print("    --src_port <PORT>                    Source UDP port (default: 12345)")
    print("    --dst_port <PORT>                    Destination UDP port (default: 53)")
    print("    --data <HEX_STRING>                   UDP payload as hex string")
    print("    --verbose                            Enable verbose output")
    print()
    print("EXAMPLES:")
    print("  hdlforge toolbox send_raw --interface enp175s0f0np0 --data 'deadbeef'")
    print("  hdlforge toolbox send_arp --interface enp175s0f0np0 --src_ip 192.168.1.10 --dst_ip 192.168.1.1")
    print("  hdlforge toolbox send_icmp --interface enp175s0f0np0 --src_ip 192.168.1.10 --dst_ip 192.168.1.1")
    print("  hdlforge toolbox send_udp --interface enp175s0f0np0 --src_ip 192.168.1.10 --dst_ip 192.168.1.1 --dst_port 53")
    print()
    print("NOTES:")
    print("  • Requires root privileges (use sudo)")
    print("  • Use tcpdump to capture packets: sudo tcpdump -i <interface> -w capture.pcap")
    print("  • View pcap file: tcpdump -r capture.pcap -X")
    print()
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='HDLForge - Hardware Development Tool',
        add_help=False  # We'll handle help manually
    )
    parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Verilator subcommand
    verilator_parser = subparsers.add_parser('Verilator', add_help=False)
    verilator_parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    verilator_parser.add_argument('--project', required=False)
    verilator_parser.add_argument('--step', action='append')
    verilator_parser.add_argument('--SimTargetName')
    verilator_parser.add_argument('--clean', action='store_true')
    verilator_parser.add_argument('--flags')
    verilator_parser.add_argument('--extra-env')
    
    # Vivado subcommand
    vivado_parser = subparsers.add_parser('vivado', add_help=False)
    vivado_parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    vivado_parser.add_argument('--project', required=False)
    vivado_parser.add_argument('--step', action='append', help='DEPRECATED: Use direct step flags instead (e.g., --generate_prj_with_external_tcl, --bit)')
    # Add direct step flags
    vivado_parser.add_argument('--list_runs', action='store_true', help='List all Vivado runs')
    vivado_parser.add_argument('--reset_run', type=str, metavar='RUN_NAME', help='Reset a Vivado synth run and all its child impl runs')
    vivado_parser.add_argument('--syn', type=str, metavar='RUN_NAME', help='Run synthesis')
    vivado_parser.add_argument('--impl', type=str, metavar='RUN_NAME', help='Run implementation')
    vivado_parser.add_argument('--bit', type=str, metavar='RUN_NAME', help='Generate bitstream')
    vivado_parser.add_argument('--lint', action='store_true', help='Run lint')
    vivado_parser.add_argument('--all', type=str, metavar='RUN_NAME', help='Run synthesis, implementation and bitstream generation')
    vivado_parser.add_argument('--generate_prj_with_external_tcl', action='store_true', help='Generate Vivado project using external TCL script')
    vivado_parser.add_argument('--write_tcl', action='store_true', help='Export Vivado project to TCL')
    vivado_parser.add_argument('--file_remove', action='store_true', help='Remove a file from the Vivado project')
    vivado_parser.add_argument('--file_add', action='store_true', help='Add a file to the Vivado project')
    vivado_parser.add_argument('--file_path', type=str, help='File path (required for file_remove and file_add)')
    vivado_parser.add_argument('--verbose', action='store_true')
    vivado_parser.add_argument('--clean', action='store_true')
    vivado_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation prompts')
    
    # Toolbox subcommand
    toolbox_parser = subparsers.add_parser('toolbox', add_help=False)
    toolbox_parser.add_argument('-h', '--help', action='store_true', help='Show help message')
    toolbox_parser.add_argument('tool', nargs='?', help='Tool to execute (send_raw, send_arp, send_icmp, send_udp)')
    toolbox_parser.add_argument('--interface', type=str, help='Network interface name')
    toolbox_parser.add_argument('--data', type=str, help='Raw data as hex string')
    toolbox_parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    # ARP arguments
    toolbox_parser.add_argument('--arp_op', type=int, help='ARP operation: 1=request, 2=reply')
    toolbox_parser.add_argument('--eth_dst_mac', type=str, help='Ethernet destination MAC address (default: FF:FF:FF:FF:FF:FF for requests)')
    toolbox_parser.add_argument('--eth_src_mac', type=str, help='Ethernet source MAC address')
    toolbox_parser.add_argument('--src_mac', type=str, help='ARP source MAC address')
    toolbox_parser.add_argument('--dst_mac', type=str, help='ARP destination MAC address')
    toolbox_parser.add_argument('--src_ip', type=str, help='Source IP address')
    toolbox_parser.add_argument('--dst_ip', type=str, help='Destination IP address')
    # ICMP arguments
    toolbox_parser.add_argument('--icmp_type', type=int, help='ICMP type: 8=echo request, 0=echo reply')
    toolbox_parser.add_argument('--icmp_code', type=int, help='ICMP code')
    toolbox_parser.add_argument('--identifier', type=int, help='ICMP identifier')
    toolbox_parser.add_argument('--sequence', type=int, help='ICMP sequence number')
    # UDP arguments
    toolbox_parser.add_argument('--src_port', type=int, help='Source UDP port')
    toolbox_parser.add_argument('--dst_port', type=int, help='Destination UDP port')
    
    # Other subcommands
    subparsers.add_parser('projects')
    subparsers.add_parser('help')
    
    args = parser.parse_args()
    
    # Create invoke Context manually
    c = Context()
    
    # Handle help at top level
    if args.help and not args.command:
        help(c)
        sys.exit(0)
    
    # Handle no command provided - show main help
    if not args.command:
        help(c)
        sys.exit(0)
    
    # Handle help for specific tools
    if args.command == 'Verilator':
        if args.help:
            help_verilator()
            sys.exit(0)
        # Check if required arguments are missing - show help
        if not args.SimTargetName and not args.help:
            help_verilator()
            sys.exit(0)
        Verilator(c, args.project, args.step, args.clean, args.SimTargetName, args.flags, args.extra_env)
    elif args.command == 'vivado':
        if args.help:
            help_vivado()
            sys.exit(0)
        
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
        
        # Combine with --step for backward compatibility (--step takes precedence if both are used)
        final_steps = args.step if args.step else steps_from_flags
        
        # Check if no steps are provided - show help
        if not final_steps:
            help_vivado()
            sys.exit(0)
        
        # Warn if both are used
        if args.step and steps_from_flags:
            print("[!] Warning: Both --step and direct step flags are specified. Using --step values.")
            # If using --step, we still need run_name from positional args for backward compatibility
            # But for now, let's require it to be passed via --step syntax or flag values
        
        # Validate that run_name is provided when needed
        requires_run_name = any(step in ['reset_run', 'syn', 'impl', 'bit', 'all'] for step in final_steps)
        if requires_run_name and not run_name:
            print("[!x!] Run name is required for reset_run, syn, impl, bit, or all commands")
            print("[i] Usage examples:")
            print("    hdlforge vivado --reset_run <synth_run_name>")
            print("    hdlforge vivado --syn <synth_run_name>")
            print("    hdlforge vivado --impl <synth_run_name>")
            print("    hdlforge vivado --bit <synth_run_name>")
            print("    hdlforge vivado --all <synth_run_name>")
            exit(1)
        
        # Validate that file_path is provided when needed
        requires_file_path = any(step in ['file_remove', 'file_add'] for step in final_steps)
        if requires_file_path and not args.file_path:
            print("[!x!] File path is required for file_remove and file_add commands")
            print("[i] Usage examples:")
            print("    hdlforge vivado --file_remove --file_path <file_path>")
            print("    hdlforge vivado --file_add --file_path <file_path>")
            exit(1)
        
        vivado(c, args.project, args.verbose, final_steps, args.clean, args.force, run_name, args.file_path)
    elif args.command == 'toolbox':
        if args.help:
            help_toolbox()
            sys.exit(0)
        # Check if tool is provided - if not, show help
        if not args.tool:
            help_toolbox()
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
        toolbox(c, args.tool, **kwargs)
    elif args.command == 'projects':
        projects(c, getattr(args, 'set_project', None))
    elif args.command == 'help':
        help(c)


