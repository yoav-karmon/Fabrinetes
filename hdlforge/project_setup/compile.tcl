# Get command-line arguments
set path_xpr        [lindex $argv 0]
set stage           [lindex $argv 1]
set synth_runs_str  [lindex $argv 2]
set impl_runs_str   [lindex $argv 3]
set param_string    [lindex $argv 4]
set define_string   [lindex $argv 5]

proc hdlforge_filter_nonempty { run_names } {
    set filtered {}
    foreach run_name $run_names {
        if { [string trim $run_name] ne "" } {
            lappend filtered [string trim $run_name]
        }
    }
    return $filtered
}

proc hdlforge_unique { run_names } {
    set unique_runs {}
    foreach run_name $run_names {
        if { [lsearch -exact $unique_runs $run_name] == -1 } {
            lappend unique_runs $run_name
        }
    }
    return $unique_runs
}

set synth_runs [hdlforge_unique [hdlforge_filter_nonempty [split $synth_runs_str " "]]]
set requested_impl_runs [hdlforge_unique [hdlforge_filter_nonempty [split $impl_runs_str " "]]]

# Vivado may return multiple objects for get_runs <name>; APIs need a single run.
proc hdlforge_one_run { run_name } {
    set matches [get_runs -quiet $run_name]
    set n [llength $matches]
    if { $n == 0 } {
        error "No Vivado run matched name: $run_name"
    }
    if { $n > 1 } {
        puts "(w) Multiple Vivado runs ($n) matched '$run_name'; using first"
    }
    return [lindex $matches 0]
}

proc hdlforge_safe_report_run { run_name } {
    if { $run_name eq "" } { return }
    set matches [get_runs -quiet $run_name]
    set n [llength $matches]
    if { $n == 0 } {
        puts "(w) No Vivado run matched for final report: $run_name"
        return
    }
    if { $n > 1 } {
        puts "(w) Multiple Vivado runs ($n) matched '$run_name' for final report; reporting first"
    }
    report_property [lindex $matches 0]
}

proc hdlforge_validate_synth_runs { synth_runs } {
    if { [llength $synth_runs] == 0 } {
        error "At least one synthesis run must be provided"
    }
    foreach synth_run $synth_runs {
        set run_obj [hdlforge_one_run $synth_run]
        set is_synth [get_property IS_SYNTHESIS $run_obj]
        if { $is_synth != 1 } {
            error "Run '$synth_run' is not a synthesis run"
        }
    }
}

proc hdlforge_run_needs_work { run_name } {
    set run_obj [hdlforge_one_run $run_name]
    set progress [get_property PROGRESS $run_obj]
    set need_refresh [get_property NEEDS_REFRESH $run_obj]
    set status [get_property STATUS $run_obj]
    set status_lower [string tolower $status]
    set is_complete [string match "*complete*" $status_lower]
    set is_100_percent [string match "100%*" $progress]
    set needs_work [expr { $is_complete == 0 || $need_refresh == 1 || $is_100_percent == 0 }]
    return [list $needs_work $status $progress $need_refresh]
}

proc hdlforge_collect_impl_children { synth_runs } {
    set impl_child_runs {}
    foreach run_obj [get_runs] {
        set run_name [get_property NAME $run_obj]
        set parent [get_property PARENT $run_obj]
        set is_impl [get_property IS_IMPLEMENTATION $run_obj]
        if { $is_impl == 1 && [lsearch -exact $synth_runs $parent] != -1 } {
            if { [lsearch -exact $impl_child_runs $run_name] == -1 } {
                lappend impl_child_runs $run_name
            }
        }
    }
    return $impl_child_runs
}

proc hdlforge_validate_impl_runs { impl_runs synth_runs } {
    set validated {}
    foreach impl_run $impl_runs {
        set run_obj [hdlforge_one_run $impl_run]
        set is_impl [get_property IS_IMPLEMENTATION $run_obj]
        if { $is_impl != 1 } {
            error "Run '$impl_run' is not an implementation run"
        }
        set parent [get_property PARENT $run_obj]
        if { [lsearch -exact $synth_runs $parent] == -1 } {
            error "Implementation run '$impl_run' is not a child of requested synth runs: $synth_runs"
        }
        lappend validated $impl_run
    }
    return [hdlforge_unique $validated]
}

