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


def add_python_paths_from_list(path_list):
    print("\n[i] Updating PYTHONPATH with the following paths:", flush=True)
    for path in path_list:
        # Step 2: Resolve env vars
        resolved = os.path.expandvars(path)
        print(f"[~] Resolving path: {resolved}")
        # Step 3: Absolute path
        abs_path = os.path.abspath(resolved)

        # Step 4: Add if not already in sys.path
        if abs_path not in sys.path:
            sys.path.insert(0, abs_path)
            print(f"[OK] Added to PYTHONPATH: {abs_path}")
        else:
            print(f"[i] Already in PYTHONPATH: {abs_path}")
    print("", flush=True)
    

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
    print("file executed: ", Path(__file__).resolve())
    table=[["key","value","allowed"]]
    for key, value in args.items():
        if( key in allowed_values):
            table.append([key.ljust(max_key_len), value, f"(allowed: {', '.join(allowed_values[key])})"])
        elif(not isinstance(value, dict) and not isinstance(value, list)):
            if REPO_TOP+"/" in str(value):
                value = str(value).replace(REPO_TOP+"/", "$REPO_TOP/")
            table.append([key.ljust(max_key_len), value, ""])
        elif(isinstance(value,dict)):
            print_str=str(value)
            if(len(print_str) > 40):
                print_str=print_str[0:37]+"..."
            table.append([key.ljust(max_key_len), print_str, ""])
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

        
def load_project_data(ProjectFilePath): 
    if( not ProjectFilePath.exists()):
        exit(f"Project file not found: {ProjectFilePath}")    

    with open(ProjectFilePath, "rb") as f:
        project_data=tomllib.load(f)
        project_data:dict
        working_path= project_data["settings"]["project_path"]
        working_path = os.path.expandvars(working_path) 
        working_path =  Path(working_path).resolve()
        return working_path, project_data

def get_project_file_path(project_file_arg:Union[str,None]) ->  Path:
    INVOKE_PATH= Path(os.environ["HDLFORGE_ORIG_PATH"] )  
    hdlforge_files = list(INVOKE_PATH.glob("*.hdlforge.toml"))
    
    if(project_file_arg==None):
        print("Available project files in current directory:")
        for i, file in enumerate(hdlforge_files):
            print(f"  [{i+1}] {file.name}")
        print("")
        print("Please specify the project file using --project <project_file.hdlforge.toml>")
        print("Example: hdlforge Verilator --project phy10gbaser.hdlforge.toml --step build --SimTargetName main")
        exit(1)
    else:
        # Look for the project file in the current directory
        project_file_path = INVOKE_PATH / project_file_arg
        if not project_file_path.exists():
            print(f"Project file not found: {project_file_path}")
            print("Available project files in current directory:")
            for i, file in enumerate(hdlforge_files):
                print(f"  [{i+1}] {file.name}")
            exit(1)
        return project_file_path
    
   
def get_file_list_for_tool(tool_name: str, project_data: dict,verbose: bool=False) -> List[dict]:
   
   
    project_path_raw = Path(project_data["settings"]["project_path"])
    project_path_expanded = os.path.expandvars(project_path_raw)
    project_path_abs = Path(project_path_expanded).resolve()


    all_source_files        =  project_data["sources"]["files"].copy()
    tool_source_files= []
    file_order=1
    for file_dict in all_source_files:
        if(tool_name in file_dict and file_dict[tool_name] is True):
            relative_to_project_path = file_dict.get("relative_to_project_path", False)
            if(not isinstance(file_dict["file"] ,list)):
                _file= file_dict["file"]
                file_dict["file"] = []  # Initialize as a list
                file_dict["file"].append(_file)

            for idx in range(len(file_dict["file"])):
                file_path = file_dict["file"][idx]
                if(relative_to_project_path):
                    file_path = project_path_abs / Path(file_path)
                else:
                    file_path = Path(file_path)
                if verbose: print(f"[i] source file #{file_order}: {str(file_path)} for tool: {tool_name}")
                _file_dict = file_dict.copy()  # Create a shallow copy of the dictionary
                _file_dict["file"] = str(file_path)
                tool_source_files.append(_file_dict)
                file_order += 1
           
    return tool_source_files



