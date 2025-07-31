# ===============================
# TCL Script to Embed or Read Commit Hash from Bitstream
# Usage: vivado -mode batch -source embed.tcl -tclargs <XPR_PATH> <READ_OR_WRITE> [HASH]
# - XPR_PATH: Path to the Vivado project file (.xpr)
# - READ_OR_WRITE: "r" for reading, "w" for writing
# - HASH (optional): The commit hash (only required when writing)
# ===============================

# ===============================
# Validate Arguments
# ===============================
if { $argc < 2 } {
    puts "ERROR: Incorrect usage. Expected arguments: <XPR_PATH> <r|w> [HASH]"
    exit 1
}

set xpr_path [lindex $argv 0]    
set operation [lindex $argv 1]   
set run [lindex $argv 2] 
set hash [lindex $argv 3]
set filename [lindex $argv 4]





# ===============================
# Handle Write Operation ("w")
# ===============================
if { $operation eq "w" } {
    if { $argc < 3 } {
        puts "ERROR: Missing HASH argument for write operation."
        exit 1
    }
        
    set commit_hash [lindex $argv 2]  
    open_project $xpr_path
    open_run [get_runs $run]
    set_property BITSTREAM.CONFIG.USERID $hash [current_design]
    write_bitstream -force $filename
    puts "Commit hash embedded successfully: $hash into $filename"
    exit 0
}

# ===============================
# Handle Read Operation ("r")
# ===============================
if { $operation eq "r" } {
    # Open Hardware Manager
    open_hw
    connect_hw_server

    # Read Bitstream Metadata
    read_bitstream my_design.bit
    set embedded_hash [get_property BITSTREAM.GENERAL.COMMENT [current_hw_device]]

    # Print the extracted commit hash
    puts "Commit hash in bitstream: $embedded_hash"

    exit 0
}

# ===============================
# Invalid Operation Argument
# ===============================
puts "ERROR: Invalid operation '$operation'. Use 'r' for read or 'w' for write."
exit 1