#!/usr/bin/env python3
"""
Vivado task handlers for HDLForge
"""

import os
import sys
from pathlib import Path
from typing import List
from enum import Enum
import re
import invoke
import threading
import time
from tabulate import tabulate

from project_file import ProjectFile

HDLFORGE_CHILD_RUNS_PREFIX = "HDLFORGE_CHILD_RUNS "


def parse_vivado_child_runs_stdout(stdout: str) -> List[str]:
    """
    Parse child implementation run names from project_tool.tcl get_child_runs output.
    Uses line 'HDLFORGE_CHILD_RUNS run1 run2 ...' so Vivado banner text on stdout is ignored.
    """
    if not stdout:
        return []
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith(HDLFORGE_CHILD_RUNS_PREFIX):
            rest = s[len(HDLFORGE_CHILD_RUNS_PREFIX) :].strip()
            return rest.split() if rest else []
    noise_markers = (
        "INFO:",
        "WARNING:",
        "ERROR:",
        "Copyright",
        "Vivado",
        "SW Build",
        "****",
        "source ",
        "open_project",
        "Scanning sources",
        "Memory (MB)",
        "Finished scanning",
        "Start of session",
        "SharedData Build",
        "IP Build",
    )
    child_lines: List[str] = []
    for line in stdout.splitlines():
        t = line.strip()
        if not t or any(m in t for m in noise_markers):
            continue
        child_lines.append(t)
    if not child_lines:
        return []
    return " ".join(child_lines).split()


def _clean_logs_from_current_dir(verbose: bool = False, force: bool = False):
    """
    Clean Vivado log files from current working directory.
    
    Cleans: vivado.log, vivado.jou, vivado_*.backup.jou, vivado_*.backup.log
    
    Args:
        verbose: Show each file being removed
        force: Skip confirmation prompt
    """
    # Use HDLFORGE_ORIG_DIR (set by hdlforge bash script) to get the original invocation directory
    current_dir = Path(os.environ.get('HDLFORGE_ORIG_DIR', os.getcwd()))
    print(f"[i] Cleaning Vivado log files from: {current_dir}")
    
    # Collect files matching the specific patterns (non-recursive)
    files_to_delete = []
    
    # vivado.log
    vivado_log = current_dir / "vivado.log"
    if vivado_log.exists():
        files_to_delete.append(vivado_log)
    
    # vivado.jou
    vivado_jou = current_dir / "vivado.jou"
    if vivado_jou.exists():
        files_to_delete.append(vivado_jou)
    
    # vivado_*.backup.jou
    backup_jou_files = list(current_dir.glob("vivado_*.backup.jou"))
    files_to_delete.extend(backup_jou_files)
    
    # vivado_*.backup.log
    backup_log_files = list(current_dir.glob("vivado_*.backup.log"))
    files_to_delete.extend(backup_log_files)
    
    if len(files_to_delete) == 0:
        print("[+] No Vivado log files found to clean")
        return
    
    print(f"\n[i] Found {len(files_to_delete)} file(s) to delete:")
    for f in files_to_delete:
        print(f"   • {f.name}")
    print()
    
    # Confirm deletion
    if not force:
        response = input(f"[!] Delete {len(files_to_delete)} file(s)? [y/N] ").strip().lower()
        if response != 'y' and response != 'yes':
            print("[!] Cancelled")
            return
    
    # Delete files
    deleted_count = 0
    for file in files_to_delete:
        try:
            file.unlink()
            deleted_count += 1
            if verbose:
                print(f"   [-] Removed: {file.name}")
        except Exception as e:
            print(f"   [!] Failed to remove {file.name}: {e}")
    
    if not verbose:
        print(f"[-] Removed {deleted_count} file(s)")
    
    print(f"\n[+] Clean complete - Removed {deleted_count} file(s)")


class VivadoStep(str, Enum):
    """Enum for Vivado step names"""
    LIST_RUNS = "list_runs"
    RESET_RUN = "reset_run"
    SYN = "syn"
    IMPL = "impl"
    BIT = "bit"
    LINT = "lint"
    ALL = "all"
    GENERATE_PRJ_WITH_EXTERNAL_TCL = "generate_prj_with_external_tcl"
    WRITE_TCL = "write_tcl"
    CLEAN_LOGS = "clean_logs"
    FILE_REMOVE = "file_remove"
    FILE_ADD = "file_add"


