# Usage:
# vivado -mode batch -source write_project_tcl.tcl -tclargs <project.xpr> <output.tcl>

if { $argc < 2 } {
    puts "Usage:"
    puts "  vivado -mode batch -source write_project_tcl.tcl -tclargs <project.xpr> <output.tcl>"
    exit 1
}

# Parse arguments
set project_path [lindex $argv 0]
set output_tcl_path [lindex $argv 1]

# Check project file exists
if {![file exists $project_path]} {
    puts "Error: Project file '$project_path' not found."
    exit 1
}

# Open project
open_project $project_path
# Remove board_part to avoid board definition warnings
set_property board_part {} [current_project]

# Write project TCL with all properties
write_project_tcl -force -all_properties -no_copy_sources -use_bd_files -dump_project_info $output_tcl_path

# Close project
close_project

puts "\nSUCCESS: Project TCL exported to: $output_tcl_path\n"
exit 0