def verify_project_file_path(_working_path: Path, REPO_TOP: Path):
    PROJECT_FILES=Path(_working_path)
    if not str(PROJECT_FILES.resolve()).startswith(str(REPO_TOP.resolve())):
        print(f"[!x!]  PROJECT_FILES path '{PROJECT_FILES}' is not under REPO_TOP '{REPO_TOP}'")
        print(f"Please run: update_repo_path")
        exit(1)
    return PROJECT_FILES

def capture_environment_variables(c: invoke.Context):
    """Capture environment variables set by update_repo_path function and validate repository environment"""
    invoked_dir = os.environ.get('HDLFORGE_ORIG_PATH', os.getcwd())
    
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

def convert_vcd_to_csv(c: invoke.Context, vcd_file_path: Path, csv_file_path: Path) -> bool:
    """
    Convert VCD (Value Change Dump) file to CSV format using command line tool.
    
    Args:
        c: Invoke context for running commands
        vcd_file_path: Path to the input VCD file
        csv_file_path: Path to the output CSV file
        
    Returns:
        bool: True if conversion successful, False otherwise
    """
    try:
        print(f"[i] Converting VCD to CSV: {vcd_file_path} -> {csv_file_path}")
        
        if not vcd_file_path.exists():
            print(f"[!x!] VCD file not found: {vcd_file_path}")
            return False
        
        # Create output directory if it doesn't exist
        csv_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Try different VCD to CSV conversion tools
        conversion_tools = [
            # Try vcd2csv if available
            f"vcd2csv {vcd_file_path} {csv_file_path}",
            # Try gtkwave with export functionality
            f"gtkwave --vcd {vcd_file_path} --export {csv_file_path}",
            # Try custom vcd_to_csv script if available
            f"vcd_to_csv {vcd_file_path} {csv_file_path}",
            # Fallback: use awk/sed for basic conversion
            f"awk '/^\\$var/ {{print $4}}' {vcd_file_path} | head -20 > {csv_file_path}.tmp && echo 'time,' > {csv_file_path} && cat {csv_file_path}.tmp >> {csv_file_path} && rm {csv_file_path}.tmp"
        ]
        
        conversion_successful = False
        for tool_cmd in conversion_tools:
            try:
                print(f"[i] Trying conversion tool: {tool_cmd.split()[0]}")
                result = c.run(tool_cmd, hide=True, warn=True)
                if result.exited == 0 and csv_file_path.exists():
                    print(f"[+] VCD to CSV conversion completed using: {tool_cmd.split()[0]}")
                    conversion_successful = True
                    break
                else:
                    print(f"[i] Tool {tool_cmd.split()[0]} not available or failed")
            except Exception as e:
                print(f"[i] Tool {tool_cmd.split()[0]} failed: {e}")
                continue
        
        if not conversion_successful:
            print(f"[!x!] No suitable VCD to CSV conversion tool found")
            print(f"[i] Available tools to install:")
            print(f"  - vcd2csv: pip install vcd2csv")
            print(f"  - gtkwave: sudo apt-get install gtkwave")
            print(f"  - Custom vcd_to_csv script")
            return False
        
        return True
        
    except Exception as e:
        print(f"[!x!] VCD to CSV conversion failed: {e}")
        return False

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

