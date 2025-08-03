#!/usr/bin/env python

import os
import sys
from pathlib import Path
import inspect
import tomllib
import tomli_w
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import Timer
from tabulate import tabulate


from pyparsing import Union
import invoke
from invoke import task, run

from typing import List, Dict, Any,Tuple
import warnings



def generate_vivado_tcl(
    output_path: Path,
    project_name: str,
    part: str,
    top_module: str,
    generics: List[Dict[str, Any]],
    defines: List[Dict[str, Any]],
    sources: List[str],
    runs: List[Dict[str, Any]]) -> None:    

   

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
    if generics:
        gen_str = " ".join(generics)
        lines.append(f"set_property generic {{{gen_str}}} [current_fileset]")
    if defines:
        defines_str = " ".join(defines)
        lines.append(f"set_property verilog_define {{{defines_str}}} [current_fileset]")

    lines.append("#******************************************************\n")

# [+] Add sources from multiple list files using add_files_from_list.tcl
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





def print_task_args(local_vars: dict, REPO_TOP: str, allowed_values: dict[str, List[str]] = {}):
    # Get the calling function name automatically
    caller_name = inspect.stack()[1].function  

    # Remove Invoke context (c)
    args = {k: v for k, v in local_vars.items() if k != "c"}
    max_key_len = max(len(k) for k in args.keys()) if args else 0
    border = "=" * (max_key_len + 30)

    print(border)
    print(f"[i] Task: {caller_name}")
    print(border)
    print(f"working directory: {os.getcwd()}")
    print("file executed: ", Path(__file__).resolve())
    table=[["key","value","allowed"]]
    for key, value in args.items():
        if( key in allowed_values):
            table.append([key.ljust(max_key_len), value, f"(allowed: {', '.join(allowed_values[key])})"])
        elif(not isinstance(value, dict) and not isinstance(value, list)):
            if REPO_TOP+"/" in str(value):
                value = str(value).replace(REPO_TOP+"/", "$REPO_TOP/")
            table.append([key.ljust(max_key_len), value, ""])
    print(tabulate(table, headers="firstrow", tablefmt="fancy_grid",colalign=("left", "left", "center")))
        
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
                exit(f"[!x!]  Environment variable '{repo_path_env}' is not set. Please set it to the repository top path.")
            working_path = REPO_TOP / working_path
            # print(f"[i] Using repo_path_env: {repo_path_env} with value: {REPO_TOP}, working path: {working_path}")
        return working_path, project_data

def get_project_file_path(project_name_arg:Union[str,None]) ->  Path:
    INVOKE_PATH= Path(os.environ["HDLFORGE_ORIG_PATH"] )  
    hdlforge_files = list(INVOKE_PATH.glob("*.hdlforge.toml"))
    if(project_name_arg==None):
        if(len(hdlforge_files) == 1):
            with open(hdlforge_files[0], "rb") as f:
                projects_dict=tomllib.load(f)
            project_name_arg=str(projects_dict["settings"]["project_name"])
            project_file_path = INVOKE_PATH / hdlforge_files[0]
            return project_file_path
        else:
            print("No project file found in the current directory.")
            print("you may have more then 1 *.hdlforge file in the current directory, please specify the project file using --project <project_name>")
            exit(1)
    else:
        project_file_path = Path(str(INVOKE_PATH) + project_name_arg)
        return project_name_arg,project_file_path
    
   
def get_file_list_for_tool(tool_name: str, project_data: dict,verbose: bool=False) -> List[str]:
   
   
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
        print(f"[i] Using relative path to project: {source_files_relative_path}")

    all_source_files        =  project_data["sources"]["files"]
    tool_source_files= []
    all_source_files:dict
    file_order=1
    for file_path,tool_list in all_source_files.items():
        if(tool_name in tool_list):
            if(relative_to_project_path):
                file_path = source_files_relative_path / Path(file_path)
            else:
                file_path = Path(file_path)
            if verbose: print(f"[i] source file #{file_order}: {str(file_path)} for tool: {tool_name}")
            file_order += 1
            tool_source_files.append(file_path)
    return tool_source_files


def set_file_list_for_tool(tool_name: str, file_path:str, project_file: Path,number:int ) -> None:
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
    print(f"[+] Added {file_path} to {tool_name} sources")


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


def get_and_verify_repo_top(INVOKE_PATH: Path):
    REPO_TOP = Path(os.environ["REPO_TOP"])  # Fail fast if REPO_TOP is not set
    INVOKE_PATH= Path(os.environ["HDLFORGE_ORIG_PATH"] )
    if(REPO_TOP not in INVOKE_PATH.resolve().parents):
        print(f"[!x!]  REPO_TOP '{REPO_TOP}' is not in the invoke path '{INVOKE_PATH}'")
        print(f"Please run: update_repo_top")
        exit(1)
    return INVOKE_PATH,REPO_TOP

