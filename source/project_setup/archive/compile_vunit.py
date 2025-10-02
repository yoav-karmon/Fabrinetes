#!/usr/bin/env python3

import os
import subprocess
import sys
import argparse
from pathlib import Path
from vunit import VUnit
import load_config



def run_cmd(cmd):
    """Run a command, print its stdout/stderr, and exit on error."""
    print(f"+ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: {e}")


def compile_vhdl(libname: str, workdir: Path, sources: list[Path]):
    UNISIM_GHDL="/home/admin/_repo/vivado/unisim/_ghdl"

    cmd = [
        "ghdl", "-a",
        "--std=08",
        "-fsynopsys",
        f"-P{UNISIM_GHDL}",
        f"--workdir={workdir}",
        "-Wno-library",   
        "-Whide",
        "-P/usr/lib/ghdl/gcc/vhdl/ieee/v08/",
        "-P/usr/lib/ghdl/gcc/vhdl/std/v08/"
    ] + [str(s) for s in sources]
    run_cmd(cmd)


def elaborate(libname: str, workdir: Path, top: str):
    """Elaborate the top-level entity into an executable."""
    cmd = [
        "ghdl", "-e",
        "--std=08",
        f"--workdir={workdir}",
        "-Wno-library",    
        f"--work={libname}",
        top
    ]
    run_cmd(cmd)

def run_vunit(  repo_top,
                build_path,
                lib_name,
                source_list,
                external_ghdl_path_list,
                test_file=None,
                compile_flag=[],
                top_level=None) -> None:
    

    # Ensure a VUnit action is present
    # right before from_argv
    os.environ["VUNIT_SIMULATOR"] = "ghdl"       # simulator “family”
    os.environ["VUNIT_GHDL_BACKEND"] = "gcc"    # pick the GCC backend explicitly

    vunit_args = []
    vu = VUnit.from_argv(argv=vunit_args, compile_builtins=False)    
    vu.add_vhdl_builtins()
   
    main_lib_path = os.path.realpath(build_path)
    lib = vu.add_library(lib_name)
    with open(str(source_list)) as f:
        for line in f:
            abs_path = os.path.abspath(os.path.join(repo_top, line.strip()))
            lib.add_source_files(abs_path)
           
   
    lib_files = vu.get_source_files(library_name=lib_name)
    vhdl_ordred_files=[]
    for src in vu.get_compile_order(source_files=lib_files):
        vhdl_ordred_files.append(src.name)
        print(os.path.relpath(os.path.abspath(src.name), repo_top))
    
    with open("vunit_vhdl_order_files.txt", "w") as f:
        for vhdl_file in vhdl_ordred_files:
            file=os.path.abspath(vhdl_file)
            f.write(f"{file}\n")
   
    
    for lib_path in external_ghdl_path_list:
        extrenal_lib_name = "unisim"  
        vu.add_external_library(extrenal_lib_name, lib)
       
    
   
