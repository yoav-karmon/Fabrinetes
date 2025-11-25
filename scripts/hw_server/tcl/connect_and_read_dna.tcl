#!/usr/bin/env vivado -mode batch -source
# ============================================================================
# Hardware Server Connection and Chip DNA Reader
# ============================================================================
# Usage:
#   vivado -mode batch -source connect_and_read_dna.tcl [server_ip]
#   vivado -mode batch -notrace -source connect_and_read_dna.tcl [server_ip]
# ============================================================================

# Source helper functions
source [file join [file dirname [info script]] hw_server_helpers.tcl]
source [file join [file dirname [info script]] dna_helpers.tcl]

# Parse arguments
set hw_server_ip [expr {$argc >= 1 ? [lindex $argv 0] : "10.1.130.74"}]

# Main execution
puts "=========================================="
puts "Hardware Server Connection Script"
puts "=========================================="
puts "Server IP: $hw_server_ip"
puts ""

set hw_device [init_hw_server $hw_server_ip]

lassign [read_chip_dna $hw_device] chip_dna all_dna_values
display_dna_result $chip_dna $all_dna_values $hw_device

puts ""
puts "Script completed"
