# Parse command-line arguments
set project_name [lindex $argv 0]
set project_path [lindex $argv 1]
set synth_name "synth_Performance_Explore"

#project_file
set project_file "${project_path}/${project_name}/$project_name.xpr"

# Open project
open_project $project_file


# Run synthesis
puts "INFO: Running synthesis..."
launch_runs synth_Performance_Explore -to_step synth_design -jobs 10
wait_on_run synth_Performance_Explore

# Save and close project
puts "INFO: Synthesis completed for project '$project_name'."
