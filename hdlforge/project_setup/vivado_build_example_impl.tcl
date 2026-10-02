# HDLForge snapshots this maintained script unchanged and supplies run.json.
if {![info exists ::hdlforge_config]} {
    source [file join [file dirname [info script]] _hdlforge runtime.tcl]
    ::hdlforge::run [file normalize [info script]] $argv
}

##############################################################################
## See the injected README.md beside this script for setup and build commands.
## HDLForge snapshots this implementation's declared inputs before launch.
## Its generated JSON records the parent synthesis DCP path and SHA-256.
##############################################################################


# Link the explicitly selected synthesis checkpoint and the JSON IP/XDC lists.
set ::ACTIVE_STEP init_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db init_design.pb
# Design and Vivado settings are maintained with this run.
set top "top"
set part "xcvu9p-fsgd2104-3-e"
::hdlforge::design $top $part
set_param general.usePosixSpawnForFork 1
set_param project.singleFileAddWarning.threshold 0
set_param "chipscope.maxJobs" "1"
set_param "general.maxThreads" "8"
create_project -in_memory -part $part
set_property "XPM_LIBRARIES" [list "XPM_CDC" "XPM_FIFO" "XPM_MEMORY"] [current_project]
set_property "default_lib" "xil_defaultlib" [current_project]
set_property "target_language" "Verilog" [current_project]
set_property "ip_output_repo" "ip_cache" [current_project]
set_property "ip_cache_permissions" [list "read" "write"] [current_project]
set_property "design_mode" "GateLvl" [current_fileset]

# Read the frozen inputs with this run's language and property choices.
add_files -quiet [dict get $::hdlforge_config input_dcp]
set input [::hdlforge::source_path "compilation/ip_example/latest/work/ip_sources/0/example.xcix"]
read_ip $input
set ip [get_ips -quiet [file rootname [file tail $input]]]
set matches {}
foreach candidate [get_files -quiet -all -of_objects $ip] {
    if {[string match "*/example_ooc.xdc" $candidate]} {lappend matches $candidate}
}
if {![llength $matches]} {error "Missing IP constraint example_ooc.xdc"}
set_property "used_in_implementation" false $matches
set input [::hdlforge::source_path "sources/XDC/implementation.xdc"]
read_xdc $input
set_property "processing_order" "LATE" [get_files $input]
link_design -top $top -part $part
## Optional: finish the message database opened for this stage.
# close_msg_db -file init_design.pb
unset ::ACTIVE_STEP

# Explore logical optimization and placement.
set ::ACTIVE_STEP opt_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db opt_design.pb
opt_design -directive Explore
# Save the completed design before generating reports.
write_checkpoint -force ${top}_opt.dcp
set_param project.isImplRun true
generate_parallel_reports -reports [list \
    "report_drc -file ${top}_drc_opted.rpt -pb ${top}_drc_opted.pb -rpx ${top}_drc_opted.rpx" \
]
set_param project.isImplRun false
## Optional: finish the message database opened for this stage.
# close_msg_db -file opt_design.pb
unset ::ACTIVE_STEP
set ::ACTIVE_STEP place_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db place_design.pb
if {[llength [get_debug_cores -quiet]]} {implement_debug_core}
set_param project.isImplRun true
place_design -directive Explore
set_param project.isImplRun false
# Save the completed design before generating reports.
write_checkpoint -force ${top}_placed.dcp
set_param project.isImplRun true
generate_parallel_reports -reports [list \
    "report_io -file ${top}_io_placed.rpt" \
    "report_utilization -file ${top}_utilization_placed.rpt -pb ${top}_utilization_placed.pb" \
    "report_control_sets -verbose -file ${top}_control_sets_placed.rpt" \
]
set_param project.isImplRun false
## Optional: finish the message database opened for this stage.
# close_msg_db -file place_design.pb
unset ::ACTIVE_STEP

# Optimize before routing, route, then optimize the routed design.
set ::ACTIVE_STEP phys_opt_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db phys_opt_design.pb
phys_opt_design -directive AggressiveExplore
# Save the completed design before generating reports.
write_checkpoint -force ${top}_physopt.dcp
## Optional: finish the message database opened for this stage.
# close_msg_db -file phys_opt_design.pb
unset ::ACTIVE_STEP
set ::ACTIVE_STEP route_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db route_design.pb
set_msg_config -source 4 -id {Route 35-39} -severity {critical warning} -new_severity warning
if {[catch {route_design -directive AggressiveExplore} route_error route_options]} {
    catch {write_checkpoint -force ${top}_routed_error.dcp}
    return -options $route_options $route_error
}
# Save the completed design before generating reports.
write_checkpoint -force ${top}_routed.dcp
set_param project.isImplRun true
generate_parallel_reports -reports [list \
    "report_drc -file ${top}_drc_routed.rpt -pb ${top}_drc_routed.pb -rpx ${top}_drc_routed.rpx" \
    "report_methodology -file ${top}_methodology_drc_routed.rpt -pb ${top}_methodology_drc_routed.pb -rpx ${top}_methodology_drc_routed.rpx" \
    "report_power -file ${top}_power_routed.rpt -pb ${top}_power_summary_routed.pb -rpx ${top}_power_routed.rpx" \
    "report_route_status -file ${top}_route_status.rpt -pb ${top}_route_status.pb" \
    "report_timing_summary -max_paths 10 -routable_nets -report_unconstrained -file ${top}_timing_summary_routed.rpt -pb ${top}_timing_summary_routed.pb -rpx ${top}_timing_summary_routed.rpx" \
    "report_incremental_reuse -file ${top}_incremental_reuse_routed.rpt" \
    "report_clock_utilization -file ${top}_clock_utilization_routed.rpt" \
    "report_bus_skew -warn_on_violation -file ${top}_bus_skew_routed.rpt -pb ${top}_bus_skew_routed.pb -rpx ${top}_bus_skew_routed.rpx" \
]
set_param project.isImplRun false
## Optional: finish the message database opened for this stage.
# close_msg_db -file route_design.pb
unset ::ACTIVE_STEP
set ::ACTIVE_STEP post_route_phys_opt_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db post_route_phys_opt_design.pb
phys_opt_design -directive AggressiveExplore
# Save the completed design before generating reports.
write_checkpoint -force ${top}_postroute_physopt.dcp
set_param project.isImplRun true
generate_parallel_reports -reports [list \
    "report_timing_summary -max_paths 10 -report_unconstrained -warn_on_violation -file ${top}_timing_summary_postroute_physopted.rpt -pb ${top}_timing_summary_postroute_physopted.pb -rpx ${top}_timing_summary_postroute_physopted.rpx" \
    "report_bus_skew -warn_on_violation -file ${top}_bus_skew_postroute_physopted.rpt -pb ${top}_bus_skew_postroute_physopted.pb -rpx ${top}_bus_skew_postroute_physopted.rpx" \
]
set_param project.isImplRun false
## Optional: finish the message database opened for this stage.
# close_msg_db -file post_route_phys_opt_design.pb
unset ::ACTIVE_STEP

# Put project-specific bitstream properties immediately before this command.
set ::ACTIVE_STEP write_bitstream
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db write_bitstream.pb
catch {write_mem_info -force -no_partial_mmi ${top}.mmi}
write_bitstream -force ${top}.bit
catch {write_debug_probes -quiet -force $top}
catch {file copy -force ${top}.ltx debug_nets.ltx}
## Optional: finish the message database opened for this stage.
# close_msg_db -file write_bitstream.pb
unset ::ACTIVE_STEP
