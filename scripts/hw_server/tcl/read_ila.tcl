#!/usr/bin/env vivado -mode batch -source
# ============================================================================
# ILA Value Reader (TCL)
# ============================================================================
# Usage:
#   vivado -mode batch -notrace -source read_ila.tcl [server_ip] [bit_file] [ltx_file]
# ============================================================================

# Source helper functions
source [file join [file dirname [info script]] hw_server_helpers.tcl]
source [file join [file dirname [info script]] ila_helpers.tcl]

# Parse arguments
set hw_server_ip [expr {$argc >= 1 ? [lindex $argv 0] : "10.1.130.74"}]
set bit_file [expr {$argc >= 2 ? [lindex $argv 1] : ""}]
set ltx_file [expr {$argc >= 3 ? [lindex $argv 2] : ""}]

# Main execution
puts "=========================================="
puts "ILA Value Reader"
puts "=========================================="
puts "Server IP: $hw_server_ip"
if { $bit_file != "" } {
    puts "Bitstream: $bit_file"
}
if { $ltx_file != "" } {
    puts "Probe file: $ltx_file"
}
puts ""

if { $bit_file == "" || $ltx_file == "" } {
    puts "ERROR: Both bitstream and probe files are required"
    puts "Usage: vivado -mode batch -source read_ila.tcl [server_ip] [bit_file] [ltx_file]"
    exit 1
}

set hw_device [init_hw_server $hw_server_ip]

set probe_values [read_ila_values $hw_device $bit_file $ltx_file]
display_ila_values $probe_values

puts ""
puts "Script completed"


