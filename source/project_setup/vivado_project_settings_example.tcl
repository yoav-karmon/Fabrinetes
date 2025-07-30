<<<<<<< HEAD
# === Setup Environment ===
set REPO_TOP $::env(REPO_TOP)
set ::REPO_TOP $REPO_TOP
source "$REPO_TOP/tools/project_setup/add_files_from_list.tcl"
set script_dir [file dirname [info script]]


# === Global Parameters ===
set ::appid     "?? 239"
set ::cfg       "?? 0"
set ::bid       "? 10"

# === Project Configuration ===
set project_name "???? "
set project_path "$script_dir/_output"
set files_list [file join $script_dir vivado_sources.txt]

# === Output Directory Info ===
puts "REPO_TOP         : $REPO_TOP"
puts "Working Directory: [pwd]"




# set origin_dir_loc "$REPO_TOP/<path to project folder where recreate.tcl created>
# source $script_dir/recreate.tcl 

catch {
# === Create Project ===
create_project -force $project_name $project_path

# === Generics Setup ===
set_property generic "G_BOARD_ID=$::bid G_APP_ID=$::appid" [current_fileset]
set gen_readback [get_property generic [current_fileset]]
puts "GENERIC FIRST READ AS = $gen_readback"

# === Add Design Sources ===
# add_files_from_list $files_list
# or
# source oter tcl file??


#some spiecil xdc read?
#read_xdc -ref cdc_stream_ll $REPO_TOP/raven_lib/raven_common/raven_cdc/cdc_stream_ll/xdc/cdc_stream_ll.tim.xdc 

#set our top level
set_property top raven_top [current_fileset]


#set runs:
#
# Define synthesis run 'synth_Performance_Explore'
#https://www.xilinx.com/support/documents/sw_manuals/xilinx2021_1/ug904-vivado-implementation.pdf


=======
# =========================================
# Parse command-line arguments passed via the Makefile
# Argument 0: project_name  – name of the Vivado project
# Argument 1: project_path  – path where the project will be created
#
# This script is intended to be run from a Makefile.
# The Makefile should invoke Vivado with:
#   vivado -mode batch -source $(SRC_FILE) -tclargs $(PROJECT_NAME) $(PROJECT_PATH)
#
# In the local Makefile, SRC_FILE should point to this script using CUR_DIR, for example:
#   SRC_FILE := $(CUR_DIR)/scripts/tcl/create_project.tcl
# =========================================

set project_name [lindex $argv 0]
set project_path [lindex $argv 1]

# Display parsed script arguments for verification
puts "INFO: Project Name      : $project_name"
puts "INFO: Project Path      : $project_path"


# =========================================
# These values are needed when calling sources.tcl
# from a recursive action (e.g., within another script).
# REPO_TOP is pulled from the environment and propagated,
# and other global values like appid, cfg, and bid are set.
# =========================================

# Reference HDL and constraint source files 
set REPO_TOP $::env(REPO_TOP)
puts "REPO_TOP: $REPO_TOP"
set ::REPO_TOP $REPO_TOP
set ::appid "240"
set ::cfg "0"
set ::bid "11"

# =========================================
# Create Vivado project
# This is a **mandatory** command.
# It initializes the project and defines the location where all
# generated files, runs, and configurations will be stored.
# Without this, no project context is created and subsequent
# commands like add_files or set_property will fail.
# =========================================
create_project -force $project_name $project_path


# =========================================
# Example of pre-setup for IP and HDL files that are NOT included
# in the recursive sources.tcl script.
# These IP cores and supporting files are read manually here to ensure
# they are part of the project before the full recursive source flow runs.
# This is useful when specific IPs or source files need to be forced into
# the project independently of the shared source management logic.
# =========================================

        # set_property ip_repo_paths {} [current_fileset]
        # set_property ip_repo_paths {output/ip} [current_fileset]

        # set ipcore_files [list \
        # "$REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_0.xcix" \
        # "$REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_1.xcix" \
        # "$REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_2.xcix" \
        # "$REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_3.xcix" \
        # "$REPO_TOP/raven_lib/ip/VUP/gdma_0.xcix" \
        # ] 
        # read_ip -verbose $REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_0.xcix 
        # read_ip -verbose $REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_1.xcix 
        # read_ip -verbose $REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_2.xcix 
        # read_ip -verbose $REPO_TOP/raven_lib/ip/VUP/gtwizard_ultrascale_3.xcix 
        # read_ip -verbose $REPO_TOP/raven_lib/ip/VUP/gdma_0.xcix 
        # set ipcores [list gtwizard_ultrascale_0 gtwizard_ultrascale_1 gtwizard_ultrascale_2 gtwizard_ultrascale_3 gdma_0]

        # read_verilog -sv $REPO_TOP/raven_lib/raven_platform/raven_interface/raven_interface/v/gtwizard_ultrascale_1_prbs_any.v 



# =========================================
# Two alternative methods for loading HDL and constraint sources into the project:
#
# METHOD 1: Use a recursive `sources.tcl` script
# - Centralized, structured, and reusable for loading platform-specific sources
# - Assumes global variables (like ::REPO_TOP, ::appid, ::bid) are already set
# =========================================
        # source ~/braavosfpga/raven_lib/raven_top/vup/raven_top/sources.tcl

# =========================================
# METHOD 2: Load VHDL source files from a flat source list
# - The source list file contains one file path per line
# - Each line should begin with `$REPO_TOP`
# - Paths are expanded and read individually using `read_vhdl`
# - All commands below are currently commented out
# =========================================
        # set vhdl_list_file  "$REPO_TOP/raven_projects/vup_top/md_arb/md_arb_project_lite/vivado_sources.txt"
        # set fp [open $vhdl_list_file "r"]
        # while {[gets $fp line] >= 0} {
        #     set trimmed_line [string trim $line]
        #     if {$trimmed_line ne ""} {
        #         # Expand $REPO_TOP in the line
        #         regsub -all {\$REPO_TOP} $trimmed_line $REPO_TOP expanded_line
        #         puts "📘 Reading: $expanded_line"
        #         # read_vhdl -vhdl2008 $expanded_line
        #     }
        # }


# =========================================
# Set essential project properties:
# - Generics are required to parameterize the design (e.g., board ID, app ID).
# - The top-level module must be explicitly defined so that Vivado knows where
#   to begin synthesis and implementation.
# Without these properties, synthesis and implementation will either fail
# or not reflect the intended configuration.
# =========================================

set_property generic {G_BOARD_ID=11 G_APP_ID=240} [current_fileset]

# Set the top module for the design
set_property top raven_top [current_fileset]






# =========================================
# Define custom synthesis and implementation runs with specific strategies.
# - The default 'synth_1' and 'impl_1' runs are not optimal for most flows.
# - Here, we define a new synthesis run 'synth_Performance_Explore' with a high-performance strategy.
# - Then, we define a dependent implementation run 'impl_2' with a performance-focused post-route optimization.
#
# These flows and strategies can be changed depending on design goals (e.g., timing, area, power).
# After defining the custom runs, we remove the default 'synth_1' run to avoid confusion or accidental use.
# =========================================

>>>>>>> origin/md_arb_lite
puts "INFO: Defining synthesis run 'synth_Performance_Explore'."
create_run synth_Performance_Explore -flow {Vivado Synthesis 2021} -strategy Flow_PerfOptimized_high

# Define the implementation run that depends on the synthesis run
create_run impl_2 -parent_run synth_Performance_Explore -flow {Vivado Implementation 2021} -strategy Performance_ExplorePostRoutePhysOpt

# Delete default synthesis and implementation runs
delete_runs synth_1


<<<<<<< HEAD
puts "INFO: Project '$project_name' created in '$project_path'."
}
=======

# Define synthesis run 'synth_Performance_Explore'
# https://www.xilinx.com/support/documents/sw_manuals/xilinx2021_1/ug904-vivado-implementation.pdf
>>>>>>> origin/md_arb_lite
