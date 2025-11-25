# Get command-line arguments
set path_xpr      [lindex $argv 0]
set stage         [lindex $argv 1]
set synth_run     [lindex $argv 2]
set impl_runs_str [lindex $argv 3]
set param_string  [lindex $argv 4]
set define_string [lindex $argv 5]

# Parse implementation runs (space-separated list)
set impl_runs [split $impl_runs_str " "]

puts "(i) print all arguments"
puts "=========== TCL Arguments ==========="
puts "Project file:     $path_xpr"
puts "Stage:            $stage"
puts "Synthesis run:    $synth_run"
puts "Implementation runs: $impl_runs"
puts "Parameters:       $param_string"
puts "Defines:          $define_string"
puts "====================================="

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file
puts "================== stage = synthesis =================="

if { $stage == "syn"  } {
    # Get the run object for the synthesis run
    set run_obj [get_runs $synth_run]
    
    set progress     [get_property PROGRESS $run_obj ]
    set need_refresh [get_property NEEDS_REFRESH $run_obj ]
    set status       [get_property STATUS $run_obj ]
    set status_lower [string tolower $status]

    puts "(i) $synth_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"

    # Check if synthesis is complete and successful
    # STATUS values: "Not Started", "Running", "Complete" (success), "Error" (failed)
    # Only skip if status is "Complete", progress is "100%", and need_refresh is 0
    set is_complete [string match "*complete*" $status_lower]
    set is_100_percent [string match "100%*" $progress]
    if { $is_complete == 0 || $need_refresh == 1 || $is_100_percent == 0 } {
        puts "(!) Resetting and launching synthesis run: $synth_run (this will reset all implementation runs as well)"
        puts "(!) Current run properties:"
        puts "======================================================"
        puts "setting current_run: $synth_run"
        current_run $run_obj
        reset_runs $synth_run
        launch_runs $synth_run -to_step synth_design -jobs 4
        set run_dir [get_property DIRECTORY $run_obj]
        set log_file [file join $run_dir "runme.log"]
        puts "To view live log output, run in another terminal: tail -f $log_file"
        wait_on_run $run_obj
       
    } else {
        puts "(!) Skipping $synth_run (STATUS: $status, PROGRESS: $progress, needs_refresh: $need_refresh - complete and successful)"
    }

} else {
    set run_obj [get_runs $synth_run]
    report_property  $run_obj
    puts "(!) Skipping synthesis stage"
}
puts "======================================================"
puts ""


puts "================== stage = Implementation ============"

if { $stage == "impl" } {
    # Implementation - run all enabled implementation runs
    foreach impl_run $impl_runs {
        if { $impl_run ne "" } {
            set run_obj [get_runs $impl_run]
            set progress     [get_property PROGRESS $run_obj]
            set need_refresh [get_property NEEDS_REFRESH $run_obj]
            set status       [get_property STATUS $run_obj]
            set status_lower [string tolower $status]

            puts "$impl_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"

            # Check if implementation is complete and successful
            # STATUS values: "Not Started", "Running", "Complete" (success), "Error" (failed)
            # Only skip if status is "Complete", progress is "100%", and need_refresh is 0
            set is_complete [string match "*complete*" $status_lower]
            set is_100_percent [string match "100%*" $progress]
            
            # For impl stage, run implementation
            if { $is_complete == 0 || $need_refresh == 1 || $is_100_percent == 0 } {
                puts "Resetting and launching implementation run: $impl_run"
                reset_runs $impl_run
                launch_runs $impl_run -to_step write_bitstream -jobs 4
                set run_dir [get_property DIRECTORY $run_obj]
                set log_file [file join $run_dir "runme.log"]
                puts "Run output will be captured here: $log_file"
                puts "To view live log output, run in another terminal: tail -f $log_file"
                wait_on_run $run_obj
            } else {
                puts "Skipping $impl_run (STATUS: $status, PROGRESS: $progress, needs_refresh: $need_refresh - complete and successful)"
            }
        }
    }
}


