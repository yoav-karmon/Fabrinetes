# Parse command-line arguments
set project_name [lindex $argv 0]
set project_path [lindex $argv 1]
set imp_path [lindex $argv 2]

#project_file
set project_file "${project_path}/${project_name}/$project_name.xpr"

# Open project
open_project $project_file


puts "INFO: Running $ $imp_path..."
launch_runs $imp_path -to_step write_bitstream -jobs 4
wait_on_run $imp_path

# Save and close project
puts "INFO: Impl completed for project '$project_name'."
