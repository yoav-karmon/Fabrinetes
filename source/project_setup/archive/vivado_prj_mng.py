#!/usr/bin/env python3

#tool_box: <file.json> ; print vivadp project settings as tcl to stdout, reset; print basic json to stdout  

import tomllib

import sys
import argparse



def get_vivado_flows():
    synth_strategies = [
        "Flow_PerfOptimized_high",
        "Flow_RuntimeOptimized",
        "Flow_AreaOptimized_high",
        "Flow_AreaOptimized_medium",
        "Flow_AlternateRoutability",
        "Flow_PerfThresholdCarry",
        "Flow_AreaMultThresholdDSP"
    ]

    impl_strategies = [
        # Performance
        "Performance_Explore",
        "Performance_ExplorePostRoutePhysOpt",
        "Performance_ExtraTimingOpt",
        "Performance_NetDelay_high",
        "Performance_WLBlockPlacement",
        "Performance_Retiming",
        # Congestion
        "Congestion_SpreadLogic_high",
        "Congestion_SpreadLogic_medium",
        "Congestion_SpreadLogic_low",
        # Area
        "Area_Explore",
        "Area_ExploreSequential",
        "Area_ExploreWithRemap",
        # Power
        "Power_DefaultOpt",
        "Power_ExploreArea",
        # Flow
        "Flow_RunPhysOpt",
        "Flow_RunPostRoutePhysOpt",
        "Flow_RuntimeOptimized",
        "Flow_Quick"
    ]

    synth_flow = "{Vivado Synthesis 2021}"
    impl_flow = "{Vivado Implementation 2021}"

    for i, synth_strategy in enumerate(synth_strategies):
        synth_name = f"synth_{i}"
        print(f"create_run {synth_name} -flow {synth_flow} -strategy {synth_strategy}")
        for j, impl_strategy in enumerate(impl_strategies):
            impl_name = f"impl_{i}_{j}"
        print(f"create_run {impl_name} -parent_run {synth_name} -flow {impl_flow} -strategy {impl_strategy}")


class TclBlock:
    def __init__(self,description=None):
        self.description = description
        self.code = []

    def add(self, line):
        self.code.append(line)

    def add_lines(self, lines):
        self.code.extend(lines)

    def to_dict(self):
        return {
            "description": self.description,
            "code": self.code
        }

    @classmethod
    def from_dict(cls, d):
        block = cls(d["section"], d.get("description"))
        block.add_lines(d.get("code", []))
        return block

def append_block(description:str, lines):
    if description:
        lines.append(f"# {description}")
        lines.extend(lines)
    lines.append("")  # blank line between blocks

def emit_vivado_project_settings_tcl(json_file):
    with open(json_file, "rb") as f:
        blocks = tomllib.load(f)
    
    tcl_lines = []

    # read the json file
    vivado_settings_dic =blocks["vivado_settings"]
    settings_dic        =blocks["settings"]

    build_dir    = vivado_settings_dic["build_dir"].strip('"')
    project_tcl = vivado_settings_dic["project_tcl"].strip('"')
    part            = vivado_settings_dic["part"].strip('"')
    project_name    = vivado_settings_dic["project_name"].strip('"')
    top_module      = vivado_settings_dic["top_module"].strip('"')
    source_files     = vivado_settings_dic["sources"]
    extra_code_lines = vivado_settings_dic["code"]
    vivado_runs            = vivado_settings_dic["runs"]
    generics_list         = vivado_settings_dic["generics"]
    # G_BOARD_ID      = settings_dic["G_BOARD_ID"].strip('"')
    # G_APP_ID        = settings_dic["G_APP_ID"].strip('"')
    # appid           = settings_dic["appid"].strip('"')
    # cfg             = settings_dic["cfg"].strip('"')
    # bid             = settings_dic["bid"].strip('"')
    import_env     = vivado_settings_dic["import_env"]


    tcl_lines.append(f"# Generated from: {json_file}")
    tcl_lines.append("# This script was auto-generated to configure Vivado project settings.")
    tcl_lines.append("")

    tcl_lines.append("#******************************************************")
    tcl_lines.append(f"set project_name {project_name}")
    tcl_lines.append(f"set PART  {part}")
    tcl_lines.append(f"set top_module {top_module}")
    tcl_lines.append("#******************************************************")
    tcl_lines.append("")


    tcl_lines.append("#******************************************************")
    tcl_lines.append(f"set REPO_TOP $::env(REPO_TOP)")
    tcl_lines.append(f"set ::REPO_TOP $REPO_TOP")
    for env_var in import_env:
        tcl_lines.append(f"set {env_var} $::env({env_var})")
        tcl_lines.append(f"set ::{env_var} ${env_var}")
    tcl_lines.append("#******************************************************")
    tcl_lines.append("")





    tcl_lines.append("#******************************************************")
    tcl_lines.append(f"set project_name {project_name}")
    tcl_lines.append(f"set PART  {part}")
    tcl_lines.append(f"set top_module {top_module}")
    tcl_lines.append("#******************************************************")
    tcl_lines.append("")



    tcl_lines.append("#******************************************************")
    tcl_lines.append(f"create_project -force $project_name  -part $PART")
    tcl_lines.append(f"set_property top $top_module [current_fileset]")
    generics_line= "set_property generic {"
    for generics in generics_list:
        generics_line+= f"{generics} "
    generics_line+=  "} [current_fileset]"   
    tcl_lines.append(generics_line) 
    tcl_lines.append("#******************************************************")
    tcl_lines.append("")
 
    


    tcl_lines.append("#******************************************************")
    tcl_lines.append("set script_dir [file dirname [info script]]")
    tcl_lines.append("source $REPO_TOP/tools/project_setup/add_files_from_list.tcl")
    for file in source_files:
        tcl_lines.append(f"add_files_from_list $script_dir/{file}")
    for code_lines in extra_code_lines:
        tcl_lines.append(code_lines)
    tcl_lines.append("#******************************************************")
    tcl_lines.append("")


    tcl_lines.append("#******************************************************")
    for run in vivado_runs:
        run = run.strip('"')
        if("ynth_1" in run):
            print("ERROR: run name contains 'synth_1', this may cause issues with Vivado project management.")
            exit(1)
        tcl_lines.append(run)
    tcl_lines.append("delete_runs synth_1")
    tcl_lines.append("#******************************************************")
    tcl_lines.append("")
    



    

    output_text = "\n".join(tcl_lines)
    with open(project_tcl, "w") as f:
        f.write(output_text)   

def reset_runs():
    blk = TclBlock("Custom Synthesis and Implementation Runs")
    blk.add("create_run synth_main -flow {Vivado Synthesis 2021} -strategy Flow_PerfOptimized_high")
    blk.add("create_run impl_main_0 -parent_run synth_main -flow {Vivado Implementation 2021} -strategy Performance_ExplorePostRoutePhysOpt")
    blk.add("delete_runs synth_1")
    return blk



def quoted_puts(text: str) -> str:
    return f'puts "{text}"'






if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Generate TCL from json     : <script_blocks.json> ")
        print("  Generate Reset JSON file   :  reset ")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

  
    parser = argparse.ArgumentParser(description="Emit Vivado TCL from JSON block file")
    parser.add_argument("json_file")
    opts = parser.parse_args(sys.argv[1:])
    emit_vivado_project_settings_tcl(opts.json_file)