if { $stage == "bit" } {
    # Bit stage: Get child runs of synth run and process them
    puts "(i) Bit stage: Getting child implementation runs for synth run: $synth_run"
    
    # Get all runs and find children of synth_run that are implementation runs
    set all_runs [get_runs]
    set impl_child_runs {}
    foreach run_obj $all_runs {
        set run_name [get_property NAME $run_obj]
        set parent [get_property PARENT $run_obj]
        set is_impl [get_property IS_IMPLEMENTATION $run_obj]
        # Only include if parent matches synth_run and it's an implementation run
        if { $parent == $synth_run && $is_impl == 1 } {
            lappend impl_child_runs $run_name
        }
    }
    
    if { [llength $impl_child_runs] == 0 } {
        puts "(!) No child implementation runs found for synth run: $synth_run"
        puts "(!) Skipping bit stage"
    } else {
        puts "(i) Found [llength $impl_child_runs] child implementation run(s): $impl_child_runs"
        
        # Check if synth run needs reset
        set synth_run_obj [get_runs $synth_run]
        set synth_need_refresh [get_property NEEDS_REFRESH $synth_run_obj]
        set synth_status [get_property STATUS $synth_run_obj]
        set synth_status_lower [string tolower $synth_status]
        set synth_is_complete [string match "*complete*" $synth_status_lower]
        set synth_progress [get_property PROGRESS $synth_run_obj]
        set synth_is_100_percent [string match "100%*" $synth_progress]
        set synth_needs_reset [expr { $synth_is_complete == 0 || $synth_need_refresh == 1 || $synth_is_100_percent == 0 }]
        
        if { $synth_needs_reset } {
            puts "(i) Synth run $synth_run needs reset. Resetting all child runs first..."
            foreach child_run $impl_child_runs {
                set child_run_obj [get_runs $child_run]
                set child_parent [get_property PARENT $child_run_obj]
                if { $child_parent == $synth_run } {
                    puts "  Resetting child run: $child_run"
                    reset_runs $child_run
                }
            }
            puts "  Resetting synth run: $synth_run"
            reset_runs $synth_run
        }
        
        # Check each child impl run if it needs reset
        foreach child_run $impl_child_runs {
            set child_run_obj [get_runs $child_run]
            set child_parent [get_property PARENT $child_run_obj]
            if { $child_parent == $synth_run } {
                set child_need_refresh [get_property NEEDS_REFRESH $child_run_obj]
                set child_status [get_property STATUS $child_run_obj]
                set child_status_lower [string tolower $child_status]
                set child_is_complete [string match "*complete*" $child_status_lower]
                set child_progress [get_property PROGRESS $child_run_obj]
                set child_is_100_percent [string match "100%*" $child_progress]
                set child_needs_reset [expr { $child_is_complete == 0 || $child_need_refresh == 1 || $child_is_100_percent == 0 }]
                
                if { $child_needs_reset } {
                    puts "  Resetting child impl run: $child_run"
                    reset_runs $child_run
                }
            }
        }
        
        # Launch all child impl runs with write_bitstream
        puts "(i) Launching all child implementation runs to write_bitstream with -jobs 52"
        foreach child_run $impl_child_runs {
            set child_run_obj [get_runs $child_run]
            set child_parent [get_property PARENT $child_run_obj]
            if { $child_parent == $synth_run } {
                puts "  Launching: $child_run"
                launch_runs $child_run -to_step write_bitstream -jobs 52
            }
        }
        
        # Wait for each child run to complete sequentially
        set child_index 0
        foreach child_run $impl_child_runs {
            set child_run_obj [get_runs $child_run]
            set child_parent [get_property PARENT $child_run_obj]
            if { $child_parent == $synth_run } {
                puts "(i) Waiting for child run $child_index ($child_run) to complete..."
                set run_dir [get_property DIRECTORY $child_run_obj]
                set log_file [file join $run_dir "runme.log"]
                puts "Run output will be captured here: $log_file"
                puts "To view live log output, run in another terminal: tail -f $log_file"
                wait_on_run $child_run_obj
                incr child_index
            }
        }
    }
}


puts "======================================================"
puts ""

puts "(i) Final status report"
puts "==================== Final run statuses ===================="
puts "$synth_run status"
report_property  [get_runs $synth_run]
foreach impl_run $impl_runs {
    if { $impl_run ne "" } {
        puts "$impl_run: status"
        report_property  [get_runs $impl_run]
    }
}
puts "============================================================"

puts "(i) tcl script completed."

