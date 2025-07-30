#!/usr/bin/env python

import os
import sys
from pathlib import Path
import inspect
import tomllib
import tomli_w


from pyparsing import Union
import invoke
from invoke import task, run
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.runner import get_runner
from cocotb.triggers import Timer
from typing import List, Dict, Any


def generate_vivado_tcl(
    output_path: Path,
    project_name: str,
    part: str,
    top_module: str,
    generics: List[Dict[str, Any]],
    defines: List[Dict[str, Any]],
    sources: List[str],
    runs: List[Dict[str, Any]]) -> None:    

   

    print(f"ℹ️  Generating Vivado TCL script: {output_path}")
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
    if generics:
        gen_str = " ".join(generics)
        lines.append(f"set_property generic {{{gen_str}}} [current_fileset]")
    if defines:
        defines_str = " ".join(defines)
        lines.append(f"set_property verilog_define {{{defines_str}}} [current_fileset]")

    lines.append("#******************************************************\n")

# ✅ Add sources from multiple list files using add_files_from_list.tcl
    lines.append("#******************************************************")
    for filepath in sources:
        filepath = str(filepath)
        if(filepath.endswith(".vhd")):
            addcmd= "read_vhdl -vhdl2008"
        elif(filepath.endswith(".v")):
            addcmd= "read_verilog -sv"
        elif(filepath.endswith(".sv")):
            addcmd= "read_verilog -sv"
        elif(filepath.endswith(".xdc")):
            addcmd= "read_xdc"
        elif(filepath.endswith(".xcix")):
            addcmd= "read_ip"
        elif(filepath.endswith(".xci")):
            addcmd= "read_ip"
        else:
            addcmd="add_files"
            print(f"⚠️  Unknown file type for {filepath}, using add_files")
        lines.append(f"{addcmd} [file normalize [subst {filepath}]]")
    lines.append("")
    lines.append("#******************************************************\n")

    # Runs
    lines.append("#******************************************************")
    for run in runs:
        lines.append(run)
    lines.append("delete_runs synth_1")
    lines.append("#******************************************************\n")

    # Write the TCL script
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))





def print_task_args(local_vars: dict,REPO_TOP:str):
    # Get the calling function name automatically
    caller_name = inspect.stack()[1].function  

    # Remove Invoke context (c)
    args = {k: v for k, v in local_vars.items() if k != "c"}
    max_key_len = max(len(k) for k in args.keys()) if args else 0
    border = "=" * (max_key_len + 30)

    print(border)
    print(f"ℹ️  Task: {caller_name}")
    print(border)
    print(f"working directory: {os.getcwd()}")
    print("file executed: ", Path(__file__).resolve())
    for key, value in args.items():
        if(not isinstance(value, dict) and not isinstance(value, list)):
            if REPO_TOP+"/" in str(value):
                value = str(value).replace(REPO_TOP+"/", "$REPO_TOP/")
            print(f"{key.ljust(max_key_len)} : {value}")
    print(border)
    
def print_boxed(message: str, border_char: str = "=", padding: int = 2):
    lines = message.split("\n")
    max_len = max(len(line) for line in lines)
    border = border_char * (max_len + padding * 2 + 2)

    print(border)
    for line in lines:
        print(f"{border_char}{' ' * padding}{line.ljust(max_len)}{' ' * padding}{border_char}")
    print(border)

        
def load_project_data(ProjectFilePath): 
    if( not ProjectFilePath.exists()):
        exit(f"Project file not found: {ProjectFilePath}")       
    with open(ProjectFilePath, "rb") as f:
        project_data=tomllib.load(f)
        project_data:dict
        working_path= project_data["settings"]["project_path"]
        working_path = Path(working_path)
        repo_path_env = project_data["settings"].get("repo_path_env",None)
        if(repo_path_env == None):
            working_path = Path(working_path)
            print(f"⚠️  No repo_path_env found in project file:(settings.repo_path_env), using absolute path")
        else:
            REPO_TOP = Path(os.environ.get(repo_path_env, "REPO_TOP"))
            if not REPO_TOP:
                exit(f"❌ Environment variable '{repo_path_env}' is not set. Please set it to the repository top path.")
            working_path = REPO_TOP / working_path
            print(f"ℹ️  Using repo_path_env: {repo_path_env} with value: {REPO_TOP}, working path: {working_path}")
        return working_path, project_data

