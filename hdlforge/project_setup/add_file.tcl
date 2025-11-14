# Usage:
# vivado -mode batch -source add_file.tcl -tclargs <project.xpr> <file_path> <output.tcl>

if { $argc < 3 } {
    puts "Usage:"
    puts "  vivado -mode batch -source add_file.tcl -tclargs <project.xpr> <file_path> <output.tcl>"
    exit 1
}

# Parse arguments
set project_path [lindex $argv 0]
set file_path [lindex $argv 1]
set output_tcl_path [lindex $argv 2]

# Open project
open_project $project_path

# Add file to project
puts "Adding file: $file_path"
add_files $file_path

# Update compile order
update_compile_order -fileset sources_1

# Write project TCL with all properties
write_project_tcl -force -all_properties -no_copy_sources -use_bd_files $output_tcl_path

# Close project
close_project

puts "\nSUCCESS: File added and project TCL exported to: $output_tcl_path\n"
exit 0

