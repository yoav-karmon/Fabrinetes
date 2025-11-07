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
from enum import Enum

# Import project loader (single source of truth for project data)
from project_loader import ProjectLoader


class VivadoStep(str, Enum):
    """Enum for Vivado step names"""
    NEW = "new"
    LIST_RUNS = "list_runs"
    RESET_RUN = "reset_run"
    SYN = "syn"
    IMPL = "impl"
    BIT = "bit"
    LINT = "lint"
    ALL = "all"
    GEN = "gen"
    WRITE_TCL = "write_tcl"
    COMMIT = "commit"
    CMD_GEN = "cmd-gen"



def generate_vivado_tcl(
    output_path: Path,
    project_name: str,
    part: str,
    top_module: str,
    sources_dict_list) -> None:    

   

    print(f"[i] Generating Vivado TCL script: {output_path}")
    lines = []

    # Header
    lines.append(f"# This script was auto-generated to configure Vivado project settings.\n")

    # Basic project vars
    lines.append("#******************************************************")
    lines.append(f"set project_name {project_name}")
    lines.append(f"set PART  {part}")
    lines.append(f"set top_module {top_module}")
    lines.append("#******************************************************\n")

    # REPO_TOP export
    lines.append("#******************************************************")
    lines.append("set REPO_TOP $::env(REPO_TOP)")
    lines.append("set ::REPO_TOP $REPO_TOP")
    lines.append("#******************************************************\n")

    # Create project & generics
    lines.append("#******************************************************")
    lines.append("create_project -force $project_name -part $PART")
    lines.append("set_property top $top_module [current_fileset]")
   

    lines.append("#******************************************************\n")

# [+] Add sources from multiple list files using add_files_from_list.tcl
    lines.append("#******************************************************")
    constrset_list=[]
    sources_list=[]
    tcl_files_list=[]
    for filedict in sources_dict_list:
        if("vivado_fileset" in filedict):
            if(isinstance(filedict["vivado_fileset"], str)):
                vivado_fileset = [filedict["vivado_fileset"]]
            else:
                vivado_fileset = filedict["vivado_fileset"]
        else:
            vivado_fileset = None
        if(vivado_fileset != None):
            for fs in vivado_fileset:
       
                if fs not in constrset_list:
                    lines.append(f"create_fileset -constrset {fs} ")
                    constrset_list.append(fs)
                lines.append(f"add_files -fileset {fs} [file normalize [subst {filedict["file"]}]]")
        else:
            sources_list.append(filedict["file"])

    addcmd="add_files "
    for file in sources_list:
        addcmd += f"{file} "
        if(file.endswith(".tcl") ):
            tcl_files_list.append(file)
    lines.append(f"{addcmd}")



    lines.append("set_property file_type {VHDL 2008}  [get_files  *.vhd]")
    lines.append("set_property file_type {SystemVerilog}  [get_files  *.sv]")
    for file in tcl_files_list:
        lines.append(f"source  {file}")
    lines.append("")
    lines.append("#******************************************************\n")

   

    # Write the TCL script
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


def add_python_paths_from_list(path_list, working_path=None):
    print("\n[i] Updating PYTHONPATH with the following paths:", flush=True)
    
    # Always add working_path first if provided
    if working_path:
        working_path_abs = os.path.abspath(working_path)
        if working_path_abs not in sys.path:
            sys.path.insert(0, working_path_abs)
            print(f"[OK] Added working_path to PYTHONPATH: {working_path_abs}")
        else:
            print(f"[i] working_path already in PYTHONPATH: {working_path_abs}")
    
    # Process additional paths from the list
    for path in path_list:
        # Resolve relative paths relative to working_path if provided
        if working_path and not os.path.isabs(path):
            resolved = str(Path(working_path) / path)
        else:
            # Resolve env vars
            resolved = os.path.expandvars(path)
        
        print(f"[~] Resolving path: {resolved}")
        # Absolute path
        abs_path = os.path.abspath(resolved)

        # Add if not already in sys.path (check for duplication)
        if abs_path not in sys.path:
            sys.path.insert(0, abs_path)
            print(f"[OK] Added to PYTHONPATH: {abs_path}")
        else:
            print(f"[i] Already in PYTHONPATH: {abs_path}")
    print("", flush=True)
    

def print_task_args(local_vars: dict, REPO_TOP: str, allowed_values: dict[str, List[str]] = {}):
    # Get the calling function name automatically
    caller_name = inspect.stack()[1].function  

    # Remove Invoke context (c), internal variables (_path, _full), and empty project argument
    # Also exclude internal metadata variables like ALLOWED_STEPS, TOOL_NAME, SCRIPT_DIR
    excluded_keys = {"c", "project", "ALLOWED_STEPS", "TOOL_NAME", "SCRIPT_DIR"}
    args = {k: v for k, v in local_vars.items() if k not in excluded_keys and not k.endswith("_path") and not k.endswith("_full")}
    max_key_len = max(len(k) for k in args.keys()) if args else 0
    border = "=" * (max_key_len + 30)

    print(border)
    print(f"[i] Task: {caller_name}")
    print(border)
    print("file executed: ", Path(__file__).resolve())
    table=[["key","value","allowed"]]
    
    # Sort keys alphabetically
    sorted_keys = sorted(args.keys())
    
    # Maximum width for value column to keep table readable
    MAX_VALUE_WIDTH = 80
    
    def truncate_value(val: str, max_width: int = MAX_VALUE_WIDTH) -> str:
        """Truncate long values with ellipsis"""
        if len(val) <= max_width:
            return val
        return val[:max_width-3] + "..."
    
    for key in sorted_keys:
        try:
            value = args[key]
            if( key in allowed_values):
                # Format value for display, truncate if needed
                display_value = str(value) if value is not None else ""
                if isinstance(value, list):
                    display_value = f"[{', '.join(map(str, value))}]"
                display_value = truncate_value(display_value)
                table.append([key.ljust(max_key_len), display_value, f"(allowed: {', '.join(allowed_values[key])})"])
            elif(not isinstance(value, dict) and not isinstance(value, list)):
                # Convert Path objects to strings
                if isinstance(value, Path):
                    value = str(value)
                # Skip if value can't be converted to string
                try:
                    str_value = str(value)
                    if REPO_TOP+"/" in str_value:
                        str_value = str_value.replace(REPO_TOP+"/", "$REPO_TOP/")
                    str_value = truncate_value(str_value)
                    table.append([key.ljust(max_key_len), str_value, ""])
                except:
                    # Skip variables that can't be converted to string
                    pass
            elif(isinstance(value, list)):
                # Format list nicely
                list_str = f"[{', '.join(map(str, value))}]"
                list_str = truncate_value(list_str)
                table.append([key.ljust(max_key_len), list_str, ""])
            elif(isinstance(value,dict)):
                # Format dict nicely, especially for dicts containing lists
                formatted_parts = []
                for k, v in value.items():
                    if isinstance(v, list):
                        formatted_parts.append(f"{k}: [{', '.join(map(str, v))}]")
                    else:
                        formatted_parts.append(f"{k}: {v}")
                print_str = ", ".join(formatted_parts)
                print_str = truncate_value(print_str)
                table.append([key.ljust(max_key_len), print_str, ""])
        except Exception as e:
            # Skip problematic variables silently
            continue
    print(tabulate(table, headers="firstrow", tablefmt="fancy_grid",colalign=("left", "left", "center")))
        
    print(border)
    print("")
    
