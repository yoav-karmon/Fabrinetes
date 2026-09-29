##############################################################################
## See the injected README.md beside this script for setup and build commands.
## HDLForge snapshots the source IP and regenerates a private working copy.
## Outputs remain in this timestamped run. HDLForge resolves latest logically.
##############################################################################

##############################################################################
## Load the JSON-selected IP from the private copy made by HDLForge.
## No saved project is opened. Source IP files are never regenerated in place.
##############################################################################
::hdlforge::initialize_design

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