def verify_project_file_path(_working_path: Path, REPO_TOP: Path):
    PROJECT_FILES=Path(_working_path)
    if not str(PROJECT_FILES.resolve()).startswith(str(REPO_TOP.resolve())):
        print(f"[!x!]  PROJECT_FILES path '{PROJECT_FILES}' is not under REPO_TOP '{REPO_TOP}'")
        print(f"Please run: update_repo_top")
        exit(1)
    return PROJECT_FILES

@task
def vivado(c,project_toml_file=None,verbose=False,step:List[str]=[],clean=False,run_flow=None):
   

    ALLOWED_STEPS = {"step":["new","list_runs","reset_run", "syn", "impl", "bit"]}
    TOOL_NAME = "vivado"
    SCRIPT_DIR                  = Path("/opt/project_setup")

    INVOKE_PATH,REPO_TOP        = get_and_verify_repo_top(Path(os.environ["HDLFORGE_ORIG_PATH"]))


    project_toml_file              = get_project_file_path(project_toml_file)
    _working_path,PROJECT_DATA_DICT = load_project_data(project_toml_file)
    VIVADO_SETTING_DICT             = PROJECT_DATA_DICT["vivado_settings"]
    PROJECT_FILES                   = verify_project_file_path(_working_path, REPO_TOP)
    del _working_path

   
    VIVADO_BUILD_DIR        = PROJECT_FILES / VIVADO_SETTING_DICT["build_dir"]
    SOURCES_LIST            = get_file_list_for_tool(TOOL_NAME, PROJECT_DATA_DICT,verbose)
    VIVADO_GEN_PRJ_TCL_PATH = PROJECT_FILES / VIVADO_SETTING_DICT["project_tcl"]
    PROJECT_NAME            = VIVADO_SETTING_DICT["project_name"].strip()  # strip spaces just in case
    TOP_MODULE              = VIVADO_SETTING_DICT["top_module"]
    PART                    = VIVADO_SETTING_DICT["part"]
    IMPORT_ENV              = VIVADO_SETTING_DICT.get("import_env", [])
    SET_VAR         = VIVADO_SETTING_DICT.get("set_var", [])
    GENERICS        = VIVADO_SETTING_DICT.get("generics", [])
    DEFINES         = VIVADO_SETTING_DICT.get("defines", [])
    CODE            = VIVADO_SETTING_DICT.get("code", [])
    RUNS            = VIVADO_SETTING_DICT.get("runs", [])

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
        cleaning(VIVADO_BUILD_DIR,True)

    def call_compile_tcl(step,syth_name,impl_name,debug_probe,paramaters,defines ):
        with c.cd(str(VIVADO_BUILD_DIR)):
            table=[["Step", step]]
            table.append(["Synth", syth_name])
            table.append(["Impl", impl_name])
            table.append(["Debug Probe", debug_probe])
            table.append(["Parameters", paramaters])
            table.append(["Defines", defines])
            print(tabulate(table, headers="firstrow", tablefmt="grid"))

            cmd= f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr {step} {syth_name} {impl_name} {debug_probe} '{paramaters}' '{defines}'"
            print(f"\n[i] Running Vivado compile TCL script with command: {cmd}\n",flush=True)
            c.run(cmd,pty=True,echo=True)

    for s in step:
        match (s):
            case "new":
                c.run(f"mkdir -p {VIVADO_BUILD_DIR}")
                cleaning(VIVADO_BUILD_DIR,True)
                print(f"[i] Creating new Vivado project: {PROJECT_NAME}")

                generate_vivado_tcl(
                    output_path=VIVADO_GEN_PRJ_TCL_PATH,
                    project_name=PROJECT_NAME,
                    part=PART,
                    top_module=TOP_MODULE,
                    generics=GENERICS,
                    defines=DEFINES,
                    sources=SOURCES_LIST,
                    runs=RUNS)
                print(f"[i] Creating Vivado project : {VIVADO_GEN_PRJ_TCL_PATH}")
                with c.cd(str(VIVADO_BUILD_DIR)):
                    c.run(f"vivado -mode batch -source {VIVADO_GEN_PRJ_TCL_PATH}")
            case "list_runs":
                print(f"[i] Listing Vivado runs for project: {PROJECT_NAME}")
                with c.cd(str(VIVADO_BUILD_DIR)):
                    c.run(f"vivado -mode batch -source {SCRIPT_DIR}/project_tool.tcl -notrace -tclargs  list_all_runs  {PROJECT_NAME}.xpr",pty=True,echo=True)
                
            case "reset_run":
                pass
            case "syn" | "impl" | "bit" | "all":
                print(f"[i] Running Vivado synthesis for project: {PROJECT_NAME}",flush=True)
                if run_flow is None:
                    runs_flow=VIVADO_SETTING_DICT["runs_flow"]
                    print("[i] Available run_flow options:")
                    for key, value in VIVADO_SETTING_DICT["runs_flow"].items():
                        print(f"--run-flow {key} ~  {key}: {value}")
                    print("[!x!] Please specify a valid run_flow argument using --run-flow <option>")
                    exit(1)
                runs_flow=VIVADO_SETTING_DICT["runs_flow"][run_flow]
                syth_name=runs_flow["synth_name"][0]
                impl_name=runs_flow["impl"][0]
                debug_probe = runs_flow.get("debug_probe", False)
                paramaters = runs_flow.get("paramaters", [])
                defines = runs_flow.get("defines", [])
                paramaters= " ".join(paramaters)
                defines= " ".join(defines)
                call_compile_tcl(f"{s}" ,f"{syth_name}" ,f"{impl_name}" ,f"{debug_probe}",f"'{paramaters}'" ,f"'{defines}'" )
          
            case "bit":
                pass
            case "all":
                print(f"[i] Running Vivado synthesis, implementation and bitstream generation for project: {PROJECT_NAME}")
                with c.cd(str(VIVADO_BUILD_DIR)):
                    c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr all",pty=True,echo=True)
            case _:
                pass


     
   

    

