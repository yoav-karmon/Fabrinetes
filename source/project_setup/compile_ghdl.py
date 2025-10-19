#!/usr/bin/env python
"""
compile_ghdl.py

A tiny helper that
1. normalises the three paths you pass in,
2. recreates the OUT_DIR if needed, and
3. launches the same Docker command you had in Bash.

Usage:
    ./compile_ghdl.py <source_list.txt> <output_dir> <REPO_TOP>
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple
from enum import Enum
from vunit import VUnit 
import tomllib

def run_ghdl_on_file_list(repo_top: str,
                          file_of_sources: str,
                          ghdl_flags: list[str],
                          compile_flag: list[str]) -> None:
    """
    Read all source filenames from `file_of_sources`, resolve them,
    then invoke ghdl-gcc -a once on the entire list.
    """
    # Resolve build path and sources file
    sources_list_path = Path(repo_top) / file_of_sources
    if not sources_list_path.exists():
        sys.exit(f"Source list not found: {sources_list_path}")

    # Collect all source file paths
    sources = []
    with sources_list_path.open() as f:
        for line in f:
            src = line.strip()
            if not src:
                continue
            src_path = Path(repo_top, src).resolve()
            if not src_path.exists():
                sys.exit(f"Source file not found: {src_path}")
            sources.append(str(src_path))

    # Build the full GHDL command
    flags = ghdl_flags + compile_flag
    ghdl_cmd = ["ghdl-gcc", "-a", *flags, *sources]

    # Quote it and pipe through tee with pipefail enabled
    cmd_str = " ".join(shlex.quote(arg) for arg in ghdl_cmd)
    bash_invocation = f"bash -o pipefail -c {shlex.quote(cmd_str + ' | tee ghdl.compile.log')}"

    print(f"Running: {bash_invocation}")
    try:
        subprocess.run(
            bash_invocation,
            shell=True,
            check=True,
            executable="/bin/bash"
        )
    except subprocess.CalledProcessError as e:
        print(f"Error during compilation (exit {e.returncode})")
        sys.exit(e.returncode)
                        
                        

def run_vunit(args) -> None:
    os.environ["VUNIT_GHDL_PATH"] = "/mnt/tools/ghdl-llvm-5.1.1-ubuntu24.04-x86_64/bin" # path to the simulator executable
    repo_top=args.repo_top
    
    print(f"ℹ️  repo_top: {repo_top}")
    project_json_full_path = os.path.join(repo_top, args.project_json)
    project_dir = os.path.dirname(project_json_full_path)
    with open(project_json_full_path, "rb") as f:
        project_data = tomllib.load(f)

    settings        = project_data["settings"]
    project_path    = settings["project_path"]
    project_name    = settings["project_name"]

    ghdl_settings   = project_data["ghdl_settings"] 
    build_dir       = ghdl_settings["build_dir"]
    lib_list        = ghdl_settings["lib_list"]


    vunit_args = []
    vu = VUnit.from_argv(argv=vunit_args, compile_builtins=False)  
    
    

    lib_match= False
    for lib_name,lib_info  in lib_list.items():
        if(args.lib==None or args.lib==lib_name):
            lib_match = True
            external_libraries = lib_info["external_libraries"]
            ######### processing external_libs ################
            print(f"ℹ️  processing external_libs")
            for external_lib_name, external_lib in external_libraries.items():
                name =external_lib_name
                path = external_lib
                if name == None or path == None:
                    continue
                path_realpath = os.path.realpath(os.path.join(repo_top, path))
                if( not os.path.isdir(path_realpath)): 
                    raise NotADirectoryError(f"external library path '{path_realpath}' does not exist or is not a directory")
                
                if(args.v):
                    print(f"ℹ️  Adding external library: {name} at {path_realpath}")
                vu.add_external_library(name, path_realpath)
            print("✅ External libraries added successfully.")
            ######### end of processing external_libs ##########

            ######### Creating library ################
            print(f"ℹ️  Creating VUnit library {lib_name}")
            vunit_lib = vu.add_library(lib_name)
            sources_file = lib_info["sources_file"]
            sources_file = os.path.join(project_dir, sources_file)
            with open(sources_file) as f:
                for line in f:
                    vhdl_file_abs_path = os.path.abspath(os.path.join(repo_top, line.strip()))
                    if(args.v):
                        print(f"ℹ️ Adding source file: {vhdl_file_abs_path}")
                    if not os.path.isfile(vhdl_file_abs_path):
                        print(f"❌ Source file '{vhdl_file_abs_path}' does not exist.")
                        exit(1) 
                    vunit_lib.add_source_file(vhdl_file_abs_path)

            print(f"✅  Library {lib_name} created with sources from {sources_file}")
            vunit_lib_ghdl_flags = lib_info["ghdl_flags"].copy()  # Copy to avoid modifying the original list 
            if lib_name == "" : raise ValueError("lib_name is empty in project JSON")
            if not os.path.isfile(sources_file): raise FileNotFoundError(f"list_of_sources file '{sources_file}' does not exist.")
            if vunit_lib_ghdl_flags == "" :  raise ValueError("ghdl_flags is empty in project JSON")
            
            ######### end Adding library ################
        
            vu.set_compile_option("ghdl.a_flags",vunit_lib_ghdl_flags)  # type: ignore


    if( not lib_match):
        print(f"❌ No library found matching '{args.lib}'")
        exit(1)

    vu.main()
    
    print("✅ VUnit compilation completed successfully.")
    
    cocotb_target   =  ghdl_settings["cocotb_targets"]["cocotb_main"]
    lib_name_to_sim =  cocotb_target["lib_name"]
    ghdl_flags_to_sim      =  ghdl_settings["lib_list"][lib_name_to_sim]["ghdl_flags"] 
    print(f"ℹ️  ghdl_settings:{ghdl_settings['lib_list'][lib_name_to_sim]}")
    generics_to_sim = cocotb_target["generics"]
    top_module_to_sim   =  cocotb_target["top_module"]

    if args.cmd == "sim":
        print(f"ℹ️  sim target: '{top_module_to_sim}' in library: '{lib_name}' with top module: '{top_module_to_sim}'")
        
        vpi_path = "/mnt/userdata/miniconda3/envs/devtools/lib/python3.11/site-packages/cocotb/libs/libcocotbvpi_ghdl.so"
        test_path = ???

        print(*ghdl_flags_to_sim)
        cmd = ["ghdl", "-e", *ghdl_flags_to_sim, f"--work={lib_name}",  top_module_to_sim]
        print("ℹ️  Running:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        env = os.environ.copy()
        env.update({
            "TOPLEVEL": "???",
            "TOPLEVEL_LANG": "vhdl",
            "MODULE": "?", 
            "PYTHONPATH": test_path,
            "COCOTB_SIM": "ghdl",
            "CONFIG_FILE": "?.json",  
            "COCOTB_FAIL_ON_EXCEPTION": "1",
            # Optional: logging level
            "COCOTB_LOG_LEVEL": "INFO",
            "LD_LIBRARY_PATH": "/mnt/userdata/miniconda3/envs/devtools/lib:" + env.get("LD_LIBRARY_PATH", "")

        })
        cmd = ["ghdl", "-r", *ghdl_flags_to_sim, f"--work={lib_name}",  top_module_to_sim,  *generics_to_sim, f"--vpi={vpi_path}"]
        print("ℹ️  Running:", " ".join(cmd))
        subprocess.run(cmd, check=True,env=env)
        print(f"✅ sim of {top_module_to_sim} finished.")


     
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile and run VUnit with GHDL.")
    parser.add_argument("--repo_top", help="Top-level repository path")
    parser.add_argument("--project_json", help="Path to project JSON file (relative to repo_top)")
    parser.add_argument("--top_level",  dest="toplevel_hdl",help="Top-level entity name for VUnit")
    parser.add_argument("--module",     dest="python_test_file",required=False, default=None,help="Top-level entity name for VUnit")
    parser.add_argument("--test",       dest="test_name",help="Top-level entity name for VUnit")
    parser.add_argument("--lib",        dest="lib",default=None,required=False, help="Library name")
    parser.add_argument("--i",          dest="interactive",  action="store_true",required=False, help="Interactive mode")
    parser.add_argument("--c",          dest="cmd", help="compile or elaborate", choices=["sim", "compile"], default="compile")
    parser.add_argument("--v",          dest="v", help="Verbose mode", action="store_true", default=False)
    args = parser.parse_args()

    run_vunit(args)