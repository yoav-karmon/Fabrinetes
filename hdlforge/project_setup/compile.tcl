# Get command-line arguments
set path_xpr        [lindex $argv 0]
set stage           [lindex $argv 1]
set synth_runs_str  [lindex $argv 2]
set impl_runs_str   [lindex $argv 3]
set define_string          [lindex $argv 4]
set more_options_json_list [lrange $argv 5 end]

set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir project_management_helpers.tcl]

set more_options_supplied [expr {[llength $more_options_json_list] != 0}]
set requested_more_options ""
if {$more_options_supplied} {
    package require json
    set more_options_entries {}
    foreach more_options_json $more_options_json_list {
        if {[string index [string trimleft $more_options_json] 0] ne "\["} {
            error "MORE OPTIONS must be a JSON array of strings"
        }
        if {[catch {set decoded_entries [json::json2dict $more_options_json]} json_error]} {
            error "Invalid MORE OPTIONS JSON: $json_error"
        }
        foreach more_option $decoded_entries {
            if {[string trim $more_option] eq ""} {
                error "MORE OPTIONS entries must be non-empty strings"
            }
            lappend more_options_entries $more_option
        }
    }
    set requested_more_options [join $more_options_entries " "]
}

set synth_runs [hdlforge::project::normalize_run_names $synth_runs_str]
set requested_impl_runs [hdlforge::project::normalize_run_names $impl_runs_str]

proc hdlforge_launch_runs_parallel { run_names to_step jobs label } {
    if { [llength $run_names] == 0 } {
        puts "(i) No $label runs need launching"
        return
    }

    puts "(i) Launching [llength $run_names] $label run(s) in parallel: $run_names"
    foreach run_name $run_names {
        set run_obj [hdlforge::project::one_run $run_name]
        puts "  Launching $run_name to step $to_step with -jobs $jobs"
        launch_runs $run_name -to_step $to_step -jobs $jobs
        set run_dir [get_property DIRECTORY $run_obj]
        set log_file [file join $run_dir "runme.log"]
        puts "    Log: $log_file"
        puts "    Live view: tail -f $log_file"
    }
}

proc hdlforge_wait_for_runs { run_names label } {
    set run_index 0
    foreach run_name $run_names {
        set run_obj [hdlforge::project::one_run $run_name]
        puts "(i) Waiting for $label run $run_index ($run_name) to complete..."
        set wait_rc [catch {wait_on_run $run_obj} wait_msg]
        if { $wait_rc != 0 } {
            set status [get_property STATUS $run_obj]
            set progress [get_property PROGRESS $run_obj]
            set run_dir [get_property DIRECTORY $run_obj]
            set log_file [file join $run_dir "runme.log"]
            puts ""
            puts "\[!x!\] Vivado $label run failed: $run_name"
            puts "      Status:   $status"
            puts "      Progress: $progress"
            puts "      Log:      $log_file"
            puts "      Reason:   $wait_msg"
            puts ""
            puts "      Check the log above or run:"
            puts "        tail -120 $log_file"
            close_project
            exit 1
        }
        incr run_index
    }
}

puts "(i) print all arguments"
puts "=========== TCL Arguments ==========="
puts "Project file:         $path_xpr"
puts "Stage:                $stage"
puts "Synthesis runs:       $synth_runs"
puts "Implementation runs:  $requested_impl_runs"
puts "More options JSON:    [expr {$more_options_supplied ? $more_options_json_list : "(unchanged)"}]"
puts "Defines:              $define_string"
puts "====================================="

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file

hdlforge::project::validate_synth_runs $synth_runs

set all_impl_runs {}

puts "================== stage = synthesis =================="

set synth_runs_to_launch {}
set synth_runs_rebuilt {}
set synth_runs_missing_prereq {}
set completion_stamp_paths {}
foreach synth_run $synth_runs {
    if {$stage eq "reset_synth"} {
        puts "(!) Resetting synthesis run: $synth_run"
        reset_runs $synth_run
        continue
    }

    set more_options_changed 0
    if {$more_options_supplied} {
        if {$stage ne "syn" && $stage ne "all" && $stage ne "continue"} {
            error "MORE OPTIONS can only be changed during syn, all, or continue"
        }
        set synth_run_obj [hdlforge::project::one_run $synth_run]
        set current_more_options [get_property {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} $synth_run_obj]
        if {$current_more_options ne $requested_more_options} {
            puts "(!) Resetting synthesis run before changing MORE OPTIONS: $synth_run"
            reset_runs $synth_run
            hdlforge::project::set_synth_more_options $synth_run $requested_more_options
            puts "(i) $synth_run MORE OPTIONS: $requested_more_options"
            set more_options_changed 1
        } else {
            puts "(i) $synth_run MORE OPTIONS unchanged"
        }
    }

    lassign [hdlforge::project::run_needs_work $synth_run] needs_work status progress need_refresh
    puts "(i) $synth_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"
    if {$more_options_changed} {
        lappend synth_runs_to_launch $synth_run
        lappend synth_runs_rebuilt $synth_run
    } elseif { $stage == "all" } {
        puts "(!) Resetting synthesis run for full rebuild: $synth_run"
        reset_runs $synth_run
        lappend synth_runs_to_launch $synth_run
        lappend synth_runs_rebuilt $synth_run
    } elseif { $needs_work } {
        if { $stage == "syn" || $stage == "continue" } {
            puts "(!) Resetting synthesis run before launch: $synth_run"
            reset_runs $synth_run
            lappend synth_runs_to_launch $synth_run
            lappend synth_runs_rebuilt $synth_run
        } else {
            puts "(!) Synth run needs work, but synthesis stage was not requested: $synth_run"
            lappend synth_runs_missing_prereq $synth_run
        }
    } else {
        puts "(!) Skipping $synth_run (complete and successful)"
    }
}

