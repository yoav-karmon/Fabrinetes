#!/usr/bin/env python3
"""
Verilator task handlers for HDLForge
"""

import os
import sys
import warnings
from pathlib import Path
from typing import List, Dict, Any

from project_file import ProjectFile


def verify_sim_target(SimTargetName, verilator_settings):
    # Convert sim_targets list to dictionary using 'name' as key
    sim_targets_dict = {}
    for target in verilator_settings['sim_targets']:
        sim_targets_dict[target['name']] = target
    
    if SimTargetName is None:
        exit(f"[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
    elif SimTargetName not in sim_targets_dict:
        print(f"Available SimTargetNames: {', '.join(sim_targets_dict.keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")

    return sim_targets_dict[SimTargetName]


def Verilator(c, project, step=None, clean=False, SimTargetName=None, flags=None, extra_env=None):
    # Import shared utilities
    from environment import capture_environment_variables
    from display import print_task_args
    from path_utils import add_python_paths_from_list
    
    # Capture environment variables set by update_repo_path
    capture_environment_variables(c)
    
    extra_env = dict(item.split('=') for item in extra_env.split(',') if '=' in item) if extra_env else {}
    tool_name = "verilator"

    ALLOWED_STEPS = {"step": ["sim", "build"], "extra_env": ["DEBUG=1"]}
    
    if isinstance(flags, str):  # Convert single input to list
        flags = [flags]
    elif flags is None:
        flags = []

    if isinstance(step, str):  # Convert single input to list
        step = [step]
    elif step is None:
        step = []
    
    REPO_TOP = Path(os.environ["REPO_TOP"])  # Fail fast if REPO_TOP is not set
    
    # Load project using ProjectFile (single source of truth)
    project_file = ProjectFile(project)
    project_file.verify_repo_path()
    
    # Get project information from ProjectFile (all values computed in __init__)
    working_path = project_file._working_path
    project_data = project_file._project_data
    verilator_settings = project_file.verilator_config
    
    # Extract available SimTargetNames for display
    available_sim_targets = [target['name'] for target in project_file.verilator_sim_targets]
    ALLOWED_STEPS["SimTargetName"] = available_sim_targets
    
    print_task_args(locals(), str(REPO_TOP), ALLOWED_STEPS)
    
    # Check if SimTargetName is specified before proceeding
    if SimTargetName is None:
        print(f"\n[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
        return
    
    build_dir = project_file.verilator_build_dir
    SOURCES_DICT_LIST = project_file.get_verilator_sources()
      
    
    # Verify the parameters and get the target data
    SimTarget = project_file.get_sim_target(SimTargetName)
    if SimTarget is None:
        print(f"\n[!x!]  SimTargetName '{SimTargetName}' not found in verilator.config['sim_targets']")
        print(f"Available SimTargetNames: {', '.join(available_sim_targets)}")
        exit(1)    
    
    top_module = SimTarget["top_module"]
    build_args = SimTarget.get("build_args", [])
    defines = SimTarget.get("defines", {})
    parameters = SimTarget.get("parameters", {})
    python_file_path = Path(working_path) / SimTarget["python_file"] 
    test_name = SimTarget.get("test_name", None)

    PYTHONPATH = SimTarget.get("PYTHONPATH", [])
    add_python_paths_from_list(PYTHONPATH, working_path)
  
    
    print(f"\n[~] processing steps {step}", flush=True)
    sys.stdout.flush()
    for s in step:
        match (s):
            case "build" | "sim":
                try:
                    print(f"[i] Verilator step: {s}", flush=True)
                    print(f"[i] Compiling Verilator sources into: {build_dir}", flush=True)
                    veruilator_sources_file = []
                    for file_dict in SOURCES_DICT_LIST:
                        veruilator_sources_file.append(Path(os.path.expandvars(str(file_dict["file"]))).resolve())
                    sys.stdout.flush()
                    print(f"\n================start of verilator output : build================", flush=True)
                    # Suppress the specific message before importing cocotb.runner
                    warnings.filterwarnings(
                        "ignore",
                        message="Python runners and associated APIs are an experimental feature and subject to change.",
                        category=UserWarning,
                    )                
                    from cocotb.runner import get_runner

                    runner = get_runner("verilator")
                    defines = {}
                    parameters = {}
                    log_file = None
                    includes_paths_list = []
                    for _ in verilator_settings["includes_paths"]:
                        includes_paths_list.append(Path(os.path.expandvars(str(_))).resolve())
                    # Use only the build_args from project configuration
                    combined_build_args = build_args
                    
                    runner.build(
                            verilog_sources=veruilator_sources_file,
                            hdl_toplevel=f"{top_module}",
                            waves=True,
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
                    print(f"================end of verilator output : build================\n", flush=True)
                    print(f"[+] Verilator build completed", flush=True)
                    
                    if s == "sim":  
                        print(f"[i] Verilator simulation started:", flush=True)
                        print(f"\n================start of verilator output : sim================", flush=True)  
                        runner.test(
                            hdl_toplevel=f"{top_module}",
                            test_module=f"{python_file_path.stem}",  
                            testcase=test_name,          
                            build_dir=f"{build_dir}",   
                            extra_env=extra_env,
                            test_dir=f"{build_dir}/{SimTargetName}",      # Directory for test outputs
                            waves=True                  # enables dump.vcd
                        )
                        print(f"================end of verilator output : sim================\n", flush=True)
                        print(f"[i] Verilator simulation completed", flush=True)
                        
                        # Check for VCD file generation
                        vcd_file_path = build_dir / SimTargetName / "dump.vcd"
                        
                        if vcd_file_path.exists():
                            print(f"[i] Found VCD file: {vcd_file_path}")
                        else:
                            print(f"[!x!] VCD file not found: {vcd_file_path}")
                            print(f"[i] Simulation may not have generated VCD file (waves=True required)")
                    else:
                        print(f"[i] Skipping Verilator simulation", flush=True)
                        
                except Exception as e:
                    print("\n[!x!]  Verilator build/simulation failed!", flush=True)
                    print(f"Error: {e}", flush=True)

