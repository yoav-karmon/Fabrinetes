#!/usr/bin/env python3
"""
Verilator task handlers for HDLForge
"""

import os
import re
import shlex
import subprocess
import sys
import warnings
from pathlib import Path
from typing import List, Dict, Any


VERILATOR_INHERITED_EXTRA_ENV_KEYS = (
    "TESTCASE",
    "TRIGGER_TEST_FEATURE",
    "CONFIG_TEST_FEATURE",
    "NETWORK_MONITOR_FEATURE",
    "CONFIG_TEST_SUFFIX",
    "NETWORK_MONITOR_SUFFIX",
    "TARGET_CORE",
    "CONFIG_TEST_CORE_ID",
    "CONFIG_TEST_SEGMENT",
    "CONFIG_TEST_COUNT",
    "CONFIG_TEST_WRITE",
    "CONFIG_TEST_ADDR",
    "CONFIG_TEST_REG_ADDR",
    "CONFIG_TEST_PRINT_TX_HEX",
    "CONFIG_TEST_PRINT_RX_HEX",
    "CONFIG_OVERFLOW_FIFO_DEPTH",
    "COCOTB_TESTNAME",
    "MDP3_SBE_PCAP_FILE",
    "MDP3_SBE_PCAP_PACKET",
    "MDP3_SBE_RANDOM_MODE",
    "MDP3_SBE_RANDOM_SEED",
)


def _parse_extra_env(extra_env) -> Dict[str, str]:
    parsed = {}
    if extra_env:
        for item in extra_env.split(","):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            parsed[key] = value

    for key in VERILATOR_INHERITED_EXTRA_ENV_KEYS:
        if key not in parsed and os.environ.get(key) is not None:
            parsed[key] = os.environ[key]

    return parsed


def _split_cli_flags(flags) -> List[str]:
    if isinstance(flags, str):
        raw_flags = [flags]
    elif flags is None:
        raw_flags = []
    else:
        raw_flags = list(flags)

    parsed_flags = []
    for flag_group in raw_flags:
        if flag_group is None:
            continue
        parsed_flags.extend(shlex.split(str(flag_group)))
    return parsed_flags


def _resolve_include_paths(includes_paths, working_path: Path) -> List[Path]:
    includes_paths_list = []
    for include_path in includes_paths:
        expanded = os.path.expandvars(str(include_path))
        resolved_path = Path(expanded).expanduser()
        if not resolved_path.is_absolute():
            resolved_path = working_path / resolved_path
        includes_paths_list.append(resolved_path.resolve())
    return includes_paths_list


def _resolve_verilator_source_files(sources_dict_list) -> List[Path]:
    source_files = []
    for file_dict in sources_dict_list:
        source_files.append(Path(os.path.expandvars(str(file_dict["file"]))).expanduser().resolve())
    return source_files


def _resolve_lint_files(lint_file, working_path: Path) -> List[Path]:
    if isinstance(lint_file, str):
        raw_files = [lint_file]
    elif lint_file is None:
        raw_files = []
    else:
        raw_files = list(lint_file)

    lint_files = []
    for raw_file in raw_files:
        for file_part in str(raw_file).split(","):
            file_part = file_part.strip()
            if not file_part:
                continue
            expanded = os.path.expandvars(file_part)
            resolved_file = Path(expanded).expanduser()
            if not resolved_file.is_absolute():
                resolved_file = working_path / resolved_file
            resolved_file = resolved_file.resolve()
            if not resolved_file.is_file():
                raise FileNotFoundError(
                    f"Verilator lint file not found: {resolved_file}. "
                    f"Relative --lint-file paths are project-relative to {working_path}."
                )
            lint_files.append(resolved_file)
    return lint_files


def _dedupe_paths(paths: List[Path]) -> List[Path]:
    deduped_paths = []
    seen_paths = set()
    for path in paths:
        resolved_path = path.resolve()
        if resolved_path in seen_paths:
            continue
        seen_paths.add(resolved_path)
        deduped_paths.append(resolved_path)
    return deduped_paths


def _resolve_project_lint_sources(selected_files: List[Path], source_files: List[Path]) -> List[Path]:
    if not selected_files:
        return []

    source_indices = {source_file.resolve(): index for index, source_file in enumerate(source_files)}
    missing_files = [selected_file for selected_file in selected_files if selected_file.resolve() not in source_indices]
    if missing_files:
        missing_text = ", ".join(str(missing_file) for missing_file in missing_files)
        raise FileNotFoundError(
            f"Verilator lint --file path(s) are not in the project source list: {missing_text}. "
            "Use --lint-file for raw selected-file lint outside the ordered project source list."
        )

    package_sources = [
        source_file
        for source_file in source_files
        if source_file.name.endswith("_pkg.sv") or "PACKAGES" in source_file.parts
    ]
    return _dedupe_paths([*package_sources, *selected_files])