def get_project_file_path(project_name_arg:Union[str,None]) -> tuple[str, Path]:
    invoke_path= Path(os.environ["HDLFORGE_ORIG_PATH"] )

    with open("hdlforge.toml", "rb") as f:
        proejcts_dict=tomllib.load(f)
        REPO_TOP = Path(os.environ["REPO_TOP"]) 
        if(project_name_arg!=None):
            for project_name, project_file in proejcts_dict["projects"].items():
                if project_name_arg.strip() == project_name.strip() :
                    project_file_path = REPO_TOP / "tools" /"project_setup" / project_file
                    return project_name_arg,project_file_path
            exit(f"❌ Project '{project_name_arg}' not found in hdlforge.toml. Available projects: {', '.join(proejcts_dict['projects'].keys())}")
        else:
            for project_name, project_file in proejcts_dict["projects"].items():
                _,_project_file_path=get_project_file_path(project_name)
                _, _project_data=load_project_data(_project_file_path)
                result_project_path = REPO_TOP / _project_data["settings"]["project_path"]
                if result_project_path == invoke_path:
                    print(f"ℹ️  Found project file for invoke path: {invoke_path} -> {result_project_path}")
                    return project_name,_project_file_path
           
        exit(f"❌ No project found for invoke path: {invoke_path}. Please specify a project name or ensure you are in a valid project directory.")

def get_file_list_for_tool(tool_name: str, project_file: Path) -> List[str]:
    # Ensure project_file is a Path object and expand environment variables
    project_file = Path(os.path.expandvars(str(project_file))).resolve()

    print(f"ℹ️  Searching for source files for tool: {tool_name} in project file: {project_file}")
   
    with open(project_file, "rb") as f:
        project_data=tomllib.load(f)
    repo_path_env = project_data["settings"]["repo_path_env"]
    use_repo_path_env= project_data["settings"]["use_repo_path_env"]
    project_path = Path(project_data["settings"]["project_path"])
    REPO_TOP = Path(os.environ[repo_path_env]) 

    if(use_repo_path_env):
        
        project_path_abs = REPO_TOP/project_path
    else:
        project_path_abs = project_path

    relative_to_project_path= project_data["sources"]["path"]["realtive_to_project_path"]
    if(relative_to_project_path):
        source_files_relative_path = project_path_abs
        if(f"{REPO_TOP}" in str(source_files_relative_path)):
            source_files_relative_path = str(source_files_relative_path).replace(f"{REPO_TOP}", "$REPO_TOP")
        print(f"ℹ️  Using relative path to project: {source_files_relative_path}")

    all_source_files        =  project_data["sources"]["files"]
    tool_source_files= []
    all_source_files:dict
    for file_path,tool_list in all_source_files.items():
        if(tool_name in tool_list):
            if(relative_to_project_path):
                file_path = source_files_relative_path / Path(file_path)
            else:
                file_path = Path(file_path)
            print(f"ℹ️  source file: {str(file_path)} for tool: {tool_name}")
            tool_source_files.append(file_path)
    return tool_source_files

def set_file_list_for_tool(tool_name: str, file_path:str, project_file: Path):
    with open(project_file, "rb") as f:
        project_data=tomllib.load(f)
    all_source_files        =  project_data["sources"]
    all_source_files:dict
    if(file_path not in all_source_files):
        all_source_files[file_path] = [tool_name]
    else:
        if(tool_name not in all_source_files[file_path]):
            all_source_files[file_path].append(tool_name)
    project_data["sources"] = all_source_files
    with open(project_file, "wb") as f:
        tomli_w.dump(project_data, f)
    print(f"✅ Added {file_path} to {tool_name} sources")


