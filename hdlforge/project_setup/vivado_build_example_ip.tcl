# HDLForge snapshots this maintained script unchanged and supplies run.json.
if {![info exists ::hdlforge_config]} {
    source [file join [file dirname [info script]] _hdlforge runtime.tcl]
    ::hdlforge::run [file normalize [info script]] $argv
}

##############################################################################
## See the injected README.md beside this script for setup and build commands.
## HDLForge snapshots the source IP and regenerates a private working copy.
## Outputs remain in this timestamped run. HDLForge resolves latest logically.
##############################################################################

##############################################################################
## Load the declared IP from the private copy made by HDLForge.
## No saved project is opened. Source IP files are never regenerated in place.
##############################################################################
# Design and Vivado settings are maintained with this run.
set top "ip"
set part "xcvu9p-fsgd2104-3-e"
::hdlforge::design $top $part
set_param general.usePosixSpawnForFork 1
set_param "general.maxThreads" "8"
create_project -in_memory -part $part
set_property "default_lib" "xil_defaultlib" [current_project]
set_property "target_language" "Verilog" [current_project]
set_property "ip_output_repo" "ip_cache" [current_project]
set_property "ip_cache_permissions" [list "read" "write"] [current_project]

# Read the frozen inputs with this run's language and property choices.
set input [::hdlforge::source_path "sources/ip/example.xcix"]
read_ip $input
set ip [get_ips -quiet [file rootname [file tail $input]]]
set_property "generate_synth_checkpoint" true [get_files -all [get_property IP_FILE $ip]]
set_property "synth_checkpoint_mode" "Singular" [get_files -all [get_property IP_FILE $ip]]

##############################################################################
## Optional: structured messages for Vivado GUI filtering. Text logs also
## contain these messages; remove both message-db commands if unnecessary.
##############################################################################
# create_msg_db ip_generation.pb

set ::ACTIVE_STEP generate_target
generate_target all [get_ips] -force
unset ::ACTIVE_STEP

## Force fresh out-of-context synthesis rather than reuse the copied DCP.
set ::ACTIVE_STEP synth_ip
synth_ip -force [get_ips]
unset ::ACTIVE_STEP

report_ip_status -file ip_status.rpt
## Optional: close the matching structured message database.
# close_msg_db -file ip_generation.pb

## Package output products; HDLForge handles optional latest publication.
convert_ips -to_core_container [get_ips]