def print_boxed(message: str, border_char: str = "=", padding: int = 2):
    lines = message.split("\n")
    max_len = max(len(line) for line in lines)
    border = border_char * (max_len + padding * 2 + 2)

    print(border)
    for line in lines:
        print(f"{border_char}{' ' * padding}{line.ljust(max_len)}{' ' * padding}{border_char}")
    print(border)


def capture_environment_variables(c: invoke.Context):
    """Capture environment variables set by update_repo_path function and validate repository environment"""
    invoked_dir = os.environ.get('ROOT_FOLDER', os.getcwd())
    
    # Run update_repo_path and capture environment variables
    try:
        result = c.run(f"cd {invoked_dir} && bash -i -c 'source ~/.bashrc && update_repo_path && env | grep -E \"^(REPO_TOP|PATH|PYTHONPATH)=\"'", hide=True)
    except Exception as e:
        print("❌ ERROR: Failed to run update_repo_path")
        print("   This usually means you're not in a Git repository")
        print(f"   Current directory: {invoked_dir}")
        print("   Please run: cd <your_git_repo> && hdlforge <command>")
        exit(1)
    
    # Parse the captured environment variables
    captured_vars = {}
    for line in result.stdout.split('\n'):
        if line.startswith('REPO_TOP='):
            repo_top = line.split('=', 1)[1]
            os.environ['REPO_TOP'] = repo_top
            captured_vars['REPO_TOP'] = repo_top
        elif line.startswith('PATH='):
            path = line.split('=', 1)[1]
            os.environ['PATH'] = path
            captured_vars['PATH'] = path
        elif line.startswith('PYTHONPATH='):
            pythonpath = line.split('=', 1)[1]
            os.environ['PYTHONPATH'] = pythonpath
            captured_vars['PYTHONPATH'] = pythonpath
    
    # Validate repository environment
    validate_repository_environment(captured_vars, invoked_dir)
    
    # Print captured environment variables nicely
    print("=" * 60)
    print("ENVIRONMENT VARIABLES SET BY update_repo_path:")
    print("=" * 60)
    for var_name, var_value in captured_vars.items():
        if var_name == 'PATH':
            # Show PATH entries on separate lines for readability
            path_entries = var_value.split(':')
            print(f"{var_name}:")
            for i, entry in enumerate(path_entries):
                print(f"  [{i+1}] {entry}")
        elif var_name == 'PYTHONPATH':
            # Show PYTHONPATH entries on separate lines for readability
            pythonpath_entries = var_value.split(':') if var_value else []
            print(f"{var_name}:")
            if pythonpath_entries:
                for i, entry in enumerate(pythonpath_entries):
                    print(f"  [{i+1}] {entry}")
            else:
                print("  (empty)")
        else:
            print(f"{var_name}: {var_value}")
    print("=" * 60)
    
    return captured_vars

def validate_repository_environment(captured_vars: dict, invoked_dir: str):
    """Validate that we're in a proper repository environment based on update_repo_path results"""
    
    # Check if REPO_TOP was captured
    if 'REPO_TOP' not in captured_vars or not captured_vars['REPO_TOP']:
        print("❌ ERROR: REPO_TOP not set by update_repo_path")
        print("   This usually means you're not in a Git repository")
        print("   Please run: cd <your_git_repo> && hdlforge <command>")
        exit(1)
    
    repo_top = captured_vars['REPO_TOP']
    repo_top_path = Path(repo_top)
    invoked_path = Path(invoked_dir)
    
    # Validate REPO_TOP directory exists
    if not repo_top_path.exists():
        print(f"❌ ERROR: REPO_TOP directory does not exist: {repo_top}")
        print("   Please check your Git repository structure")
        exit(1)
    
    # Validate REPO_TOP is a Git repository
    git_dir = repo_top_path / '.git'
    if not git_dir.exists():
        print(f"❌ ERROR: REPO_TOP is not a Git repository: {repo_top}")
        print("   Missing .git directory")
        exit(1)
    
    # Validate current directory is under REPO_TOP
    try:
        invoked_resolved = invoked_path.resolve()
        repo_top_resolved = repo_top_path.resolve()
        
        # Check if invoked directory is under REPO_TOP
        if not str(invoked_resolved).startswith(str(repo_top_resolved)):
            print(f"❌ ERROR: Current directory is not under REPO_TOP")
            print(f"   Current directory: {invoked_resolved}")
            print(f"   REPO_TOP: {repo_top_resolved}")
            print("   Please run HDLForge commands from within the repository")
            exit(1)
            
    except Exception as e:
        print(f"❌ ERROR: Failed to validate directory structure: {e}")
        exit(1)
    
    # Validate PATH contains expected repository tools
    if 'PATH' in captured_vars:
        path_entries = captured_vars['PATH'].split(':')
        repo_tools_path = str(repo_top_path / 'tools' / 'tool_box')
        
        if repo_tools_path not in path_entries:
            print(f"⚠️  WARNING: Repository tools not found in PATH")
            print(f"   Expected: {repo_tools_path}")
            print("   This may cause issues with HDLForge tools")
    
    print("✅ Repository environment validation passed")
    print(f"   REPO_TOP: {repo_top}")
    print(f"   Current directory: {invoked_dir}")
    print(f"   Git repository: ✓")
    print(f"   Directory structure: ✓")

