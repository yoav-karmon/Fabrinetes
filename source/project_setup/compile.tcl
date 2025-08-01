set path_xpr [lindex $argv 0]
set stage [lindex $argv 1]
set project_file "${path_xpr}"
puts "Project file: $project_file"
open_project $project_file



puts "==================stage=$stage=========================="
set doing_run 0
if { $stage == "syn" || $stage == "all" } {

    puts "Launching all synthesis runs..."

    foreach synth_run [get_runs -filter {IS_SYNTHESIS == True}] {
        set progress [get_property PROGRESS [get_runs $synth_run]]
        set need_refresh [get_property NEEDS_REFRESH [get_runs $synth_run]]
        set status [get_property STATUS [get_runs $synth_run]]
        set status_lower [string tolower $status]
        puts "$synth_run: $status (PROGRESS: $progress) , needs_refresh: $need_refresh"
        if { [string match "*complete*" $status_lower] == 0 || $need_refresh == 1 } {
            puts "Resetting and launching synthesis run: $synth_run"
            set doing_run 1
            reset_runs $synth_run
            launch_runs $synth_run -to_step synth_design -jobs 4
        } else {
            puts "Skipping $synth_run (STATUS: $status)"
        }
    }
    if { $doing_run == 0 } {
        puts "No synthesis runs to launch."
    } else {
        puts "Waiting for synthesis runs to complete..."
        wait_on_run [get_runs -filter {IS_SYNTHESIS == True}]
    }
} else {
    puts "Skipping synthesis stage."
}

puts "========================================================"


puts "====================stage=$stage========================="
if { $stage == "impl" || $stage == "all" } {

    # Launch all implementation runs
    puts "Launching all implementation runs..."
    foreach impl_run [get_runs -filter {IS_IMPLEMENTATION == True}] {
        set status [get_property STATUS [get_runs $impl_run]]
        set need_refresh [get_property NEEDS_REFRESH [get_runs $impl_run]]
        set status_lower [string tolower $status]
        puts "$impl_run: $status (PROGRESS: $progress) , needs_refresh: $need_refresh"
        if { $need_refresh == 1 || [string match "*complete*" $status_lower] == 0 } {
            puts "Resetting and launching impl run: $impl_run"
            reset_runs $impl_run
            launch_runs $impl_run -to_step write_bitstream -jobs 4
        } else {
            puts "Skipping $impl_run (STATUS: $status)"
        }
        
    }
    wait_on_run [get_runs -filter {IS_IMPLEMENTATION == True}]
} else {
    puts "Skipping implementation stage."
}
puts "========================================================"



if { $stage == "bitstream"} {
    puts "====================stage=$stage========================="
    # Launch all implementation runs
    puts "Launching all implementation runs..."
    foreach impl_run [get_runs -filter {IS_IMPLEMENTATION == True}] {
       write_bitstream -force [get_runs $impl_run]
    }
    wait_on_run [get_runs -filter {IS_IMPLEMENTATION == True}]
    puts "========================================================"
}




puts "====================Final runs status======================"
foreach run [get_runs] {
    puts "$run: [get_property STATUS [get_runs $run]]"
    set needs_refresh [get_property NEEDS_REFRESH [get_runs $run]]
    puts "  Needs refresh: $needs_refresh"
}
puts "========================================================"