@task
def Verilator(c,project=None,step=None,clean=False,SimTargetName=None):
    ALLOWED_STEPS = {"step":["compile", "run", "sim", "build", "all"]}

    if isinstance(step, str):  # Convert single input to list
        step = [step]
    elif step is None:
        step = []
    
    REPO_TOP = Path(os.environ["REPO_TOP"])  # Fail fast if REPO_TOP is not set
    tool_name = "verilator"
    project_file_path = get_project_file_path(project)
    working_path,project_data = load_project_data(project_file_path)
    
    print_task_args(locals(),str(REPO_TOP),ALLOWED_STEPS)
      
    
    verilator_settings  = project_data["verilator_settings"]
    build_dir           = Path(working_path ) / verilator_settings["build_dir"]
    sources_files = get_file_list_for_tool(tool_name, project_data)
      
    
        
    if SimTargetName is None:
            sim_targets_dic = verilator_settings["sim_targets"]
            # Get the first value in sim_targets
            SimTargetName = next(iter(sim_targets_dic.keys()))
            print(f"[i] Using first SimTargetName: {SimTargetName}")
            
    if(SimTargetName not in verilator_settings["sim_targets"]):
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")
        

    SimTarget = verilator_settings["sim_targets"][SimTargetName]

    top_module = SimTarget["top_module"]
    python_file_path          =  Path(working_path ) / SimTarget["python_file"]   
    python_file_dir_path = str(Path(python_file_path).parent.resolve())
    sys.path.insert(0, python_file_dir_path)

    python_module = python_file_path.stem  
    sys.stdout.flush()
    for s in step:
        match (s):
            case "build" | "sim":
                try:
                    print(f"[i] Compiling Verilator sources into: {build_dir}",flush=True)
                    veruilator_sources_file = []
                    for file in sources_files:
                        veruilator_sources_file.append(Path(os.path.expandvars(str(file))).resolve())
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
                    print(f"================end of verilator output : build================\n",flush=True)
                    print(f"[+] Verilator build completed",flush=True)
                    print(f"[i] Verilator simulation started:",flush=True)
                    
                    if(step=="sim"):  
                        print(f"\n================start of verilator output : sim================",flush=True)  
                        runner.test(
                            hdl_toplevel=f"{top_module}",
                            test_module=f"{python_module}",  
                            build_dir=f"{build_dir}",   
                            waves=True                  # enables dump.vcd
                        )
                        print(f"================end of verilator output : sim================\n",flush=True)
                        print(f"[+] Verilator simulation completed",flush=True)
                    else:
                        print(f"[i] Skipping Verilator simulation",flush=True)
                        
                except Exception as e:
                    print("\n[!x!]  Verilator build/simulation failed!",flush=True)
                    print(f"Error: {e}",flush=True)

@task
def projects(c,set_project=None):
    projects=get_project_file_path(None)
