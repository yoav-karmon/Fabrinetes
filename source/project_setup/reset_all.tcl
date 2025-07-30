# Parse command-line arguments
set project_file [lindex $argv 0]

# Open project
open_project $project_file

puts "Launching all synthesis runs..."
foreach synth_run [get_runs -filter {IS_SYNTHESIS == True}] {
    set progress [get_property PROGRESS [get_runs $synth_run]]
    set status [get_property STATUS [get_runs $synth_run]]
    puts "*********Run $synth_run status = $status"
    puts "Resetting $synth_run..."
    reset_runs $synth_run
}

# Final status check
puts "Final run statuses:"
foreach run [get_runs] {
    puts "$run: [get_property STATUS [get_runs $run]]"
}