def _resolve_project_lint_library_files(source_files: List[Path], lint_sources: List[Path]) -> List[Path]:
    lint_source_set = {lint_source.resolve() for lint_source in lint_sources}
    return _dedupe_paths([
        source_file
        for source_file in source_files
        if source_file.resolve() not in lint_source_set
    ])


def _werror_warning_codes(cli_flags: List[str]) -> List[str]:
    warning_codes = []
    for cli_flag in cli_flags:
        match = re.match(r"^-Werror-([0-9A-Za-z_-]+)$", cli_flag)
        if match:
            warning_codes.append(match.group(1))
    return warning_codes


def _demote_werror_flags(cli_flags: List[str], warning_codes: List[str]) -> List[str]:
    warning_code_set = set(warning_codes)
    demoted_flags = []
    for cli_flag in cli_flags:
        match = re.match(r"^-Werror-([0-9A-Za-z_-]+)$", cli_flag)
        if match and match.group(1) in warning_code_set:
            warning_flag = f"-Wwarn-{match.group(1)}"
            if warning_flag not in demoted_flags:
                demoted_flags.append(warning_flag)
            continue
        demoted_flags.append(cli_flag)
    return demoted_flags


def _selected_file_warning_lines(output: str, selected_files: List[Path], warning_codes: List[str]) -> List[str]:
    selected_file_set = {selected_file.resolve() for selected_file in selected_files}
    warning_code_set = set(warning_codes)
    diagnostic_pattern = re.compile(r"^%(?:Warning|Error)-([^:]+): ([^:]+):[0-9]+:[0-9]+:")
    scoped_lines = []

    for line in output.splitlines():
        match = diagnostic_pattern.match(line)
        if not match or match.group(1) not in warning_code_set:
            continue
        diagnostic_path = Path(match.group(2)).expanduser().resolve()
        if diagnostic_path in selected_file_set:
            scoped_lines.append(line)

    return scoped_lines


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
    sim_targets_dict = {}
    sim_targets = verilator_settings.get("sim_targets", [])
    if isinstance(sim_targets, dict):
        for target_name, target in sim_targets.items():
            if isinstance(target, dict):
                target = dict(target)
                target.setdefault("name", target_name)
                sim_targets_dict[target_name] = target
    else:
        for target in sim_targets:
            if isinstance(target, dict) and "name" in target:
                sim_targets_dict[target["name"]] = target
    
    if SimTargetName is None:
        exit(f"[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
    elif SimTargetName not in sim_targets_dict:
        print(f"Available SimTargetNames: {', '.join(sim_targets_dict.keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")

    return sim_targets_dict[SimTargetName]


def Verilator(c, project, step=None, clean=False, SimTargetName=None, flags=None, extra_env=None, lint_file=None, project_lint_file=None):
    # Import shared utilities
    from environment import capture_environment_variables
    from display import print_task_args
    
    # Capture environment variables set by update_repo_path
    capture_environment_variables(c)
    
    extra_env = _parse_extra_env(extra_env)
    tool_name = "verilator"

    ALLOWED_STEPS = {"step": ["sim", "build", "lint"], "extra_env": ["DEBUG=1"]}
    cli_flags = _split_cli_flags(flags)

    if isinstance(step, str):  # Convert single input to list
        step = [step]
    elif step is None:
        step = []
    if not step and (lint_file or project_lint_file):
        step = ["lint"]
    
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

    targetless_file_lint = (
        SimTargetName is None
        and step
        and all(requested_step == "lint" for requested_step in step)
        and bool(lint_file or project_lint_file)
    )

    if SimTargetName is None and not targetless_file_lint:
        print(
            "\n[!x!]  SimTargetName must be specified for build/sim or full-target lint. "
            "For file-only lint, use --file <path> or --lint-file <path>."
        )
        return
    
    build_dir = project_file.verilator_build_dir
    SOURCES_DICT_LIST = project_file.get_verilator_sources()

    if targetless_file_lint:
        top_module = None
        build_args = []
        lint_args = []
        defines = {}
        parameters = {}
        python_file_path = None
        test_name = None
        run_dir_name = "lint"
    else:
        # Verify the parameters and get the target data
        SimTarget = project_file.get_sim_target(SimTargetName)
        if SimTarget is None:
            print(f"\n[!x!]  SimTargetName '{SimTargetName}' not found in verilator.config['sim_targets']")
            print(f"Available SimTargetNames: {', '.join(available_sim_targets)}")
            exit(1)

        top_module = SimTarget["top_module"]
        build_args = _split_cli_flags(SimTarget.get("build_args", []))
        lint_args = _split_cli_flags(SimTarget.get("lint_args", []))
        defines = SimTarget.get("defines", {})
        parameters = SimTarget.get("parameters", {})
        python_file_path = Path(working_path) / SimTarget["python_file"]
        test_name = SimTarget.get("test_name", None)
        if test_name is None and extra_env.get("TESTCASE"):
            test_name = str(extra_env["TESTCASE"]).strip() or None
        run_dir_name = _verilator_run_dir_name(SimTargetName, extra_env)
    
    print(f"\n[~] processing steps {step}", flush=True)
    sys.stdout.flush()
    for s in step:
        match (s):
            case "lint":
                try:
                    veruilator_sources_file = _resolve_verilator_source_files(SOURCES_DICT_LIST)
                    selected_lint_files = _resolve_lint_files(lint_file, working_path)
                    project_selected_lint_files = _resolve_lint_files(project_lint_file, working_path)
                    project_lint_sources = _resolve_project_lint_sources(
                        project_selected_lint_files,
                        veruilator_sources_file,
                    )
                    lint_sources = _dedupe_paths([*project_lint_sources, *selected_lint_files])
                    if not lint_sources:
                        lint_sources = veruilator_sources_file
                    project_lint_library_files = (
                        _resolve_project_lint_library_files(veruilator_sources_file, lint_sources)
                        if project_selected_lint_files
                        else []
                    )
                    includes_paths_list = _resolve_include_paths(
                        verilator_settings.get("includes_paths", []),
                        working_path,
                    )
                    selected_warning_error_codes = (
                        _werror_warning_codes(cli_flags)
                        if targetless_file_lint and lint_sources
                        else []
                    )
                    active_cli_flags = (
                        _demote_werror_flags(cli_flags, selected_warning_error_codes)
                        if selected_warning_error_codes
                        else cli_flags
                    )

                    command = ["verilator", "--lint-only"]
                    if not selected_lint_files and not project_selected_lint_files and top_module is not None:
                        command.extend(["--top-module", str(top_module)])
                    command.extend(f"-I{include_path}" for include_path in includes_paths_list)
                    for library_file in project_lint_library_files:
                        command.extend(["-v", str(library_file)])
                    command.extend(build_args)
                    command.extend(lint_args)
                    command.extend(active_cli_flags)
                    command.extend(str(source_file) for source_file in lint_sources)

                    print(f"[i] Verilator step: {s}", flush=True)
                    print(f"[i] Linting {len(lint_sources)} source file(s)", flush=True)
                    if project_selected_lint_files:
                        print("[i] Project-aware selected lint file(s):", flush=True)
                        for selected_file in project_selected_lint_files:
                            print(f"    {selected_file}", flush=True)
                        print(f"[i] Included project package sources: {len(project_lint_sources) - len(project_selected_lint_files)}", flush=True)
                        print(f"[i] Added project source library files: {len(project_lint_library_files)}", flush=True)
                    if selected_lint_files:
                        print("[i] Raw selected lint file(s):", flush=True)
                        for selected_file in selected_lint_files:
                            print(f"    {selected_file}", flush=True)
                    if selected_warning_error_codes:
                        print(
                            "[i] Selected-file warning failures: "
                            f"{', '.join(selected_warning_error_codes)}",
                            flush=True,
                        )
                    print(f"[i] Verilator lint command: {shlex.join(command)}", flush=True)
                    print(f"\n================start of verilator output : lint================", flush=True)
                    if selected_warning_error_codes:
                        completed_lint = subprocess.run(
                            command,
                            cwd=working_path,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            check=False,
                        )
                        print(completed_lint.stdout, end="", flush=True)
                        selected_warning_lines = _selected_file_warning_lines(
                            completed_lint.stdout,
                            [*project_selected_lint_files, *selected_lint_files],
                            selected_warning_error_codes,
                        )
                        if selected_warning_lines:
                            raise RuntimeError(
                                "Selected file warning(s) matched fatal lint rule:\n"
                                + "\n".join(selected_warning_lines)
                            )
                        completed_lint.check_returncode()
                    else:
                        subprocess.run(command, cwd=working_path, check=True)
                    print(f"================end of verilator output : lint================\n", flush=True)
                    print("[+] Verilator lint completed", flush=True)
                except Exception as e:
                    print("\n[!x!]  Verilator lint failed!", flush=True)
                    print(f"Error: {e}", flush=True)
                    raise
            case "build" | "sim":
                try:
                    print(f"[i] Verilator step: {s}", flush=True)
                    print(f"[i] Compiling Verilator sources into: {build_dir}", flush=True)
                    veruilator_sources_file = _resolve_verilator_source_files(SOURCES_DICT_LIST)
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
                    includes_paths_list = _resolve_include_paths(
                        verilator_settings.get("includes_paths", []),
                        working_path,
                    )
                    combined_build_args = [*build_args, *cli_flags]
                    
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
                                "[!x!]  SimTargetName 'full_sim' requires TESTCASE "
                                'through --env-var \'{"TESTCASE":"arp_test"}\' '
                                'or --extra-env "TESTCASE=arp_test".'
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
            case _:
                print(f"\n[!x!] Unsupported Verilator step: {s}", flush=True)
                print("[i] Supported steps: build, sim, lint", flush=True)
                exit(1)
