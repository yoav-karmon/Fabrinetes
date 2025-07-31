# Check if enough arguments are provided
if { $argc < 2 } {
    puts "Usage: vivado -mode tcl -source open_vivado_project.tcl -tclargs <project.xpr> <repo_top_path>"
    exit 1
}

# Get arguments
set project_xpr [lindex $argv 0]
set repo_top [lindex $argv 1]

# Open the Vivado project
open_project $project_xpr

# Get list of all VHDL source files
set source_files [get_files -filter { FILE_TYPE == "VHDL 2008" }]

# Open a file to write the sources
set output_file [open "sources.txt" "w"]

# Process and write each VHDL file to sources.txt
foreach file $source_files {
    # Replace occurrences of REPO_TOP in file paths
    set modified_file [string map [list $repo_top "\$REPO_TOP"] $file]
    
    # Write to file
    puts $output_file $modified_file
}

# Close the file
close $output_file

# Print a completion message
puts "VHDL sources have been saved to sources.txt with REPO_TOP substitutions."

# Close the project
close_project
exit