def run_invoke(command, cwd=None, log_file=None, pty=False):
    """
    Run a shell command using invoke with optional cwd and logging.

    :param command: Command to run (str)
    :param cwd: Working directory (str, optional)
    :param log_file: Log file to save stdout (str, optional)
    :param pty: Use pty=True for interactive apps (default False)
    :return: Exit code (int)
    """
    original_cwd = os.getcwd()
    try:
        if cwd:
            os.chdir(cwd)

        if log_file:
            command = f"bash -c 'set -o pipefail; {command} >> {log_file}'"

        result = run(command, pty=pty, warn=True)  # warn=True prevents exception on nonzero exit
        return result.exited
    finally:
        os.chdir(original_cwd)



@task
def vivado(c,project=None,new=False,dryrun=False,reset=False,syn=False,imp=False,all=False, bit=False, clean=False):
    if dryrun and (syn or imp or bit or all):
        print("❌ Dry run mode is incompatible with synthesis, implementation or bitstream generation. Exiting.")
        exit(1)

    REPO_TOP = Path(os.environ["REPO_TOP"])  # Fail fast if REPO_TOP is not set
    invoke_path= Path(os.environ["HDLFORGE_ORIG_PATH"] )
    if(REPO_TOP not in invoke_path.resolve().parents):
        print(f"❌ REPO_TOP '{REPO_TOP}' is not in the invoke path '{invoke_path}'")
        print(f"Please run: update_repo_top")
        exit(1)
    print(f"ℹ️  invoke_path: {invoke_path}")
    tool_name = "vivado"
    project,project_file_path = get_project_file_path(project)
    working_path,project_data = load_project_data(project_file_path)
    vivado_settings  = project_data["vivado_settings"]

    PROJECT_FILES =  Path(working_path ) 
    SCRIPT_DIR = REPO_TOP / "tools" / "project_setup"

    if not str(PROJECT_FILES.resolve()).startswith(str(REPO_TOP.resolve())):
        print(f"❌ PROJECT_FILES path '{PROJECT_FILES}' is not under REPO_TOP '{REPO_TOP}'")
        print(f"Please run: update_repo_top")
        exit(1)


    VIVADO_BUILD_DIR        = PROJECT_FILES / vivado_settings["build_dir"]
    SOURCES_LIST            = get_file_list_for_tool(tool_name, project_file_path)
    VIVADO_GEN_PRJ_TCL_PATH = PROJECT_FILES / vivado_settings["project_tcl"]
    PROJECT_NAME            = vivado_settings["project_name"].strip()  # strip spaces just in case
    TOP_MODULE              = vivado_settings["top_module"]
    PART                    = vivado_settings["part"]
    IMPORT_ENV              = vivado_settings.get("import_env", [])
    SET_VAR         = vivado_settings.get("set_var", [])
    GENERICS        = vivado_settings.get("generics", [])
    DEFINES         = vivado_settings.get("defines", [])
    CODE            = vivado_settings.get("code", [])
    RUNS            = vivado_settings.get("runs", [])

    ##remove REPO_TOP  from sources list


    print_task_args(locals(),str(REPO_TOP))

    def cleaning(BUILD_DIR,clean):  
        if(clean):
            print(f"ℹ️  Cleaning Vivado build directory: {BUILD_DIR}")
            if BUILD_DIR.exists():
                response = input(f"{BUILD_DIR} will be deleted! (y/n): ")
                if response.lower() != "y":
                    print("Aborted clean operation.")
                    return
                c.run(f"rm -rf {BUILD_DIR}")
                print(f"✅ removed Vivado build directory: {BUILD_DIR}")
            else:
                print(f"ℹ️  nothing to clean in Vivado build directory: {BUILD_DIR}")
            c.run(f"mkdir {BUILD_DIR}")
    if(clean):
        cleaning(VIVADO_BUILD_DIR,True)

    if(new):
        cleaning(VIVADO_BUILD_DIR,True)
        print(f"ℹ️  Creating new Vivado project: {PROJECT_NAME}")

        generate_vivado_tcl(
            output_path=VIVADO_GEN_PRJ_TCL_PATH,
            project_name=PROJECT_NAME,
            part=PART,
            top_module=TOP_MODULE,
            generics=GENERICS,
            defines=DEFINES,
            sources=SOURCES_LIST,
            runs=RUNS)
        if(not dryrun):
            print(f"ℹ️  Creating Vivado project : {VIVADO_GEN_PRJ_TCL_PATH}")
            with c.cd(str(VIVADO_BUILD_DIR)):
                c.run(f"vivado -mode batch -source {VIVADO_GEN_PRJ_TCL_PATH}")


     
    if(dryrun):
        print_boxed(f"ℹ️  Dry run mode enabled. No actions will be performed for Vivado project: {PROJECT_NAME}")
        with c.cd(str(VIVADO_BUILD_DIR)):
            c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr dryrun",pty=True)

    if(all):
        print(f"ℹ️  Running Vivado synthesis, implementation and bitstream generation for project: {PROJECT_NAME}")
        with c.cd(str(VIVADO_BUILD_DIR)):
            c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr all",pty=True)
    else:
        if(syn):
            print(f"ℹ️  Running Vivado synthesis for project: {PROJECT_NAME}")
            with c.cd(str(VIVADO_BUILD_DIR)):
                c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr syn",pty=True)
        if(imp):
            print(f"ℹ️  Running Vivado implementation for project: {PROJECT_NAME}")
            with c.cd(str(VIVADO_BUILD_DIR)):
                c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr impl",pty=True)
    