proc hdlforge_launch_runs_parallel { run_names to_step jobs label } {
    if { [llength $run_names] == 0 } {
        puts "(i) No $label runs need launching"
        return
    }

    puts "(i) Launching [llength $run_names] $label run(s) in parallel: $run_names"
    foreach run_name $run_names {
        set run_obj [hdlforge_one_run $run_name]
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
        set run_obj [hdlforge_one_run $run_name]
        puts "(i) Waiting for $label run $run_index ($run_name) to complete..."
        wait_on_run $run_obj
        incr run_index
    }
}

puts "(i) print all arguments"
puts "=========== TCL Arguments ==========="
puts "Project file:         $path_xpr"
puts "Stage:                $stage"
puts "Synthesis runs:       $synth_runs"
puts "Implementation runs:  $requested_impl_runs"
puts "Parameters:           $param_string"
puts "Defines:              $define_string"
puts "====================================="

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file

hdlforge_validate_synth_runs $synth_runs

set all_impl_runs {}

puts "================== stage = synthesis =================="

set synth_runs_to_launch {}
set synth_runs_rebuilt {}
set synth_runs_missing_prereq {}
foreach synth_run $synth_runs {
    lassign [hdlforge_run_needs_work $synth_run] needs_work status progress need_refresh
    puts "(i) $synth_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"
    if { $needs_work } {
        if { $stage == "syn" || $stage == "all" } {
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

if { ($stage == "impl" || $stage == "bit") && [llength $synth_runs_missing_prereq] > 0 } {
    error "Cannot run $stage because these synth runs are not complete and up-to-date: $synth_runs_missing_prereq"
}

if { $stage == "syn" || $stage == "all" } {
    hdlforge_launch_runs_parallel $synth_runs_to_launch synth_design 4 "synthesis"
    hdlforge_wait_for_runs $synth_runs_to_launch "synthesis"
} else {
    puts "(!) Skipping synthesis stage"
}
puts "======================================================"
puts ""

puts "================== stage = Implementation ============"

set discovered_impl_runs [hdlforge_collect_impl_children $synth_runs]
if { [llength $requested_impl_runs] == 0 } {
    set all_impl_runs $discovered_impl_runs
} else {
    set all_impl_runs [hdlforge_validate_impl_runs $requested_impl_runs $synth_runs]
}

if { $stage == "all" && [llength $all_impl_runs] == 0 } {
    puts "(i) No child implementation runs found for synth runs: $synth_runs"
}

if { $stage == "impl" || $stage == "bit" || $stage == "all" } {
    set impl_runs_to_launch {}
    set impl_to_step "write_bitstream"
    set impl_jobs 4
    if { $stage == "bit" } {
        set impl_jobs 52
    }

    foreach impl_run $all_impl_runs {
        if { [lsearch -exact $synth_runs_rebuilt [get_property PARENT [hdlforge_one_run $impl_run]]] != -1 } {
            puts "(!) Resetting child implementation run because parent synth was rebuilt: $impl_run"
            reset_runs $impl_run
            lappend impl_runs_to_launch $impl_run
            continue
        }

        lassign [hdlforge_run_needs_work $impl_run] needs_work status progress need_refresh
        puts "(i) $impl_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"
        if { $needs_work } {
            puts "(!) Resetting implementation run before launch: $impl_run"
            reset_runs $impl_run
            lappend impl_runs_to_launch $impl_run
        } else {
            puts "(!) Skipping $impl_run (complete and successful)"
        }
    }

    hdlforge_launch_runs_parallel $impl_runs_to_launch $impl_to_step $impl_jobs "implementation"
    hdlforge_wait_for_runs $impl_runs_to_launch "implementation"
} else {
    puts "(!) Skipping implementation stage"
}

puts "======================================================"
puts ""

puts "(i) Final status report"
puts "==================== Final run statuses ===================="
foreach synth_run $synth_runs {
    puts "$synth_run: status"
    hdlforge_safe_report_run $synth_run
}
foreach impl_run $all_impl_runs {
    puts "$impl_run: status"
    hdlforge_safe_report_run $impl_run
}
puts "============================================================"

puts "(i) tcl script completed."

