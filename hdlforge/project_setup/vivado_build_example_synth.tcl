##############################################################################
## See the injected README.md beside this script for setup and build commands.
## HDLForge snapshots these inputs, plus declared implementation inputs,
## before this script starts. Build ip_example first to populate latest.
##############################################################################

set top [dict get $::hdlforge_config top]
set part [dict get $::hdlforge_config part]

# Initialize the in-memory project and read the JSON source/IP/XDC lists.
::hdlforge::initialize_design

# Timing-oriented synthesis. These are run choices, not executor defaults.
set ::ACTIVE_STEP synth_design
##############################################################################
## Optional: record structured stage messages for Vivado GUI filtering.
## Text logs already contain the messages. Remove this and its matching
## close_msg_db command if you do not need a stage message database.
##############################################################################
# create_msg_db synth_design.pb
synth_design -top $top -part $part -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -verilog_define [dict get $::hdlforge_config defines]
set_param constraints.enableBinaryConstraints false
# Save the completed design before generating reports.
write_checkpoint -force -noxdef ${top}.dcp
generate_parallel_reports -reports [list \
    "report_utilization -file ${top}_utilization_synth.rpt -pb ${top}_utilization_synth.pb" \
]
## Optional: finish the message database opened for this stage.
# close_msg_db -file synth_design.pb
unset ::ACTIVE_STEP