@task
def VerlatorCompile(c,project=None,SimTargetName=None,clean=False, sim=False):
    REPO_TOP = Path(os.environ["REPO_TOP"])  # Fail fast if REPO_TOP is not set
    tool_name = "verilator"
    project,project_file_path = get_project_file_path(project)
    working_path,project_data = load_project_data(project_file_path)
    
    print_task_args(locals(),str(REPO_TOP))
      
    
    verilator_settings  = project_data["verilator_settings"]
    build_dir           = Path(working_path ) / verilator_settings["build_dir"]
    sources_files = get_file_list_for_tool(tool_name, project_file_path)
      
    
        
    if SimTargetName is None:
            sim_targets_dic = verilator_settings["sim_targets"]
            # Get the first value in sim_targets
            SimTargetName = next(iter(sim_targets_dic.keys()))
            print(f"ℹ️  Using first SimTargetName: {SimTargetName}")
            
    if(SimTargetName not in verilator_settings["sim_targets"]):
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"❌ SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")
        

    SimTarget = verilator_settings["sim_targets"][SimTargetName]

    top_module = SimTarget["top_module"]
    python_file_path          =  Path(working_path ) / SimTarget["python_file"]   
    python_file_dir_path = str(Path(python_file_path).parent.resolve())
    sys.path.insert(0, python_file_dir_path)

    python_module = python_file_path.stem  
    

    try:
        runner = get_runner("verilator")

        print(f"ℹ️  Compiling Verilator sources into: {build_dir}")
        veruilator_sources_file = []
        for file in sources_files:
            veruilator_sources_file.append(Path(os.path.expandvars(str(file))).resolve())

        runner.build(
                verilog_sources=veruilator_sources_file,
                hdl_toplevel=f"{top_module}",
                waves=True   ,
                build_dir=f"{build_dir}",   
                always=True,   
                build_args=[
                    "--public-flat-rw",       # Expose signals for RW
                    "--trace",                # Needed for waves
                    "--trace-structs"       # Better struct/array visibility (5.x)
                ],
                clean=clean   # force rebuild
            )
        print(f"✅ Verilator build completed")
        print(f"ℹ️  Verilator simulation started:")
        if(sim):    
            runner.test(
                hdl_toplevel=f"{top_module}",
                test_module=f"{python_module}",  
                build_dir=f"{build_dir}",   
                waves=True                  # enables dump.vcd
            )
            print(f"✅ Verilator simulation completed")
        else:
            print(f"ℹ️  Skipping Verilator simulation")
            
    except Exception as e:
        print("\n❌ Verilator build/simulation failed!")
        print(f"Error: {e}")

@task
def projects(c,set_project=None):
    projects=get_project_file_path(None)
