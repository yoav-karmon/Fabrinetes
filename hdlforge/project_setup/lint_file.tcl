# Get command-line arguments
set path_xpr      [lindex $argv 0]
set file_path     [lindex $argv 1]

puts "(i) print all arguments"
puts "=========== TCL Arguments ==========="
puts "Project file:     $path_xpr"
puts "File to lint:     $file_path"
puts "====================================="

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file
# Remove board_part to avoid board definition warnings
set_property board_part {} [current_project]

puts "================== stage = lint_file =================="
puts "(i) Checking syntax for file: $file_path"

# Determine file type based on extension
set file_ext [string tolower [file extension $file_path]]

# Read file based on file type (Vivado will report syntax errors automatically)
# Note: If file is already in project, this will skip with a warning but errors will still be checked
if { [string match "*.sv" $file_path] || [string match "*.svh" $file_path] } {
    puts "(i) Reading SystemVerilog file for syntax check..."
    read_verilog -sv $file_path
} elseif { [string match "*.v" $file_path] } {
    puts "(i) Reading Verilog file for syntax check..."
    read_verilog $file_path
} elseif { [string match "*.vhd" $file_path] || [string match "*.vhdl" $file_path] } {
    puts "(i) Reading VHDL file for syntax check..."
    read_vhdl $file_path
} else {
    puts "WARNING: Unknown file extension. Attempting to read as SystemVerilog..."
    read_verilog -sv $file_path
}

puts "(i) File read completed. Any syntax errors or warnings were reported above."

puts ""
puts "=========================================="
puts "Single-file lint check completed!"
puts "=========================================="

# Get current working directory for log file location
set current_dir [pwd]
puts "Log files location: $current_dir"
puts "Vivado log: $current_dir/.Xil/Vivado-*/vivado.log"
puts "(Check the .Xil directory in the build folder for detailed logs)"
puts "=========================================="

puts "(i) tcl script completed."

exit