if { ($stage == "impl" || $stage == "impl_and_bitstream" || $stage == "bit") && [llength $synth_runs_missing_prereq] > 0 } {
    error "Cannot run $stage because these synth runs are not complete and up-to-date: $synth_runs_missing_prereq"
}

if { $stage == "syn" || $stage == "all" || $stage == "continue" } {
    hdlforge_launch_runs_parallel $synth_runs_to_launch synth_design 4 "synthesis"
    hdlforge_wait_for_runs $synth_runs_to_launch "synthesis"
    foreach synth_run $synth_runs_to_launch {
        lappend completion_stamp_paths [hdlforge::project::completion_stamp_path $synth_run synth]
    }
} else {
    puts "(!) Skipping synthesis stage"
}
puts "======================================================"
puts ""

puts "================== stage = Implementation ============"

set discovered_impl_runs [hdlforge::project::collect_impl_children $synth_runs]
if { [llength $requested_impl_runs] == 0 } {
    set all_impl_runs $discovered_impl_runs
} else {
    set all_impl_runs [hdlforge::project::validate_impl_runs $requested_impl_runs $synth_runs]
}

if { ($stage == "all" || $stage == "continue") && [llength $all_impl_runs] == 0 } {
    puts "(i) No child implementation runs found for synth runs: $synth_runs"
}

if {$stage == "reset_impl"} {
    foreach impl_run $all_impl_runs {
        puts "(!) Resetting implementation run: $impl_run"
        reset_runs $impl_run
    }
} elseif {$stage == "reset_bitstream"} {
    foreach impl_run $all_impl_runs {
        puts "(!) Resetting only write_bitstream: $impl_run"
        reset_runs $impl_run -from_step write_bitstream
    }
} elseif { $stage == "impl" || $stage == "impl_and_bitstream" || $stage == "bit" || $stage == "all" || $stage == "continue" } {
    set impl_runs_to_launch {}
    set impl_to_step [expr {$stage eq "impl" ? "route_design" : "write_bitstream"}]
    set impl_jobs 4
    if { $stage == "bit" } {
        set impl_jobs 52
    }

    foreach impl_run $all_impl_runs {
        if { [lsearch -exact $synth_runs_rebuilt [get_property PARENT [hdlforge::project::one_run $impl_run]]] != -1 } {
            puts "(!) Resetting child implementation run because parent synth was rebuilt: $impl_run"
            reset_runs $impl_run
            lappend impl_runs_to_launch $impl_run
            continue
        }

        lassign [hdlforge::project::impl_status $impl_run] impl_needs_work impl_status progress need_refresh
        puts "(i) $impl_run implementation: $impl_status (PROGRESS: $progress), needs_refresh: $need_refresh"
        if { $impl_needs_work } {
            if {$stage eq "bit"} {
                error "Cannot generate bitstream because implementation is not complete and fresh: $impl_run"
            }
            puts "(!) Resetting implementation run before launch: $impl_run"
            reset_runs $impl_run
            lappend impl_runs_to_launch $impl_run
            continue
        }

        if {$stage eq "impl"} {
            puts "(!) Skipping $impl_run (implementation complete, successful, and fresh)"
            continue
        }

        lassign [hdlforge::project::bitstream_needs_work $impl_run] bitstream_needs_work bitstream_status progress need_refresh
        puts "(i) $impl_run bitstream: $bitstream_status (PROGRESS: $progress), needs_refresh: $need_refresh"
        if { $bitstream_needs_work } {
            puts "(!) Implementation is good; resetting only write_bitstream before launch: $impl_run"
            reset_runs $impl_run -from_step write_bitstream
            lappend impl_runs_to_launch $impl_run
        } else {
            puts "(!) Skipping $impl_run (implementation and bitstream complete, successful, and fresh)"
        }
    }

    hdlforge_launch_runs_parallel $impl_runs_to_launch $impl_to_step $impl_jobs "implementation"
    hdlforge_wait_for_runs $impl_runs_to_launch "implementation"
    foreach impl_run $impl_runs_to_launch {
        lappend completion_stamp_paths [hdlforge::project::completion_stamp_path $impl_run impl]
        if {$impl_to_step eq "write_bitstream"} {
            lappend completion_stamp_paths [hdlforge::project::completion_stamp_path $impl_run bitstream]
        }
    }
} else {
    puts "(!) Skipping implementation stage"
}

puts "======================================================"
puts ""

puts "(i) Final status report"
puts "==================== Final run statuses ===================="
foreach synth_run $synth_runs {
    puts "$synth_run: status"
    hdlforge::project::safe_report_run $synth_run
}
foreach impl_run $all_impl_runs {
    puts "$impl_run: status"
    hdlforge::project::safe_report_run $impl_run
}
puts "============================================================"

puts "(i) tcl script completed."
close_project
hdlforge::project::write_completion_stamps $completion_stamp_paths
exit 0
