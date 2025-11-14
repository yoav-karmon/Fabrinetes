# Usage:
# vivado -mode batch -source remove_file.tcl -tclargs <project.xpr> <file_path> <output.tcl>

if { $argc < 3 } {
    puts "Usage:"
    puts "  vivado -mode batch -source remove_file.tcl -tclargs <project.xpr> <file_path> <output.tcl>"
    exit 1
}

# Parse arguments
set project_path [lindex $argv 0]
set file_path [lindex $argv 1]
set output_tcl_path [lindex $argv 2]

# Open project
open_project $project_path

# Remove file from project
puts "Removing file: $file_path"
remove_files $file_path

# Write project TCL with all properties
write_project_tcl -force -all_properties -no_copy_sources -use_bd_files $output_tcl_path

# Close project
close_project

puts "\nSUCCESS: File removed and project TCL exported to: $output_tcl_path\n"
exit 0
