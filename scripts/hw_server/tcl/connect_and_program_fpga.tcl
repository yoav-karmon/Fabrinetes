#!/usr/bin/env vivado -mode batch -source
# ============================================================================
# Hardware Server Connection and FPGA Programmer
# ============================================================================
# Usage:
#   vivado -mode batch -source connect_and_program_fpga.tcl [server_ip] [bitstream_path] [probes_path]
#   vivado -mode batch -notrace -source connect_and_program_fpga.tcl [server_ip] [bitstream_path] [probes_path]
# ============================================================================

# Source helper functions
source [file join [file dirname [info script]] hw_server_helpers.tcl]

# Parse arguments
set hw_server_ip [expr {$argc >= 1 ? [lindex $argv 0] : "10.1.130.74"}]
set bitstream_path [expr {$argc >= 2 ? [lindex $argv 1] : ""}]
set probes_path [expr {$argc >= 3 ? [lindex $argv 2] : ""}]

# Main execution
puts "=========================================="
puts "Hardware Server FPGA Programming Script"
puts "=========================================="
puts "Server IP: $hw_server_ip"
if { $bitstream_path != "" } {
    puts "Bitstream: $bitstream_path"
}
if { $probes_path != "" } {
    puts "Probes: $probes_path"
}
puts ""

# Initialize hardware server connection
set hw_device [init_hw_server $hw_server_ip]

# Program the FPGA
if { [catch {program_fpga_device $hw_device $bitstream_path $probes_path} result] } {
    puts "ERROR: Failed to program FPGA: $result"
    exit 1
}

puts ""
puts "Script completed successfully"

