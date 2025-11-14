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
    print("  4. Run simulation: hdlforge Verilator --step build --step sim")
    print()
    print("GETTING HELP:")
    print("  hdlforge help                    # Show this help")
    print("  hdlforge --help <task_name>       # Get detailed help for specific task")
    print("  hdlforge --list                   # List all available tasks")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HDLForge - Hardware Development Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Verilator subcommand
    verilator_parser = subparsers.add_parser('Verilator')
    verilator_parser.add_argument('--project', required=False)
    verilator_parser.add_argument('--step', action='append')
    verilator_parser.add_argument('--SimTargetName')
    verilator_parser.add_argument('--clean', action='store_true')
    verilator_parser.add_argument('--flags')
    verilator_parser.add_argument('--extra-env')
    
    # Vivado subcommand
    vivado_parser = subparsers.add_parser('vivado')
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
    
    # Other subcommands
    subparsers.add_parser('projects')
    subparsers.add_parser('help')
    
    args = parser.parse_args()
    
    # Create invoke Context manually
    c = Context()
    
    if args.command == 'Verilator':
        Verilator(c, args.project, args.step, args.clean, args.SimTargetName, args.flags, args.extra_env)
    elif args.command == 'vivado':
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
    elif args.command == 'projects':
        projects(c, getattr(args, 'set_project', None))
    elif args.command == 'help':
        help(c)
    else:
        parser.print_help()