def vivado(c, project, verbose=False, step: List[str] = [], clean=False, force=False, run_name=None, file_path=None):
    """
    Vivado command handler.
    
    Args:
        c: Invoke context
        project: Project file path
        verbose: Verbose output
        step: List of steps to execute
        clean: Clean the Vivado project directory
        force: Skip confirmation prompts
        run_name: Run name (required for reset_run, syn, impl, bit steps)
        file_path: File path (required for file_remove, file_add steps)
    """
    # Import shared utilities
    from environment import capture_environment_variables
    
    # Capture environment variables set by update_repo_path
    capture_environment_variables(c)
    
    # Handle None or empty step
    if step is None:
        step = []
    elif isinstance(step, str):
        step = [step]
    
    # Handle clean_logs early - it doesn't require a project file
    if step == ['clean_logs']:
        _clean_logs_from_current_dir(verbose, force)
        return

    TOOL_NAME = "vivado"
    # Get script directory from environment or use the directory where this script is located
    SCRIPT_DIR = Path(os.environ.get("HDLFORGE", str(Path(__file__).parent)))
    REPO_TOP = Path(os.environ["REPO_TOP"]) 

    # Load project using ProjectFile (single source of truth)
    project_file = ProjectFile(project)
    project_file.verify_repo_path()
    project_file.require_vivado_project_name()

    def cleaning(BUILD_DIR, clean, force=False):
        if clean:
            project_dir = project_file.vivado_project_xpr_path.parent
            print(f"[i] Cleaning Vivado project directory: {project_dir}")
            if project_dir.exists():
                if not force:
                    response = input(f"{project_dir} will be deleted! (y/n): ")
                    if response.lower() != "y":
                        print("Aborted clean operation.")
                        return
                c.run(f"rm -rf {project_dir}")
                print(f"[+] removed Vivado project directory: {project_dir}")
            else:
                print(f"[i] nothing to clean in Vivado project directory: {project_dir}")
            c.run(f"mkdir -p {BUILD_DIR}")
    
    if clean:
        cleaning(project_file.vivado_build_dir, True, force)

    def parse_synth_run_names(run_names_value: str | None) -> List[str]:
        if run_names_value is None:
            return []
        synth_run_names = []
        for item in run_names_value.split(","):
            run_name = item.strip()
            if run_name:
                synth_run_names.append(run_name)
        return synth_run_names

    def call_compile_tcl(step, synth_run_names, impl_list, paramaters, defines):
        # Filter enabled implementations
        enabled_impls = []
        for impl_item in impl_list:
            if isinstance(impl_item, dict):
                if impl_item.get('enabled', True):  # Default to enabled if not specified
                    enabled_impls.append(impl_item['name'])
            else:
                # Old format - just a string, treat as enabled
                enabled_impls.append(impl_item)
        
        synth_run_names = [run_name.strip() for run_name in synth_run_names if run_name and run_name.strip()]
        if not synth_run_names:
            print("[!x!] At least one synth run must be provided to compile.tcl")
            exit(1)

        if not enabled_impls and step not in {"syn", "impl", "bit", "all"}:
            print("[i] No enabled implementation runs were provided.")
        
        synth_names_str = " ".join(synth_run_names)
        # Join enabled impl names with space for TCL script
        impl_names_str = " ".join(enabled_impls)
        
        with c.cd(str(project_file.vivado_build_dir)):
            table = [["Step", step]]
            table.append(["Synth", synth_names_str])
            table.append(["Impl", impl_names_str])
            table.append(["Parameters", paramaters])
            table.append(["Defines", defines])
            print(tabulate(table, headers="firstrow", tablefmt="grid"))

            cmd = f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {project_file.vivado_project_xpr_relative} {step} '{synth_names_str}' '{impl_names_str}' '{paramaters}' '{defines}'"
            print(f"\n[i] Running Vivado compile TCL script with command: {cmd}\n", flush=True)
            c.run(cmd, pty=True, echo=True)

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
            case VivadoStep.LIST_RUNS:
                # Check if build directory exists
                if not project_file.vivado_build_dir.exists():
                    print(f"[!x!] Vivado build directory not found: {project_file.vivado_build_dir}")
                    print(f"[i] Please create the project first using: hdlforge vivado --step gen")
                    exit(1)
                
                # Check if project file exists
                if not project_file.vivado_project_xpr_path.exists():
                    print(f"[!x!] Vivado project file not found: {project_file.vivado_project_xpr_path}")
                    print(f"[i] Expected location: {project_file.vivado_project_xpr_path}")
                    print(f"[i] Please create the project first using: hdlforge vivado --step gen")
                    exit(1)
                
                # Print progress messages
                print(f"[i] Listing Vivado runs for project: {project_file.vivado_project_name}")
                print(f"[i] Opening Vivado...")
                
                # Build the command
                cmd = f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_file.vivado_project_xpr_relative}"
                print(f"[i] Running command: vivado -mode batch -source project_tool.tcl -notrace -tclargs list_all_runs {project_file.vivado_project_xpr_relative}")
                print(f"[i] Please wait", end='', flush=True)
                
                # Simple spinner function
                spinner_active = threading.Event()
                spinner_active.set()
                
                def spinner():
                    chars = ['|', '/', '-', '\\']
                    i = 0
                    while spinner_active.is_set():
                        print(f'\r[i] Please wait {chars[i % len(chars)]}', end='', flush=True)
                        i += 1
                        time.sleep(0.2)
                
                # Start spinner in background thread
                spinner_thread = threading.Thread(target=spinner, daemon=True)
                spinner_thread.start()
                
                # Run list_all_runs command and capture output silently (no live streaming)
                try:
                    with c.cd(str(project_file.vivado_build_dir)):
                        result = c.run(cmd, pty=False, echo=False, warn=True, hide='stdout')
                    
                    # Stop spinner
                    spinner_active.clear()
                    spinner_thread.join(timeout=0.5)
                    print('\r[i] Done!                    \n', flush=True)  # Clear spinner line
                    
                    # Check if command failed
                    if result.exited != 0:
                        print(f"[!x!] Vivado command failed with exit code: {result.exited}")
                        if hasattr(result, 'stderr') and result.stderr:
                            print(f"[!x!] Error output: {result.stderr}")
                        exit(1)
                except invoke.exceptions.UnexpectedExit as e:
                    print(f"[!x!] Failed to execute Vivado command")
                    print(f"[!x!] Error: {e}")
                    print(f"[i] Make sure Vivado is installed and in your PATH")
                    exit(1)
                except Exception as e:
                    print(f"[!x!] Unexpected error while executing Vivado command: {e}")
                    print(f"[i] Make sure Vivado is installed and in your PATH")
                    exit(1)
                
                # Parse output - simplified to show run names with type and parent
                output_lines = result.stdout.split('\n') if hasattr(result, 'stdout') else []
                runs = []
                
                # Parse all runs
                for line in output_lines:
                    line_stripped = line.strip()
                    if line_stripped and '\t' in line_stripped:
                        # Parse format: run_name\tSynth=1 Impl=0 Status=... Parent=...
                        parts = line_stripped.split('\t')
                        if len(parts) >= 2:
                            run_name = parts[0].strip()
                            # Parse properties: "Synth=1 Impl=0 Status=... Parent=..."
                            props_str = parts[1].strip()
                            props = {}
                            # Simple parsing - just get Synth, Impl, Status, Parent
                            prop_pattern = r'(\w+)=([^\s]+(?:\s+[^\s=]+)*?)(?=\s+\w+=|$)'
                            for match in re.finditer(prop_pattern, props_str):
                                key = match.group(1)
                                value = match.group(2).strip()
                                # Only keep Synth, Impl, Status, Parent
                                if key in ['Synth', 'Impl', 'Status', 'Parent']:
                                    props[key] = value
                            
                            run_type = "Unknown"
                            synth_val = props.get('Synth', '').strip()
                            impl_val = props.get('Impl', '').strip()
                            parent = props.get('Parent', '').strip()
                            status = props.get('Status', 'Unknown')
                            
                            # Handle both numeric (1/0) and boolean (true/false) values
                            if synth_val in ('1', 'true', 'True'):
                                run_type = "synth"
                            elif impl_val in ('1', 'true', 'True'):
                                run_type = "impl"
                            
                            runs.append({
                                'name': run_name,
                                'type': run_type,
                                'status': status,
                                'parent': parent if parent else "(none)"
                            })
                
                # Display runs in a simple table
                if runs:
                    print("\n" + "=" * 80)
                    print("[i] Vivado Runs:")
                    print("=" * 80)
                    table = [["Run Name", "Type", "Parent", "Status"]]
                    for run in runs:
                        table.append([run['name'], run['type'], run['parent'], run['status']])
                    print(tabulate(table, headers="firstrow", tablefmt="fancy_grid"))
                    print("=" * 80 + "\n")
                else:
                    print("\n[i] No runs found in the output.\n")
                
            case VivadoStep.LINT:
                print(f"[i] Running Vivado lint for project: {project_file.vivado_project_name}", flush=True)
                # Parameters and defines are now in TCL file, not JSON
                # Use empty strings (they can be set in TCL if needed)
                paramaters_str = ""
                defines_str = ""
                ignore_error_codes = " ".join(project_file.vivado_lint_ignore_error_codes)
                ignore_warning_codes = " ".join(project_file.vivado_lint_ignore_warning_codes)
                with c.cd(str(project_file.vivado_build_dir)):
                    cmd = f"vivado -mode batch -source {SCRIPT_DIR}/lint.tcl -notrace -tclargs {project_file.vivado_project_xpr_relative} '{paramaters_str}' '{defines_str}' '{ignore_error_codes}' '{ignore_warning_codes}'"
                    print(f"\n[i] Running Vivado lint TCL script with command: {cmd}\n", flush=True)
                    c.run(cmd, pty=True, echo=True)
                
            case VivadoStep.RESET_RUN:
                if run_name is None:
                    print(f"[!x!] Run name must be specified for reset_run")
                    print(f"[i] Usage: hdlforge vivado --reset_run <synth_run_name>")
                    print(f"[i] Available runs:")
                    # List all runs first to show what's available
                    with c.cd(str(project_file.vivado_build_dir)):
                        result = c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_file.vivado_project_xpr_relative}", pty=False, echo=False, warn=True, hide='stdout')
                        # Parse and display runs in formatted table (same logic as LIST_RUNS case)
                        output_lines = result.stdout.split('\n') if hasattr(result, 'stdout') else []
                        runs = []
                        for line in output_lines:
                            line_stripped = line.strip()
                            if line_stripped and '\t' in line_stripped:
                                parts = line_stripped.split('\t')
                                if len(parts) >= 2:
                                    run_name = parts[0].strip()
                                    props_str = parts[1].strip()
                                    props = {}
                                    prop_pattern = r'(\w+)=([^\s]+(?:\s+[^\s=]+)*?)(?=\s+\w+=|$)'
                                    for match in re.finditer(prop_pattern, props_str):
                                        key = match.group(1)
                                        value = match.group(2).strip()
                                        if key in ['Synth', 'Impl', 'Status', 'Parent']:
                                            props[key] = value
                                    run_type = "Unknown"
                                    synth_val = props.get('Synth', '').strip()
                                    impl_val = props.get('Impl', '').strip()
                                    parent = props.get('Parent', '').strip()
                                    status = props.get('Status', 'Unknown')
                                    if synth_val in ('1', 'true', 'True'):
                                        run_type = "synth"
                                    elif impl_val in ('1', 'true', 'True'):
                                        run_type = "impl"
                                    runs.append({
                                        'name': run_name,
                                        'type': run_type,
                                        'status': status,
                                        'parent': parent if parent else "(none)"
                                    })
                        if runs:
                            print("\n" + "=" * 80)
                            print("[i] Vivado Runs:")
                            print("=" * 80)
                            table = [["Run Name", "Type", "Parent", "Status"]]
                            for run in runs:
                                table.append([run['name'], run['type'], run['parent'], run['status']])
                            print(tabulate(table, headers="firstrow", tablefmt="fancy_grid"))
                            print("=" * 80 + "\n")
                        else:
                            print("\n[i] No runs found.\n")
                    exit(1)
                
                # Get child impl runs for the synth run
                print(f"[i] Getting child implementation runs for synth run: {run_name}")
                with c.cd(str(project_file.vivado_build_dir)):
                    result = c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  get_child_runs  {project_file.vivado_project_xpr_relative} {run_name}", pty=False, echo=False, warn=True, hide='stdout')
                    raw = result.stdout.strip() if hasattr(result, 'stdout') else ""
                    child_runs = parse_vivado_child_runs_stdout(raw)
                
                # Reset the synth run
                print(f"[i] Resetting Vivado synth run: {run_name} in project: {project_file.vivado_project_name}")
                with c.cd(str(project_file.vivado_build_dir)):
                    c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  reset_run  {project_file.vivado_project_xpr_relative} {run_name}", pty=True, echo=True)
                
                # Reset all child impl runs
                if child_runs:
                    print(f"[i] Resetting {len(child_runs)} child implementation run(s)")
                    for child_run in child_runs:
                        print(f"[i] Resetting impl run: {child_run}")
                        with c.cd(str(project_file.vivado_build_dir)):
                            c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  reset_run  {project_file.vivado_project_xpr_relative} {child_run}", pty=True, echo=True)
                else:
                    print(f"[i] No child implementation runs found for synth run: {run_name}")
            case VivadoStep.SYN | VivadoStep.IMPL | VivadoStep.BIT:
                print(f"[i] Running Vivado {s} for project: {project_file.vivado_project_name}", flush=True)
                if run_name is None:
                    print(f"[!x!] Synth run name must be specified")
                    print(f"[i] Usage: hdlforge vivado --{s} <synth_run_name[,synth_run_name2,...]>")
                    print("[i] Available runs:")
                    # List all runs first to show what's available
                    with c.cd(str(project_file.vivado_build_dir)):
                        c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_file.vivado_project_xpr_relative}", pty=True, echo=True)
                    exit(1)

                synth_run_names = parse_synth_run_names(run_name)
                
                # Parameters and defines are now in TCL file, not JSON
                # Pass empty strings (they can be set in TCL if needed)
                paramaters = ""
                defines = ""
                call_compile_tcl(f"{s}", synth_run_names, [], paramaters, defines)
          
            case VivadoStep.ALL:
                print(f"[i] Running Vivado synthesis, implementation and bitstream generation for project: {project_file.vivado_project_name}")
                if run_name is None:
                    print(f"[!x!] Synth run name must be specified for all")
                    print(f"[i] Usage: hdlforge vivado --all <synth_run_name[,synth_run_name2,...]>")
                    print("[i] Available runs:")
                    # List all runs first to show what's available
                    with c.cd(str(project_file.vivado_build_dir)):
                        c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {project_file.vivado_project_xpr_relative}", pty=True, echo=True)
                    exit(1)

                synth_run_names = parse_synth_run_names(run_name)
                
                # Parameters and defines are now in TCL file, not JSON
                # Pass empty strings (they can be set in TCL if needed)
                paramaters = ""
                defines = ""
                call_compile_tcl("all", synth_run_names, [], paramaters, defines)
            
            case VivadoStep.GENERATE_PRJ_WITH_EXTERNAL_TCL:
                print(f"[i] Running Vivado project TCL script: {project_file.vivado_project_tcl}")
                
                # Check if TCL file exists
                if not project_file.vivado_project_tcl.exists():
                    print(f"[!x!] TCL file not found: {project_file.vivado_project_tcl}")
                    print(f"[i] Please create the TCL file first")
                    exit(1)
                
                # Show command details
                print("=" * 80)
                print("[i] Command Details:")
                print(f"    TCL File:     {project_file.vivado_project_tcl}")
                print(f"    Working Dir:  {project_file.vivado_build_dir}")
                print(f"    Origin Dir:   {project_file._working_path}")
                print(f"    Project Name:  {project_file.vivado_project_name}")
                print("=" * 80)
                
                # Show the exact command
                # Calculate relative path from build directory to TCL file
                try:
                    tcl_path_relative = project_file.vivado_project_tcl.relative_to(project_file.vivado_build_dir)
                except ValueError:
                    # TCL file is not under _vivado, use absolute path
                    tcl_path_relative = project_file.vivado_project_tcl.resolve()
                
                # Pass origin_dir and project_name as TCL arguments (handled by TCL script at lines 192-193)
                # The TCL script already supports --origin_dir and --project_name via -tclargs
                origin_dir_path = project_file._working_path.resolve()
                project_name = project_file.vivado_project_name
                
                # Create build directory if it doesn't exist
                c.run(f"mkdir -p {project_file.vivado_build_dir}")
                
                # Pass arguments directly to TCL script via -tclargs
                cmd = f"vivado -mode batch -source {tcl_path_relative} -notrace -tclargs --origin_dir {origin_dir_path} --project_name {project_name}"
                print(f"\n[i] Executing command:")
                print(f"    cd {project_file.vivado_build_dir}")
                print(f"    {cmd}\n")
                
                # Ask for final confirmation
                if not force:
                    response = input(f"Execute this command? (y/n) [y]: ").strip().lower()
                    if response == 'n' or response == 'no':
                        print("Operation cancelled.")
                        return
                
                # Execute the command from within _vivado directory
                try:
                    with c.cd(str(project_file.vivado_build_dir)):
                        result = c.run(cmd, pty=True, echo=True, warn=True)
                        
                        # Check if command failed
                        if result.exited != 0:
                            print(f"\n[!x!] Vivado command failed with exit code: {result.exited}")
                            if hasattr(result, 'stderr') and result.stderr:
                                print(f"[!x!] Error output:")
                                print(result.stderr)
                            if hasattr(result, 'stdout') and result.stdout:
                                # Look for error messages in stdout
                                error_lines = [line for line in result.stdout.split('\n') 
                                             if 'ERROR' in line.upper() or 'CRITICAL' in line.upper() or 'FATAL' in line.upper()]
                                if error_lines:
                                    print(f"[!x!] Error messages from Vivado:")
                                    for error_line in error_lines:
                                        print(f"    {error_line}")
                            print(f"\n[i] Please check the TCL script for errors:")
                            print(f"    {project_file.vivado_project_tcl}")
                            exit(1)
                except invoke.exceptions.UnexpectedExit as e:
                    print(f"\n[!x!] Failed to execute Vivado command")
                    print(f"[!x!] Error: {e}")
                    if hasattr(e, 'result') and hasattr(e.result, 'stderr') and e.result.stderr:
                        print(f"[!x!] Error output: {e.result.stderr}")
                    print(f"[i] Make sure Vivado is installed and in your PATH")
                    exit(1)
                except Exception as e:
                    print(f"\n[!x!] Unexpected error while executing Vivado command: {e}")
                    print(f"[i] Make sure Vivado is installed and in your PATH")
                    exit(1)
                
                print(f"[+] TCL script executed successfully")

            case VivadoStep.WRITE_TCL:
                print(f"[i] Exporting Vivado project to TCL: {project_file.vivado_project_name}")
                
                # Check if project exists
                if not project_file.vivado_project_xpr_path.exists():
                    print(f"[!x!] Project file not found: {project_file.vivado_project_xpr_path}")
                    print(f"[i] Please create the project first using --generate_prj_with_external_tcl")
                    exit(1)
                
                # Calculate relative path from _vivado directory to the output TCL file
                try:
                    output_tcl_relative = project_file.vivado_project_tcl.relative_to(project_file.vivado_build_dir)
                except ValueError:
                    # TCL file is not under _vivado, calculate path from working_path
                    output_tcl_relative = project_file.vivado_project_tcl.relative_to(project_file.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    output_tcl_relative = Path("..") / output_tcl_relative
                
                # Execute the command
                cmd = f"vivado -mode batch -source {SCRIPT_DIR}/write_project_tcl.tcl -notrace -tclargs {project_file.vivado_project_xpr_relative} {output_tcl_relative}"
                with c.cd(str(project_file.vivado_build_dir)):
                    c.run(cmd, pty=True, echo=True)
                
                print(f"[+] Project TCL exported successfully: {project_file.vivado_project_tcl}")
            
            case VivadoStep.CLEAN_LOGS:
                # Clean Vivado log files from current working directory
                _clean_logs_from_current_dir(verbose, force)
            
            case VivadoStep.FILE_REMOVE:
                print(f"[i] Removing file from Vivado project: {project_file.vivado_project_name}")
                
                # Check if file_path is provided
                if file_path is None:
                    print(f"[!x!] File path must be specified for file_remove")
                    print(f"[i] Usage: hdlforge vivado --step file_remove --file_path <file_path>")
                    exit(1)
                
                # Check if project exists
                if not project_file.vivado_project_xpr_path.exists():
                    print(f"[!x!] Project file not found: {project_file.vivado_project_xpr_path}")
                    print(f"[i] Please create the project first using --generate_prj_with_external_tcl")
                    exit(1)
                
                # Resolve file path (can be relative to project root or absolute)
                # Note: For file_remove, we don't check if file exists - it may have been moved/deleted
                file_path_resolved = Path(file_path)
                if not file_path_resolved.is_absolute():
                    # Try relative to project root
                    file_path_resolved = project_file.working_path / file_path_resolved
                
                # Calculate relative paths for TCL script
                try:
                    file_path_relative = file_path_resolved.relative_to(project_file.vivado_build_dir)
                except ValueError:
                    # File is not under _vivado, calculate from working_path
                    file_path_relative = file_path_resolved.relative_to(project_file.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    file_path_relative = Path("..") / file_path_relative
                
                try:
                    output_tcl_relative = project_file.vivado_project_tcl.relative_to(project_file.vivado_build_dir)
                except ValueError:
                    # TCL file is not under _vivado, calculate path from working_path
                    output_tcl_relative = project_file.vivado_project_tcl.relative_to(project_file.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    output_tcl_relative = Path("..") / output_tcl_relative
                
                # Execute the command
                cmd = f"vivado -mode batch -source {SCRIPT_DIR}/remove_file.tcl -notrace -tclargs {project_file.vivado_project_xpr_relative} {file_path_relative} {output_tcl_relative}"
                print(f"[i] Removing file: {file_path_resolved}")
                print(f"[i] Command: {cmd}")
                with c.cd(str(project_file.vivado_build_dir)):
                    c.run(cmd, pty=True, echo=True)
                
                print(f"[+] File removed and project TCL updated successfully: {project_file.vivado_project_tcl}")
            
            case VivadoStep.FILE_ADD:
                print(f"[i] Adding file to Vivado project: {project_file.vivado_project_name}")
                
                # Check if file_path is provided
                if file_path is None:
                    print(f"[!x!] File path must be specified for file_add")
                    print(f"[i] Usage: hdlforge vivado --step file_add --file_path <file_path>")
                    exit(1)
                
                # Check if project exists
                if not project_file.vivado_project_xpr_path.exists():
                    print(f"[!x!] Project file not found: {project_file.vivado_project_xpr_path}")
                    print(f"[i] Please create the project first using --generate_prj_with_external_tcl")
                    exit(1)
                
                # Resolve file path (can be relative to project root or absolute)
                file_path_resolved = Path(file_path)
                if not file_path_resolved.is_absolute():
                    # Try relative to project root
                    file_path_resolved = project_file.working_path / file_path_resolved
                
                # Check if file exists
                if not file_path_resolved.exists():
                    print(f"[!x!] File not found: {file_path_resolved}")
                    print(f"[i] Please provide a valid file path")
                    exit(1)
                
                # Calculate relative paths for TCL script
                try:
                    file_path_relative = file_path_resolved.relative_to(project_file.vivado_build_dir)
                except ValueError:
                    # File is not under _vivado, calculate from working_path
                    file_path_relative = file_path_resolved.relative_to(project_file.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    file_path_relative = Path("..") / file_path_relative
                
                try:
                    output_tcl_relative = project_file.vivado_project_tcl.relative_to(project_file.vivado_build_dir)
                except ValueError:
                    # TCL file is not under _vivado, calculate path from working_path
                    output_tcl_relative = project_file.vivado_project_tcl.relative_to(project_file.working_path)
                    # Since we run from _vivado, we need to go up to project root
                    output_tcl_relative = Path("..") / output_tcl_relative
                
                # Execute the command
                cmd = f"vivado -mode batch -source {SCRIPT_DIR}/add_file.tcl -notrace -tclargs {project_file.vivado_project_xpr_relative} {file_path_relative} {output_tcl_relative}"
                print(f"[i] Adding file: {file_path_resolved}")
                print(f"[i] Command: {cmd}")
                with c.cd(str(project_file.vivado_build_dir)):
                    c.run(cmd, pty=True, echo=True)
                
                print(f"[+] File added and project TCL updated successfully: {project_file.vivado_project_tcl}")
            
            case _:
                pass