def vivado(c,project,verbose=False,step:List[str]=[],clean=False,run_flow=None,force=False,run_name=None,cmd=None,arg=None):
    # Capture environment variables set by update_repo_path
    capture_environment_variables(c)
    
    # Handle None or empty step
    if step is None:
        step = []
    elif isinstance(step, str):
        step = [step]

    ALLOWED_STEPS = {"step":[step.value for step in VivadoStep]}
    TOOL_NAME = "vivado"
    # Get script directory from environment or use the directory where this script is located
    SCRIPT_DIR = Path(os.environ.get("HDLFORGE", str(Path(__file__).parent)))
    REPO_TOP = Path(os.environ["REPO_TOP"]) 

    # Load project using ProjectLoader (single source of truth)
    project_loader = ProjectLoader(project)
    project_loader.verify_repo_path()

    ##remove REPO_TOP  from sources list


    print_task_args(locals(),str(REPO_TOP),ALLOWED_STEPS)

    def cleaning(BUILD_DIR,clean):  
        if(clean):
            print(f"[i] Cleaning Vivado build directory: {BUILD_DIR}")
            if BUILD_DIR.exists():
                response = input(f"{BUILD_DIR} will be deleted! (y/n): ")
                if response.lower() != "y":
                    print("Aborted clean operation.")
                    return
                c.run(f"rm -rf {BUILD_DIR}")
                print(f"[+] removed Vivado build directory: {BUILD_DIR}")
            else:
                print(f"[i] nothing to clean in Vivado build directory: {BUILD_DIR}")
            c.run(f"mkdir -p {BUILD_DIR}")
    
    if(clean):
        cleaning(project_loader.vivado_build_dir,True)

    def call_compile_tcl(step,syth_name,impl_list,paramaters,defines ):
        # Filter enabled implementations
        enabled_impls = []
        for impl_item in impl_list:
            if isinstance(impl_item, dict):
                if impl_item.get('enabled', True):  # Default to enabled if not specified
                    enabled_impls.append(impl_item['name'])
            else:
                # Old format - just a string, treat as enabled
                enabled_impls.append(impl_item)
        
        if not enabled_impls:
            print("[!] No enabled implementation runs found. Skipping.")
            return
        
        # Join enabled impl names with space for TCL script
        impl_names_str = " ".join(enabled_impls)
        
        with c.cd(str(project_loader.vivado_build_dir)):
            table=[["Step", step]]
            table.append(["Synth", syth_name])
            table.append(["Impl", impl_names_str])
            table.append(["Parameters", paramaters])
            table.append(["Defines", defines])
            print(tabulate(table, headers="firstrow", tablefmt="grid"))

            cmd= f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {project_loader.vivado_project_xpr_relative} {step} {syth_name} '{impl_names_str}' '{paramaters}' '{defines}'"
            print(f"\n[i] Running Vivado compile TCL script with command: {cmd}\n",flush=True)
            c.run(cmd,pty=True,echo=True)

    # Convert step strings to enum values
    def to_vivado_step(step_str: str) -> VivadoStep:
        """Convert string step name to VivadoStep enum"""
        try:
            return VivadoStep(step_str)
        except ValueError:
            print(f"[!x!] Invalid step name: {step_str}")
            print(f"[i] Allowed steps: {', '.join([step.value for step in VivadoStep])}")
            exit(1)
    
    for s in step:
        step_enum = to_vivado_step(s)
        match (step_enum):
            case VivadoStep.NEW:
                c.run(f"mkdir -p {project_loader.vivado_build_dir}")
                cleaning(project_loader.vivado_build_dir,True)
                print(f"[i] Creating new Vivado project: {project_loader.vivado_project_name}")

                # Check if vivado_project_settings.tcl already exists
                if project_loader.vivado_project_tcl.exists():
                    print(f"[i] Found existing script: {project_loader.vivado_project_tcl}")
                    response = input(f"Regenerate the script or reuse existing? (r)egenerate/(u)se existing [u]: ").strip().lower()
                    if response == 'r' or response == 'regenerate':
                        print(f"[i] Regenerating script: {project_loader.vivado_project_tcl}")
                        generate_vivado_tcl(
                            output_path=project_loader.vivado_project_tcl,
                            project_name=project_loader.vivado_project_name,
                            part=project_loader.vivado_part,
                            top_module=project_loader.vivado_top_module,
                            sources_dict_list=project_loader.get_vivado_sources(verbose))
                    else:
                        print(f"[i] Reusing existing script: {project_loader.vivado_project_tcl}")
                else:
                    # File doesn't exist, generate it
                    generate_vivado_tcl(
                        output_path=project_loader.vivado_project_tcl,
                        project_name=project_loader.vivado_project_name,
                        part=project_loader.vivado_part,
                        top_module=project_loader.vivado_top_module,
                        sources_dict_list=project_loader.get_vivado_sources(verbose))
                
                print(f"[i] Creating Vivado project : {project_loader.vivado_project_tcl}")
                with c.cd(str(project_loader.vivado_build_dir)):
                    c.run(f"vivado -mode batch -source {project_loader.vivado_project_tcl} -notrace")

            case VivadoStep.LIST_RUNS:
                print(f"[i] Listing Vivado runs for project: {project_loader.vivado_project_name}")
                
                # Run list_all_runs command and capture output
                with c.cd(str(project_loader.vivado_build_dir)):
                    result = c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_loader.vivado_project_xpr_relative}",pty=True,echo=True)
                
                # Parse output and create hierarchical structure
                all_runs_dict = {}  # Dictionary to store all runs with their properties
                synth_runs = []
                impl_runs = []
                output_lines = result.stdout.split('\n') if hasattr(result, 'stdout') else []
                
                # Parse all runs and store in dictionary
                for line in output_lines:
                    line_stripped = line.strip()
                    if line_stripped and '\t' in line_stripped:
                        # Parse format: run_name\tSynth=1 Impl=0 Status=... Parent=... Defines=... Parameters=...
                        parts = line_stripped.split('\t')
                        if len(parts) >= 2:
                            run_name = parts[0].strip()
                            # Parse properties: "Synth=1 Impl=0 Status=... Parent=... Defines=... Parameters=..."
                            props_str = parts[1].strip()
                            props = {}
                            # Handle properties that may have spaces in values (like Defines and Parameters)
                            # Split by key=value pattern, but handle values that might contain spaces
                            # Match pattern: Key=Value (where value can contain spaces until next Key=)
                            prop_pattern = r'(\w+)=([^\s]+(?:\s+[^\s=]+)*?)(?=\s+\w+=|$)'
                            for match in re.finditer(prop_pattern, props_str):
                                key = match.group(1)
                                value = match.group(2).strip()
                                props[key] = value
                            
                            run_type = "Unknown"
                            synth_val = props.get('Synth', '').strip()
                            impl_val = props.get('Impl', '').strip()
                            parent = props.get('Parent', '').strip()
                            status = props.get('Status', 'Unknown')
                            defines = props.get('Defines', '').strip()
                            parameters = props.get('Parameters', '').strip()
                            
                            # Handle both numeric (1/0) and boolean (true/false) values
                            if synth_val in ('1', 'true', 'True'):
                                run_type = "Synthesis"
                            elif impl_val in ('1', 'true', 'True'):
                                run_type = "Implementation"
                            
                            # Store in dictionary
                            all_runs_dict[run_name] = {
                                'type': run_type,
                                'status': status,
                                'parent': parent,
                                'synth_val': synth_val,
                                'impl_val': impl_val,
                                'defines': defines,
                                'parameters': parameters
                            }
                
                # Build hierarchical structure from dictionary
                for run_name, run_data in all_runs_dict.items():
                    if run_data['type'] == "Synthesis":
                        synth_runs.append({
                            'name': run_name,
                            'type': run_data['type'],
                            'status': run_data['status'],
                            'defines': run_data['defines'],
                            'parameters': run_data['parameters'],
                            'impl_runs': []
                        })
                    elif run_data['type'] == "Implementation":
                        impl_runs.append({
                            'name': run_name,
                            'type': run_data['type'],
                            'status': run_data['status'],
                            'parent': run_data['parent']
                        })
                
                # Group implementation runs under their synthesis parents
                for impl in impl_runs:
                    parent_name = impl['parent']
                    for synth in synth_runs:
                        if synth['name'] == parent_name:
                            synth['impl_runs'].append(impl)
                            break
                
                # Display single hierarchical table
                if synth_runs or impl_runs:
                    print("\n" + "=" * 80)
                    print("[i] Run Summary:")
                    print("=" * 80)
                    table = [["Run Name", "Type", "Status", "Defines", "Parameters"]]
                    for synth in synth_runs:
                        # Add synthesis run with defines and parameters
                        defines_str = synth['defines'] if synth['defines'] else "(none)"
                        params_str = synth['parameters'] if synth['parameters'] else "(none)"
                        table.append([synth['name'], synth['type'], synth['status'], defines_str, params_str])
                        # Add all implementation runs that have Parent=synth['name']
                        for impl in synth['impl_runs']:
                            table.append([f"  └─ {impl['name']}", impl['type'], impl['status'], "", ""])
                    # Add any orphaned implementation runs (shouldn't happen, but just in case)
                    for impl in impl_runs:
                        if not any(impl['name'] in [i['name'] for i in s['impl_runs']] for s in synth_runs):
                            table.append([impl['name'], impl['type'], impl['status'], "", ""])
                    print(tabulate(table, headers="firstrow", tablefmt="fancy_grid"))
                    print("=" * 80 + "\n")
                else:
                    print("\n[i] No runs found in the output.\n")
                
            case VivadoStep.LINT:
                print(f"[i] Running Vivado lint for project: {project_loader.vivado_project_name}",flush=True)
                if run_flow is None:
                    print("[i] Available run_flow options:")
                    for key, value in project_loader.vivado_runs_flow.items():
                        print(f"--run-flow {key} ~  {key}: {value}")
                    print("[!x!] Please specify a valid run_flow argument using --run-flow <option>")
                    exit(1)
                runs_flow = project_loader.vivado_runs_flow[run_flow]
                paramaters = runs_flow.get("paramaters", [])
                defines = runs_flow.get("defines", [])
                paramaters_str = " ".join(paramaters) if paramaters else ""
                defines_str = " ".join(defines) if defines else ""
                ignore_error_codes = " ".join(project_loader.vivado_lint_ignore_error_codes)
                ignore_warning_codes = " ".join(project_loader.vivado_lint_ignore_warning_codes)
                with c.cd(str(project_loader.vivado_build_dir)):
                    cmd = f"vivado -mode batch -source {SCRIPT_DIR}/lint.tcl -notrace -tclargs {project_loader.vivado_project_xpr_relative} '{paramaters_str}' '{defines_str}' '{ignore_error_codes}' '{ignore_warning_codes}'"
                    print(f"\n[i] Running Vivado lint TCL script with command: {cmd}\n",flush=True)
                    c.run(cmd,pty=True,echo=True)
                
            case VivadoStep.RESET_RUN:
                if run_name is None:
                    print(f"[!x!] Run name must be specified for reset_run")
                    print(f"[i] Usage: hdlforge vivado --step reset_run --run-name <run_name>")
                    print(f"[i] Available runs:")
                    # List all runs first to show what's available
                    with c.cd(str(project_loader.vivado_build_dir)):
                        c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_loader.vivado_project_xpr_relative}",pty=True,echo=True)
                    exit(1)
                
                print(f"[i] Resetting Vivado run: {run_name} in project: {project_loader.vivado_project_name}")
                with c.cd(str(project_loader.vivado_build_dir)):
                    c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  reset_run  {project_loader.vivado_project_xpr_relative} {run_name}",pty=True,echo=True)
            case VivadoStep.SYN | VivadoStep.IMPL | VivadoStep.BIT:
                print(f"[i] Running Vivado synthesis for project: {project_loader.vivado_project_name}",flush=True)
                if run_flow is None:
                    print("[i] Available run_flow options:")
                    for key, value in project_loader.vivado_runs_flow.items():
                        print(f"--run-flow {key} ~  {key}: {value}")
                    print("[!x!] Please specify a valid run_flow argument using --run-flow <option>")
                    exit(1)
                runs_flow = project_loader.vivado_runs_flow[run_flow]
                syth_name=runs_flow["synth"]
                impl_name_list=runs_flow["impl"]
                paramaters = runs_flow.get("paramaters", [])
                defines = runs_flow.get("defines", [])
                paramaters= " ".join(paramaters)
                defines= " ".join(defines)
                call_compile_tcl(f"{s}" ,f"{syth_name}" ,impl_name_list ,f"'{paramaters}'" ,f"'{defines}'" )
          
            case VivadoStep.ALL:
                print(f"[i] Running Vivado synthesis, implementation and bitstream generation for project: {project_loader.vivado_project_name}")
                with c.cd(str(project_loader.vivado_build_dir)):
                    c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {project_loader.vivado_project_xpr_relative} all",pty=True,echo=True)
            
            case VivadoStep.GEN:
                print(f"[i] Generating Vivado project from TCL: {project_loader.vivado_project_name}")
                
                # Check if TCL file exists
                if not project_loader.vivado_project_tcl.exists():
                    print(f"[!x!] Project TCL file not found: {project_loader.vivado_project_tcl}")
                    print(f"[i] Please create the TCL file first or use --step new to generate it")
                    exit(1)
                
                # Set origin_dir to "." since we'll run from within _vivado directory
                # This allows source paths like "$origin_dir/../sources/..." to resolve correctly
                origin_dir = "."
                
                # Show command details
                print("=" * 80)
                print("[i] Command Details:")
                print(f"    TCL File:     {project_loader.vivado_project_tcl}")
                print(f"    Working Dir:  {project_loader.vivado_build_dir}")
                print(f"    Origin Dir:   {origin_dir}")
                print(f"    Project Name: {project_loader.vivado_project_name}")
                print(f"    Output:       {project_loader.vivado_project_xpr_path}")
                print("=" * 80)
                
                # Warn if project already exists
                if project_loader.vivado_project_xpr_path.exists():
                    print(f"⚠️  WARNING: Project already exists: {project_loader.vivado_project_xpr_path}")
                    print(f"    This operation will overwrite the existing project!")
                    if not force:
                        response = input(f"Continue? (y/n) [n]: ").strip().lower()
                        if response != 'y' and response != 'yes':
                            print("Operation cancelled.")
                            return
                    else:
                        print("[i] Force flag set, proceeding with overwrite...")
                
                # Show the exact command
                # Note: We run from _vivado directory with origin_dir="."
                cmd = f"vivado -mode batch -source {project_loader.vivado_project_tcl} -notrace -tclargs --origin_dir {origin_dir} --project_name {project_loader.vivado_project_name}"
                print(f"\n[i] Executing command:")
                print(f"    cd {project_loader.vivado_build_dir}")
                print(f"    {cmd}\n")
                
                # Ask for final confirmation
                if not force:
                    response = input(f"Execute this command? (y/n) [y]: ").strip().lower()
                    if response == 'n' or response == 'no':
                        print("Operation cancelled.")
                        return
                
                # Create build directory if it doesn't exist
                c.run(f"mkdir -p {project_loader.vivado_build_dir}")
                
                # Execute the command from within _vivado directory
                with c.cd(str(project_loader.vivado_build_dir)):
                    c.run(cmd, pty=True, echo=True)
                
                print(f"[+] Project generated successfully: {project_loader.vivado_project_xpr_path}")
            
            case VivadoStep.WRITE_TCL:
                print(f"[i] Exporting Vivado project to TCL: {project_loader.vivado_project_name}")
                
                # Check if project exists
                if not project_loader.vivado_project_xpr_path.exists():
                    print(f"[!x!] Project file not found: {project_loader.vivado_project_xpr_path}")
                    print(f"[i] Please create the project first using --step new or --step gen")
                    exit(1)
                
                # Show command details
                print("=" * 80)
                print("[i] Command Details:")
                print(f"    Project:      {project_loader.vivado_project_xpr_path}")
                print(f"    Output TCL:   {project_loader.vivado_project_tcl}")
                print(f"    Options:      -all_properties -no_copy_sources -use_bd_files -dump_project_info")
                print("=" * 80)
                
                # Warn if TCL file already exists
                if project_loader.vivado_project_tcl.exists():
                    print(f"⚠️  WARNING: TCL file already exists: {project_loader.vivado_project_tcl}")
                    print(f"    This operation will overwrite the existing file!")
                    if not force:
                        response = input(f"Continue? (y/n) [n]: ").strip().lower()
                        if response != 'y' and response != 'yes':
                            print("Operation cancelled.")
                            return
                    else:
                        print("[i] Force flag set, proceeding with overwrite...")
                
                # Calculate relative path from _vivado directory to the output TCL file
                # Since TCL file is in project root and we run from _vivado, we need to go up one level
                try:
                    output_tcl_relative = project_loader.vivado_project_tcl.relative_to(project_loader.vivado_build_dir)
                except ValueError:
                    # TCL file is not under _vivado, calculate path from working_path
                    output_tcl_relative = project_loader.vivado_project_tcl.relative_to(project_loader.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    output_tcl_relative = Path("..") / output_tcl_relative
                
                # Show the command
                cmd = f"vivado -mode batch -source {SCRIPT_DIR}/write_project_tcl.tcl -notrace -tclargs {project_loader.vivado_project_xpr_relative} {output_tcl_relative}"
                print(f"\n[i] Executing command:")
                print(f"    {cmd}\n")
                
                # Ask for final confirmation
                if not force:
                    response = input(f"Execute this command? (y/n) [y]: ").strip().lower()
                    if response == 'n' or response == 'no':
                        print("Operation cancelled.")
                        return
                
                # Execute the command
                with c.cd(str(project_loader.vivado_build_dir)):
                    c.run(cmd, pty=True, echo=True)
                
                print(f"[+] Project TCL exported successfully: {project_loader.vivado_project_tcl}")
            
            case VivadoStep.COMMIT:
                print(f"[i] Updating HDLForge project file with runs from Vivado project: {project_loader.vivado_project_name}")
                
                # Check if project exists
                if not project_loader.vivado_project_xpr_path.exists():
                    print(f"[!x!] Project file not found: {project_loader.vivado_project_xpr_path}")
                    print(f"[i] Please create the project first using --step new or --step gen")
                    exit(1)
                
                # Run list_all_runs command and capture output
                with c.cd(str(project_loader.vivado_build_dir)):
                    result = c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_loader.vivado_project_xpr_relative}",pty=True,echo=True)
                
                # Parse output to get all runs
                all_runs_dict = {}
                synth_runs = []
                impl_runs = []
                output_lines = result.stdout.split('\n') if hasattr(result, 'stdout') else []
                
                # Parse all runs and store in dictionary
                for line in output_lines:
                    line_stripped = line.strip()
                    if line_stripped and '\t' in line_stripped:
                        # Parse format: run_name\tSynth=1 Impl=0 Status=... Parent=...
                        parts = line_stripped.split('\t')
                        if len(parts) >= 2:
                            run_name = parts[0].strip()
                            # Parse properties
                            props_str = parts[1].strip()
                            props = {}
                            prop_pattern = r'(\w+)=([^\s]+(?:\s+[^\s=]+)*?)(?=\s+\w+=|$)'
                            for match in re.finditer(prop_pattern, props_str):
                                key = match.group(1)
                                value = match.group(2).strip()
                                props[key] = value
                            
                            run_type = "Unknown"
                            synth_val = props.get('Synth', '').strip()
                            impl_val = props.get('Impl', '').strip()
                            parent = props.get('Parent', '').strip()
                            status = props.get('Status', 'Unknown')
                            
                            # Handle both numeric (1/0) and boolean (true/false) values
                            if synth_val in ('1', 'true', 'True'):
                                run_type = "Synthesis"
                                synth_runs.append({
                                    'name': run_name
                                })
                            elif impl_val in ('1', 'true', 'True'):
                                run_type = "Implementation"
                                impl_runs.append({
                                    'name': run_name,
                                    'parent': parent
                                })
                
                # Get current runs_flow from project_loader
                current_runs_flow = project_loader.vivado_runs_flow.copy()
                
                # Create sets of existing synth and impl run names for quick lookup
                existing_synth_names = {synth['name'] for synth in synth_runs}
                existing_impl_names = {impl['name'] for impl in impl_runs}
                
                # Build new runs_flow structure - only include runs that exist in Vivado
                new_runs_flow = {}
                
                for synth in synth_runs:
                    # Create flow name: synth_run_name + "flow" (e.g., "synth_main" -> "synth_mainflow")
                    flow_name = f"{synth['name']}flow"
                    
                    # Preserve defines and parameters from existing flow if it exists
                    existing_defines = []
                    existing_parameters = []
                    if flow_name in current_runs_flow:
                        existing_flow_data = current_runs_flow[flow_name]
                        existing_defines = existing_flow_data.get('defines', [])
                        existing_parameters = existing_flow_data.get('paramaters', [])
                    
                    # Find all implementation runs that belong to this synthesis run
                    impl_list = []
                    for impl in impl_runs:
                        if impl['parent'] == synth['name']:
                            # Only include impl runs that still exist
                            if impl['name'] in existing_impl_names:
                                # Check if this impl run already exists in current runs_flow
                                impl_dict = None
                                # Search through current flows to find if this impl exists
                                for existing_flow_name, existing_flow_data in current_runs_flow.items():
                                    existing_impl = existing_flow_data.get('impl', [])
                                    # Check if impl is a list
                                    if isinstance(existing_impl, list):
                                        for existing_impl_item in existing_impl:
                                            if isinstance(existing_impl_item, dict):
                                                if existing_impl_item.get('name') == impl['name']:
                                                    # Found existing entry - preserve it as-is (including enabled/disabled)
                                                    impl_dict = existing_impl_item.copy()
                                                    break
                                            elif existing_impl_item == impl['name']:
                                                # Old format (just string) - convert to dict with enabled
                                                impl_dict = {'name': impl['name'], 'enabled': True}
                                                break
                                    elif isinstance(existing_impl, dict):
                                        # Single dict
                                        if existing_impl.get('name') == impl['name']:
                                            impl_dict = existing_impl.copy()
                                            break
                                    elif existing_impl == impl['name']:
                                        # Single string
                                        impl_dict = {'name': impl['name'], 'enabled': True}
                                    
                                    if impl_dict:
                                        break
                                
                                # If not found, create new with enabled=True
                                # If found but doesn't have 'enabled', add it as True
                                # If found and has 'enabled', keep it as-is (don't edit)
                                if impl_dict is None:
                                    impl_dict = {'name': impl['name'], 'enabled': True}
                                elif 'enabled' not in impl_dict:
                                    impl_dict['enabled'] = True
                                
                                impl_list.append(impl_dict)
                    
                    # Create the flow entry - only if synth run still exists
                    # Preserve defines and parameters from existing flow, or use empty lists
                    if synth['name'] in existing_synth_names:
                        new_runs_flow[flow_name] = {
                            'synth': synth['name'],
                            'paramaters': existing_parameters if existing_parameters else [],
                            'defines': existing_defines if existing_defines else [],
                            'impl': impl_list
                        }
                
                # Compare new and current runs_flow to detect changes
                import json
                changes_detected = False
                removed_flows = []
                added_flows = []
                modified_flows = []
                
                # Check for removed flows
                for existing_flow_name, existing_flow_data in current_runs_flow.items():
                    existing_synth = existing_flow_data.get('synth', '')
                    if existing_synth not in existing_synth_names:
                        removed_flows.append(existing_flow_name)
                        changes_detected = True
                
                # Check for added or modified flows
                for new_flow_name, new_flow_data in new_runs_flow.items():
                    if new_flow_name not in current_runs_flow:
                        added_flows.append(new_flow_name)
                        changes_detected = True
                    else:
                        # Compare flow data
                        current_flow_data = current_runs_flow[new_flow_name]
                        # Compare synth, defines, parameters, and impl list
                        if (current_flow_data.get('synth') != new_flow_data.get('synth') or
                            current_flow_data.get('defines') != new_flow_data.get('defines') or
                            current_flow_data.get('paramaters') != new_flow_data.get('paramaters')):
                            modified_flows.append(new_flow_name)
                            changes_detected = True
                        else:
                            # Compare impl lists (order and content)
                            current_impl = current_flow_data.get('impl', [])
                            new_impl = new_flow_data.get('impl', [])
                            # Normalize impl lists for comparison
                            def normalize_impl(impl_list):
                                result = []
                                for item in impl_list:
                                    if isinstance(item, dict):
                                        result.append((item.get('name'), item.get('enabled', True)))
                                    else:
                                        result.append((item, True))
                                return sorted(result)
                            
                            if normalize_impl(current_impl) != normalize_impl(new_impl):
                                modified_flows.append(new_flow_name)
                                changes_detected = True
                
                # First, write the TCL script (before updating runs_flow)
                print(f"\n[i] Exporting Vivado project to TCL: {project_loader.vivado_project_name}")
                
                # Calculate relative path from _vivado directory to the output TCL file
                # Since TCL file is in project root and we run from _vivado, we need to go up one level
                try:
                    output_tcl_relative = project_loader.vivado_project_tcl.relative_to(project_loader.vivado_build_dir)
                except ValueError:
                    # TCL file is not under _vivado, calculate path from working_path
                    output_tcl_relative = project_loader.vivado_project_tcl.relative_to(project_loader.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    output_tcl_relative = Path("..") / output_tcl_relative
                
                # Execute the command using the reusable script
                cmd = f"vivado -mode batch -source {SCRIPT_DIR}/write_project_tcl.tcl -notrace -tclargs {project_loader.vivado_project_xpr_relative} {output_tcl_relative}"
                print(f"[i] Executing: {cmd}")
                
                with c.cd(str(project_loader.vivado_build_dir)):
                    c.run(cmd, pty=True, echo=True)
                
                print(f"[+] Project TCL exported successfully: {project_loader.vivado_project_tcl}")
                
                # Then, update the runs_flow in JSON (if there are changes)
                if not changes_detected:
                    print("\n[i] No changes detected. Project file is already up to date with Vivado project runs.")
                else:
                    # Show what will be changed
                    if removed_flows:
                        print("\n" + "=" * 80)
                        print("[i] Flows that will be removed (synthesis runs no longer exist in Vivado):")
                        print("=" * 80)
                        for flow_name in removed_flows:
                            print(f"  - {flow_name}")
                        print("=" * 80 + "\n")
                    
                    if added_flows:
                        print("\n" + "=" * 80)
                        print("[i] Flows that will be added:")
                        print("=" * 80)
                        for flow_name in added_flows:
                            print(f"  + {flow_name}")
                        print("=" * 80 + "\n")
                    
                    if modified_flows:
                        print("\n" + "=" * 80)
                        print("[i] Flows that will be modified:")
                        print("=" * 80)
                        for flow_name in modified_flows:
                            print(f"  ~ {flow_name}")
                        print("=" * 80 + "\n")
                    
                    # Show what will be updated
                    print("\n" + "=" * 80)
                    print("[i] Updated runs_flow:")
                    print("=" * 80)
                    print(json.dumps(new_runs_flow, indent=2))
                    print("=" * 80 + "\n")
                    
                    # Ask for confirmation only if there are changes
                    if not force:
                        response = input(f"Update project file with these runs_flow settings? (y/n) [y]: ").strip().lower()
                        if response == 'n' or response == 'no':
                            print("Operation cancelled.")
                            return
                    
                    # Update the project data
                    project_loader.update_vivado_runs_flow(new_runs_flow)
                    project_loader.save_project_data()
                    
                    print(f"[+] Successfully updated runs_flow in {project_loader.project_file_path.name}")
            
            case VivadoStep.CMD_GEN:
                # Generate TCL command for piping to vivado
                if cmd is None:
                    print("[!x!] --cmd argument is required for cmd-gen", file=sys.stderr)
                    exit(1)
                
                if not project_loader.vivado_project_xpr_path.exists():
                    print(f"[!x!] Project file not found: {project_loader.vivado_project_xpr_path}", file=sys.stderr)
                    exit(1)
                
                # Calculate relative path from _vivado directory to project
                project_xpr_relative = project_loader.vivado_project_xpr_relative
                
                # Generate TCL command
                tcl_lines = [
                    f"open_project {project_xpr_relative}",
                    f"set_property board_part {{}} [current_project]"
                ]
                
                # Build the command based on cmd type
                if cmd == "add_files":
                    if arg is None:
                        print("[!x!] --arg is required for add_files command (file path)", file=sys.stderr)
                        exit(1)
                    # Determine fileset based on file extension or use default
                    fileset = "sources_1"
                    if arg.endswith(('.vhd', '.vhdl')):
                        fileset = "sources_1"
                    elif arg.endswith(('.v', '.sv')):
                        fileset = "sources_1"
                    tcl_lines.append(f"{cmd} -fileset {fileset} {arg}")
                else:
                    # Generic command - just append cmd and arg
                    if arg:
                        tcl_lines.append(f"{cmd} {arg}")
                    else:
                        tcl_lines.append(cmd)
                
                tcl_lines.append("close_project")
                
                # Print to stdout (can be piped)
                print("\n".join(tcl_lines))
            
            case _:
                pass


     
   
def verify_sim_target(SimTargetName, verilator_settings)    :
    # Convert sim_targets list to dictionary using 'name' as key
    sim_targets_dict = {}
    for target in verilator_settings['sim_targets']:
        sim_targets_dict[target['name']] = target
    
    if SimTargetName is None:
        exit(f"[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
    elif(SimTargetName not in sim_targets_dict):
        print(f"Available SimTargetNames: {', '.join(sim_targets_dict.keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")

    return sim_targets_dict[SimTargetName]

def Verilator(c,project,step=None,clean=False,SimTargetName=None,flags=None,extra_env=None):
    # Capture environment variables set by update_repo_path
    capture_environment_variables(c)
    
    extra_env= dict(item.split('=') for item in extra_env.split(',') if '=' in item) if extra_env else {}
    tool_name = "verilator"

    ALLOWED_STEPS = {"step":["sim", "build"],"extra_env":["DEBUG=1"]}
    
    if isinstance(flags, str):  # Convert single input to list
        flags = [flags]
    elif flags is None:
        flags = []

    if isinstance(step, str):  # Convert single input to list
        step = [step]
    elif step is None:
        step = []
    
    REPO_TOP = Path(os.environ["REPO_TOP"])  # Fail fast if REPO_TOP is not set
    
    # Load project using ProjectLoader (single source of truth)
    project_loader = ProjectLoader(project)
    project_loader.verify_repo_path()
    
    # Get project information from ProjectLoader (all values computed in __init__)
    working_path = project_loader._working_path
    project_data = project_loader._project_data
    verilator_settings = project_loader.verilator_settings
    
    # Extract available SimTargetNames for display
    available_sim_targets = [target['name'] for target in project_loader.verilator_sim_targets]
    ALLOWED_STEPS["SimTargetName"] = available_sim_targets
    
    print_task_args(locals(),str(REPO_TOP),ALLOWED_STEPS)
    
    # Check if SimTargetName is specified before proceeding
    if SimTargetName is None:
        print(f"\n[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
        return
    
    build_dir = project_loader.verilator_build_dir
    SOURCES_DICT_LIST = project_loader.get_verilator_sources()
      
    
    # Verify the parameters and get the target data
    SimTarget = project_loader.get_sim_target(SimTargetName)
    if SimTarget is None:
        print(f"\n[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")
        print(f"Available SimTargetNames: {', '.join(available_sim_targets)}")
        exit(1)    
    
    top_module                = SimTarget["top_module"]
    build_args                = SimTarget.get("build_args", [])
    defines                   = SimTarget.get("defines", {})
    parameters                = SimTarget.get("parameters", {})
    python_file_path          = Path(working_path ) / SimTarget["python_file"] 
    test_name                 = SimTarget.get("test_name",None)

    PYTHONPATH = SimTarget.get("PYTHONPATH", [])
    add_python_paths_from_list(PYTHONPATH, working_path)
  

    
    print(f"\n[~] processing steps {step}",flush=True)
    sys.stdout.flush()
    for s in step:
        match (s):
            case "build" | "sim":
                try:
                    print(f"[i] Verilator step: {s}",flush=True)
                    print(f"[i] Compiling Verilator sources into: {build_dir}",flush=True)
                    veruilator_sources_file = []
                    for file_dict in SOURCES_DICT_LIST:
                        veruilator_sources_file.append(Path(os.path.expandvars(str(file_dict["file"]))).resolve())
                    sys.stdout.flush()
                    print(f"\n================start of verilator output : build================",flush=True)
                    # Suppress the specific message before importing cocotb.runner
                    warnings.filterwarnings(
                        "ignore",
                        message="Python runners and associated APIs are an experimental feature and subject to change.",
                        category=UserWarning,
                    )                
                    from cocotb.runner import get_runner

                    runner = get_runner("verilator")
                    defines={}
                    parameters={}
                    log_file = None
                    includes_paths_list=[]
                    for _ in verilator_settings["includes_paths"]:
                        includes_paths_list.append(Path(os.path.expandvars(str(_))).resolve())
                    # Use only the build_args from project configuration
                    combined_build_args = build_args
                    
                    runner.build(
                            verilog_sources=veruilator_sources_file,
                            hdl_toplevel=f"{top_module}",
                            waves=True   ,
                            always=True, 
                            verbose=False, 
                            build_dir=f"{build_dir}",   
                            defines=defines,  
                            includes=includes_paths_list,
                            parameters=parameters,
                            log_file=log_file,  # Use default logging
                            build_args=combined_build_args,
                            clean=clean   # force rebuild
                        )
                    print(f"================end of verilator output : build================\n",flush=True)
                    print(f"[+] Verilator build completed",flush=True)
                    
                    if(s=="sim"):  
                        print(f"[i] Verilator simulation started:",flush=True)
                        print(f"\n================start of verilator output : sim================",flush=True)  
                        runner.test(
                            hdl_toplevel=f"{top_module}",
                            test_module=f"{python_file_path.stem}",  
                            testcase=test_name,          
                            build_dir=f"{build_dir}",   
                            extra_env=extra_env,
                            test_dir=f"{build_dir}/{SimTargetName}",      # Directory for test outputs
                            waves=True                  # enables dump.vcd
                        )
                        print(f"================end of verilator output : sim================\n",flush=True)
                        print(f"[i] Verilator simulation completed",flush=True)
                        
                        # Check for VCD file generation
                        vcd_file_path = build_dir / SimTargetName / "dump.vcd"
                        
                        if vcd_file_path.exists():
                            print(f"[i] Found VCD file: {vcd_file_path}")
                        else:
                            print(f"[!x!] VCD file not found: {vcd_file_path}")
                            print(f"[i] Simulation may not have generated VCD file (waves=True required)")
                    else:
                        print(f"[i] Skipping Verilator simulation",flush=True)
                        
                except Exception as e:
                    print("\n[!x!]  Verilator build/simulation failed!",flush=True)
                    print(f"Error: {e}",flush=True)

def projects(c,set_project=None):
    """List available projects in the current directory."""
    # Use ProjectLoader to detect project files
    try:
        project_loader = ProjectLoader(None)
        print(f"Found project: {project_loader.project_file_path.name}")
        print(f"  Path: {project_loader.project_file_path}")
        print(f"  Project Name: {project_loader.project_name}")
        print(f"  Working Path: {project_loader.working_path}")
    except SystemExit:
        # ProjectLoader will handle error messages
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
    print("  2. Create Vivado project: hdlforge vivado --step new --clean")
    print("  3. Run synthesis: hdlforge vivado --step syn --run-flow default")
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
    vivado_parser.add_argument('--step', action='append')
    vivado_parser.add_argument('--verbose', action='store_true')
    vivado_parser.add_argument('--clean', action='store_true')
    vivado_parser.add_argument('--run-flow')
    vivado_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation prompts')
    vivado_parser.add_argument('--run-name', help='Run name for reset_run command')
    vivado_parser.add_argument('--cmd', help='TCL command name for cmd-gen (e.g., add_files)')
    vivado_parser.add_argument('--arg', help='Arguments for the TCL command (e.g., file path)')
    
    # Other subcommands
    subparsers.add_parser('projects')
    subparsers.add_parser('help')
    
    args = parser.parse_args()
    
    # Create invoke Context manually
    c = Context()
    
    if args.command == 'Verilator':
        Verilator(c, args.project, args.step, args.clean, args.SimTargetName, args.flags, args.extra_env)
    elif args.command == 'vivado':
        vivado(c, args.project, args.verbose, args.step, args.clean, args.run_flow, args.force, args.run_name, args.cmd, args.arg)
    elif args.command == 'projects':
        projects(c, getattr(args, 'set_project', None))
    elif args.command == 'help':
        help(c)
    else:
        parser.print_help()


