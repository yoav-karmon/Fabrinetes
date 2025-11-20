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

if { $stage == "syn" | $stage == "all" | $stage == "impl" | $stage == "bit" } {
    puts "(i) preparing synthesis run OPTIONS"
    set more_opts ""
    set run_obj [get_runs $synth_run]



    if { $define_string ne "" } {
        foreach define [split $define_string " "] {
            append more_opts " -verilog_define $define"
        }
    }

    if { $param_string ne "" } {
        foreach param [split $param_string " "] {
            append more_opts " -generic $param"
        }
    }
    puts "=================================================="
    puts "Current MORE_OPTIONS for synthesis run '$synth_run':"
    puts "$more_opts"
    puts "=================================================="

    puts "(i) Setting MORE_OPTIONS for $synth_run: $more_opts"
    set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value $more_opts -objects $run_obj
    puts "(i) Setting run properties for $synth_run"
    report_property  $run_obj

    puts "(i) processing stages: $stage"



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
        puts "(!) Resetting and launching synthesis run: $synth_run"
        puts "(!) Current run properties:"
        puts "======================================================"
        puts "setting current_run: $synth_run"
        current_run $run_obj
        reset_runs $synth_run
        launch_runs $synth_run -to_step synth_design -jobs 4
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


if { $stage == "impl" | $stage == "all" | $stage == "bit" } {
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
            
            if { $stage == "bit" } {
                # For bit stage, always run to write_bitstream (which includes impl if needed)
                # Run if not complete, or needs refresh, or not 100%, or need_refresh != 0
                if { $is_complete == 0 || $need_refresh == 1 || $is_100_percent == 0 } {
                    puts "Resetting and launching implementation run to bitstream: $impl_run"
                    reset_runs $impl_run
                    launch_runs $impl_run -to_step write_bitstream -jobs 4
                    wait_on_run $run_obj
                } else {
                    # Implementation is complete and successful, just write bitstream (no reset needed)
                    puts "Implementation complete. Writing bitstream for: $impl_run (no reset needed)"
                    launch_runs $impl_run -to_step write_bitstream -jobs 4
                    wait_on_run $run_obj
                }
            } else {
                # For impl or all stage, run implementation
                if { $is_complete == 0 || $need_refresh == 1 || $is_100_percent == 0 } {
                    puts "Resetting and launching implementation run: $impl_run"
                    reset_runs $impl_run
                    launch_runs $impl_run -to_step write_bitstream -jobs 4
                    wait_on_run $run_obj
                } else {
                    puts "Skipping $impl_run (STATUS: $status, PROGRESS: $progress, needs_refresh: $need_refresh - complete and successful)"
                }
            }
        }
    }
} else {
    puts "(!) Skipping implementation / bit stage"
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

