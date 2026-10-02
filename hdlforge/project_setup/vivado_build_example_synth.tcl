# HDLForge snapshots this maintained script unchanged and supplies run.json.
if {![info exists ::hdlforge_config]} {
    source [file join [file dirname [info script]] _hdlforge runtime.tcl]
    ::hdlforge::run [file normalize [info script]] $argv
}

##############################################################################
## See the injected README.md beside this script for setup and build commands.
## HDLForge snapshots this run's declared inputs before this script starts.
## Build ip_example first to populate the logical latest selection.
##############################################################################


# Initialize the in-memory design and read this run's frozen sources.
# Design and Vivado settings are maintained with this run.
set top "top"
set part "xcvu9p-fsgd2104-3-e"
::hdlforge::design $top $part
set_param general.usePosixSpawnForFork 1
set_param project.singleFileAddWarning.threshold 0
set_param project.compositeFile.enableAutoGeneration 0
set_param "general.maxThreads" "8"
create_project -in_memory -part $part
set_property "XPM_LIBRARIES" [list "XPM_CDC" "XPM_FIFO" "XPM_MEMORY"] [current_project]
set_property "default_lib" "xil_defaultlib" [current_project]
set_property "target_language" "Verilog" [current_project]
set_property "ip_output_repo" "ip_cache" [current_project]
set_property "ip_cache_permissions" [list "read" "write"] [current_project]
set_property "verilog_define" "SYNTHESIS" [current_fileset]

# Read the frozen inputs with this run's language and property choices.
set input [::hdlforge::source_path "sources/RTL/top.sv"]
read_verilog -sv -library "xil_defaultlib" $input
set input [::hdlforge::source_path "sources/RTL/helper.vhd"]
read_vhdl -vhdl2008 -library "xil_defaultlib" $input
set_property "used_in_simulation" false [get_files $input]
set input [::hdlforge::source_path "compilation/ip_example/latest/work/ip_sources/0/example.xcix"]
read_ip $input
set ip [get_ips -quiet [file rootname [file tail $input]]]
set matches {}
foreach candidate [get_files -quiet -all -of_objects $ip] {
    if {[string match "*/example_ooc.xdc" $candidate]} {lappend matches $candidate}
}
if {![llength $matches]} {error "Missing IP constraint example_ooc.xdc"}
set_property "used_in_implementation" false $matches
foreach checkpoint [get_files -quiet -all -filter {file_type == "Design Checkpoint"}] {
    set_property "used_in_implementation" false $checkpoint
}
set input [::hdlforge::source_path "sources/XDC/synthesis.xdc"]
read_xdc $input
set_property "used_in_implementation" false [get_files $input]
set_property "used_in_synthesis" true [get_files $input]
set_property "used_in_implementation" false [get_files $input]
set input [::hdlforge::source_path "compilation/synth_example/ip_keep_hierarchy.xdc"]
read_xdc $input
set_property "used_in_implementation" false [get_files $input]
set_param "ips.enableIPCacheLiteLoad" "1"

# Timing-oriented synthesis. These are run choices, not executor defaults.
set ::ACTIVE_STEP synth_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db synth_design.pb
synth_design -top $top -part $part -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -verilog_define [list "BUILD_RUN_TYPE=0"]
set_param constraints.enableBinaryConstraints false
# Save the completed design before generating reports.
write_checkpoint -force -noxdef ${top}.dcp
generate_parallel_reports -reports [list \
    "report_utilization -file ${top}_utilization_synth.rpt -pb ${top}_utilization_synth.pb" \
]
## Optional: finish the message database opened for this stage.
# close_msg_db -file synth_design.pb
unset ::ACTIVE_STEP