@task
def vivado(c,project,verbose=False,step:List[str]=[],clean=False,run_flow=None):
    # Capture environment variables set by update_repo_path
    capture_environment_variables(c)

    ALLOWED_STEPS = {"step":["new","list_runs","reset_run", "syn", "impl", "bit"]}
    TOOL_NAME = "vivado"
    SCRIPT_DIR                  = Path("/opt/project_setup")
    REPO_TOP = Path(os.environ["REPO_TOP"]) 


    project_toml_file              = get_project_file_path(project)
    WORKING_PATH,PROJECT_DATA_DICT = load_project_data(project_toml_file)
    VIVADO_SETTING_DICT             = PROJECT_DATA_DICT["vivado_settings"]

   
    VIVADO_BUILD_DIR        = WORKING_PATH / VIVADO_SETTING_DICT["build_dir"]
    SOURCES_DICT_LIST       = get_file_list_for_tool(TOOL_NAME, PROJECT_DATA_DICT,verbose)
    VIVADO_GEN_PRJ_TCL_PATH = WORKING_PATH / VIVADO_SETTING_DICT["project_tcl"]
    PROJECT_NAME            = VIVADO_SETTING_DICT["project_name"].strip()  # strip spaces just in case
    TOP_MODULE              = VIVADO_SETTING_DICT["top_module"]
    PART                    = VIVADO_SETTING_DICT["part"]

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

    def call_compile_tcl(step,syth_name,impl_name,paramaters,defines ):
        with c.cd(str(VIVADO_BUILD_DIR)):
            table=[["Step", step]]
            table.append(["Synth", syth_name])
            table.append(["Impl", impl_name])
            table.append(["Parameters", paramaters])
            table.append(["Defines", defines])
            print(tabulate(table, headers="firstrow", tablefmt="grid"))

            cmd= f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr {step} {syth_name} {impl_name} '{paramaters}' '{defines}'"
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
                    sources_dict_list=SOURCES_DICT_LIST)
                print(f"[i] Creating Vivado project : {VIVADO_GEN_PRJ_TCL_PATH}")
                with c.cd(str(VIVADO_BUILD_DIR)):
                    c.run(f"vivado -mode batch -source {VIVADO_GEN_PRJ_TCL_PATH} -notrace")

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
                syth_name=runs_flow["synth"]
                impl_name_list=runs_flow["impl"]
                paramaters = runs_flow.get("paramaters", [])
                defines = runs_flow.get("defines", [])
                paramaters= " ".join(paramaters)
                defines= " ".join(defines)
                call_compile_tcl(f"{s}" ,f"{syth_name}" ,f"{impl_name_list[0]}" ,f"'{paramaters}'" ,f"'{defines}'" )
          
            case "bit":
                pass
            case "all":
                print(f"[i] Running Vivado synthesis, implementation and bitstream generation for project: {PROJECT_NAME}")
                with c.cd(str(VIVADO_BUILD_DIR)):
                    c.run(f"vivado -mode batch -source {SCRIPT_DIR}/compile.tcl -notrace -tclargs  {PROJECT_NAME}.xpr all",pty=True,echo=True)
            case _:
                pass


     
   
def verify_sim_target(SimTargetName, verilator_settings)    :
    if SimTargetName is None:
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName must be specified. Use --SimTargetName <target_name>")
    elif(SimTargetName not in verilator_settings["sim_targets"]):
        print(f"Available SimTargetNames: {', '.join(verilator_settings['sim_targets'].keys())}")
        exit(f"[!x!]  SimTargetName '{SimTargetName}' not found in verilator_settings['sim_targets']")

    return SimTargetName

@task
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
    
    project_file_path = get_project_file_path(project)
    working_path,project_data = load_project_data(project_file_path)
    
    print_task_args(locals(),str(REPO_TOP),ALLOWED_STEPS)
      
    
    verilator_settings  = project_data["verilator_settings"]
    build_dir           = Path(working_path ) / verilator_settings["build_dir"]
    SOURCES_DICT_LIST = get_file_list_for_tool(tool_name, project_data)
      
    
    # Verify the parameters
    SimTargetName=verify_sim_target(SimTargetName, verilator_settings)    
   
    
    SimTarget                 = verilator_settings["sim_targets"][SimTargetName]
    top_module                = SimTarget["top_module"]
    build_args                = SimTarget.get("build_args", [])
    defines                   = SimTarget.get("defines", {})
    parameters                = SimTarget.get("parameters", {})
    python_file_path          = Path(working_path ) / SimTarget["python_file"] 
    test_name                 = SimTarget.get("test_name",None)

    PYTHONPATH = SimTarget.get("PYTHONPATH", [])
    # PYTHONPATH.append(str(python_file_path.parent.resolve()))  # Add the directory of the Python file
    add_python_paths_from_list(PYTHONPATH)
  

    
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
                        
                        # VCD to CSV conversion disabled to prevent hanging
                        vcd_file_path = build_dir / SimTargetName / "dump.vcd"
                        csv_file_path = build_dir / SimTargetName / "dump.csv"
                        
                        if vcd_file_path.exists():
                            print(f"[i] Found VCD file: {vcd_file_path}")
                            print(f"[i] VCD to CSV conversion disabled to prevent hanging")
                        else:
                            print(f"[!x!] VCD file not found: {vcd_file_path}")
                            print(f"[i] Simulation may not have generated VCD file (waves=True required)")
                    else:
                        print(f"[i] Skipping Verilator simulation",flush=True)
                        
                except Exception as e:
                    print("\n[!x!]  Verilator build/simulation failed!",flush=True)
                    print(f"Error: {e}",flush=True)

@task
def projects(c,set_project=None):
    projects=get_project_file_path(None)


@task
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
    print("  Projects are configured using *.hdlforge.toml files in your working directory.")
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


