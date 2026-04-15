#!/usr/bin/env python3
"""
Verilator task handlers for HDLForge
"""

import os
import re
import sys
import warnings
from pathlib import Path
from typing import List, Dict, Any


def _verilator_run_dir_name(SimTargetName: str, extra_env: Dict[str, Any]) -> str:
    """Unique cocotb test_dir under build_dir for feature shards and config_test suffixes."""
    testcase = extra_env.get("TESTCASE", "").strip()
    # Single integration sim target (full_sim): name dirs like trigger_test_<feature>, not full_sim_<feature>.
    sim_base = testcase if SimTargetName == "full_sim" and testcase else SimTargetName
    feature_tag = extra_env.get("TRIGGER_TEST_FEATURE", "").strip()
    if not feature_tag:
        feature_tag = extra_env.get("CONFIG_TEST_FEATURE", "").strip()
    if not feature_tag:
        feature_tag = extra_env.get("NETWORK_MONITOR_FEATURE", "").strip()
    suffix = extra_env.get("CONFIG_TEST_SUFFIX", "").strip()
    if not suffix:
        suffix = extra_env.get("NETWORK_MONITOR_SUFFIX", "").strip()
    safe_suffix = re.sub(r"[^0-9A-Za-z_]+", "_", suffix) if suffix else ""
    base = f"{sim_base}_{feature_tag}" if feature_tag else sim_base
    if safe_suffix:
        return f"{base}_{safe_suffix}"
    return base


def _validate_cocotb_results(results_xml_path: Path, requested_testcase: str | None = None) -> None:
    """Fail the run if cocotb did not execute the requested testcase cleanly."""
    import xml.etree.ElementTree as ET

    if not results_xml_path.is_file():
        raise RuntimeError(f"results.xml not found: {results_xml_path}")

    root = ET.parse(results_xml_path).getroot()
    testcase_names = [tc.get("name", "") for tc in root.iter("testcase")]
    if not testcase_names:
        raise RuntimeError(f"No testcases were recorded in {results_xml_path}")

    if requested_testcase and requested_testcase not in testcase_names:
        raise RuntimeError(
            f"Requested testcase '{requested_testcase}' was not executed. "
            f"Recorded testcases: {testcase_names}"
        )

    failures = []
    for tc in root.iter("testcase"):
        failure = tc.find("failure")
        if failure is not None:
            failures.append(tc.get("name", "?"))

    if failures:
        raise RuntimeError(
            f"results.xml reports failure in testcase(s): {', '.join(failures)}"
        )

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
    if test_name is None and extra_env.get("TESTCASE"):
        test_name = str(extra_env["TESTCASE"]).strip() or None
    run_dir_name = _verilator_run_dir_name(SimTargetName, extra_env)

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
                    for _ in verilator_settings.get("includes_paths", []):
                        expanded = os.path.expandvars(str(_))
                        ip = Path(expanded)
                        if not ip.is_absolute():
                            ip = Path(working_path) / ip
                        includes_paths_list.append(ip.resolve())
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
                        if SimTargetName == "full_sim" and test_name is None:
                            exit(
                                "[!x!]  SimTargetName 'full_sim' requires TESTCASE in --extra-env "
                                '(e.g. --extra-env "TESTCASE=arp_test").'
                            )
                        # Clean test directory before simulation to avoid stale logs
                        test_output_dir = build_dir / run_dir_name
                        if test_output_dir.exists():
                            import shutil
                            print(f"[i] Cleaning test directory: {test_output_dir}", flush=True)
                            try:
                                # Remove all contents but keep the directory
                                for item in test_output_dir.iterdir():
                                    if item.is_dir():
                                        shutil.rmtree(item)
                                    else:
                                        item.unlink()
                                print(f"[i] Test directory cleaned", flush=True)
                            except Exception as e:
                                print(f"[!x!] Warning: Failed to clean test directory: {e}", flush=True)
                        
                        print(f"[i] Verilator simulation started:", flush=True)
                        print(f"\n================start of verilator output : sim================", flush=True)  
                        runner.test(
                            hdl_toplevel=f"{top_module}",
                            test_module=f"{python_file_path.stem}",  
                            testcase=test_name,          
                            build_dir=f"{build_dir}",   
                            extra_env=extra_env,
                            test_dir=f"{build_dir}/{run_dir_name}",      # Directory for test outputs
                            waves=True                  # enables dump.vcd
                        )
                        print(f"================end of verilator output : sim================\n", flush=True)
                        print(f"[i] Verilator simulation completed", flush=True)
                        
                        # Check for VCD file generation
                        vcd_file_path = build_dir / run_dir_name / "dump.vcd"
                        
                        if vcd_file_path.exists():
                            print(f"[i] Found VCD file: {vcd_file_path}")
                        else:
                            print(f"[!x!] VCD file not found: {vcd_file_path}")
                            print(f"[i] Simulation may not have generated VCD file (waves=True required)")
                        
                        # List all artifacts and logs that will be generated
                        test_output_dir = build_dir / run_dir_name
                        print(f"\n[i] Simulation artifacts location: {test_output_dir}")
                        print(f"[i] Generated files:")
                        print(f"    • {test_output_dir}/dump.vcd                    - Waveform data (VCD format)")
                        print(f"    • {test_output_dir}/results.xml                  - Cocotb test results (XML)")
                        print(f"    • {test_output_dir}/cocotb_verilator_output.log - Cocotb simulation log")
                        print(f"    • {test_output_dir}/{run_dir_name}_results.md  - Test report (if generated by test)")
                        print(f"    • {test_output_dir}/{run_dir_name}_packets.pcap - Packet capture (if generated by test)")
                        print(f"    • {test_output_dir}/{run_dir_name}_tshark_output.txt - Tshark validation (if generated by test)")
                        print(f"    • {test_output_dir}/captures/                    - Per-interface captures (if generated by test)")
                        print("", flush=True)

                        results_xml_path = test_output_dir / "results.xml"
                        _validate_cocotb_results(results_xml_path, test_name)

                        # Post-sim: generate report + collect artifacts.
                        # The shared integration main_test_bench already collects artifacts
                        # itself so the same run can be reused by HW-oriented helpers too.
                        if python_file_path.name == "main_test_bench.py":
                            print(
                                "[i] Skipping post_sim_collect; main_test_bench.py handles artifact collection",
                                flush=True,
                            )
                        else:
                            # TEST_PATH = directory containing the test script
                            test_path = str(python_file_path.parent.resolve())
                            try:
                                from TEST_UTILS.report_utils import post_sim_collect
                                dest = post_sim_collect(
                                    run_dir=str(test_output_dir),
                                    test_path=test_path,
                                    test_name=run_dir_name,
                                )
                                print(f"[i] Artifacts collected to: {dest}", flush=True)
                            except ImportError:
                                pass
                            except Exception as e:
                                print(f"[!] Artifact collection failed: {e}", flush=True)
                    else:
                        print(f"[i] Skipping Verilator simulation", flush=True)
                        
                except Exception as e:
                    print("\n[!x!]  Verilator build/simulation failed!", flush=True)
                    print(f"Error: {e}", flush=True)
                    raise



