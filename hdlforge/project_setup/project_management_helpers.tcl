namespace eval hdlforge::project {}

proc hdlforge::project::help {} {
    puts "Source project_management_helpers.tcl after opening a Vivado project."
    puts "  hdlforge::project::print_runs"
    puts "  hdlforge::project::run_info <run_name>"
    puts "  hdlforge::project::collect_impl_children {<synth_run> ...}"
    puts "  hdlforge::project::set_synth_more_options <synth_run> <options>"
    puts "  hdlforge::project::reset_synth {<synth_run> ...}"
    puts "  hdlforge::project::reset_impl {<synth_run> ...}"
    puts "  hdlforge::project::reset_bitstream {<synth_run> ...}"
}

proc hdlforge::project::filter_nonempty {values} {
    set filtered {}
    foreach value $values {
        set value [string trim $value]
        if {$value ne ""} {
            lappend filtered $value
        }
    }
    return $filtered
}

proc hdlforge::project::unique {values} {
    set unique_values {}
    foreach value $values {
        if {[lsearch -exact $unique_values $value] == -1} {
            lappend unique_values $value
        }
    }
    return $unique_values
}

proc hdlforge::project::normalize_run_names {run_names_string} {
    return [unique [filter_nonempty [split $run_names_string " "]]]
}

proc hdlforge::project::one_run {run_name} {
    set matches [get_runs -quiet $run_name]
    set match_count [llength $matches]
    if {$match_count == 0} {
        error "No Vivado run matched name: $run_name"
    }
    if {$match_count > 1} {
        puts "(w) Multiple Vivado runs ($match_count) matched '$run_name'; using first"
    }
    return [lindex $matches 0]
}

proc hdlforge::project::run_info {run_name} {
    set run_obj [one_run $run_name]
    set info [dict create]
    foreach property {NAME IS_SYNTHESIS IS_IMPLEMENTATION STATUS PROGRESS NEEDS_REFRESH PARENT DIRECTORY} {
        dict set info $property [get_property $property $run_obj]
    }
    if {[dict get $info IS_SYNTHESIS] == 1} {
        dict set info MORE_OPTIONS [get_property {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} $run_obj]
    } else {
        dict set info MORE_OPTIONS ""
    }
    return $info
}

proc hdlforge::project::list_runs {} {
    set runs {}
    foreach run_obj [get_runs] {
        lappend runs [run_info [get_property NAME $run_obj]]
    }
    return $runs
}

proc hdlforge::project::print_runs {} {
    puts "Run\tSynth\tImpl\tStatus\tProgress\tRefresh\tParent\tMoreOptions"
    foreach info [list_runs] {
        puts "[dict get $info NAME]\t[dict get $info IS_SYNTHESIS]\t[dict get $info IS_IMPLEMENTATION]\t[dict get $info STATUS]\t[dict get $info PROGRESS]\t[dict get $info NEEDS_REFRESH]\t[dict get $info PARENT]\t[dict get $info MORE_OPTIONS]"
    }
}

proc hdlforge::project::safe_report_run {run_name} {
    if {$run_name eq ""} {
        return
    }
    set matches [get_runs -quiet $run_name]
    set match_count [llength $matches]
    if {$match_count == 0} {
        puts "(w) No Vivado run matched for final report: $run_name"
        return
    }
    if {$match_count > 1} {
        puts "(w) Multiple Vivado runs ($match_count) matched '$run_name'; reporting first"
    }
    report_property [lindex $matches 0]
}

proc hdlforge::project::completion_stamp_path {run_name stage_name} {
    set run_dir [get_property DIRECTORY [one_run $run_name]]
    return [file join $run_dir ".hdlforge_${stage_name}_complete"]
}

proc hdlforge::project::completion_stamp_is_fresh {run_name stage_name} {
    set stamp_path [completion_stamp_path $run_name $stage_name]
    if {![file exists $stamp_path]} {
        return 0
    }

    set stamp_mtime [file mtime $stamp_path]
    set tracked_files [list {*}[get_files -quiet]]
    if {![catch {set project_file [get_property FILE_NAME [current_project]]}] && $project_file ne ""} {
        lappend tracked_files $project_file
    }

    set run_obj [one_run $run_name]
    if {[get_property IS_IMPLEMENTATION $run_obj] == 1} {
        set parent_name [get_property PARENT $run_obj]
        set parent_dir [get_property DIRECTORY [one_run $parent_name]]
        set source_set [get_filesets [get_property SRCSET [one_run $parent_name]]]
        lappend tracked_files [file join $parent_dir "[get_property TOP $source_set].dcp"]
    }

    foreach tracked_file [unique $tracked_files] {
        if {[file isfile $tracked_file] && [file mtime $tracked_file] > $stamp_mtime} {
            return 0
        }
    }
    return 1
}

proc hdlforge::project::effective_needs_refresh {run_name stage_name vivado_needs_refresh} {
    if {!$vivado_needs_refresh} {
        return 0
    }
    if {[completion_stamp_is_fresh $run_name $stage_name]} {
        puts "(i) $run_name: ignoring sticky NEEDS_REFRESH; no tracked input changed after the successful $stage_name stage"
        return 0
    }
    return 1
}

proc hdlforge::project::write_completion_stamps {stamp_paths} {
    foreach stamp_path [unique $stamp_paths] {
        set stamp_file [open $stamp_path w]
        puts $stamp_file "completed [clock seconds]"
        close $stamp_file
    }
}

proc hdlforge::project::validate_synth_runs {synth_runs} {
    if {[llength $synth_runs] == 0} {
        error "At least one synthesis run must be provided"
    }
    foreach synth_run $synth_runs {
        if {[get_property IS_SYNTHESIS [one_run $synth_run]] != 1} {
            error "Run '$synth_run' is not a synthesis run"
        }
    }
}

proc hdlforge::project::run_needs_work {run_name} {
    set info [run_info $run_name]
    set status [dict get $info STATUS]
    set progress [dict get $info PROGRESS]
    set needs_refresh [effective_needs_refresh $run_name synth [dict get $info NEEDS_REFRESH]]
    set status_lower [string tolower $status]
    set is_failed [expr {[string match "*error*" $status_lower] || [string match "*fail*" $status_lower]}]
    set is_100_percent [string match "100%*" $progress]
    set is_complete [expr {[string match "*complete*" $status_lower] || ($is_100_percent && [completion_stamp_is_fresh $run_name synth])}]
    set needs_work [expr {!$is_complete || $is_failed || $needs_refresh || !$is_100_percent}]
    return [list $needs_work $status $progress $needs_refresh]
}

proc hdlforge::project::impl_status {run_name} {
    set info [run_info $run_name]
    set status [dict get $info STATUS]
    set progress [dict get $info PROGRESS]
    set needs_refresh [effective_needs_refresh $run_name impl [dict get $info NEEDS_REFRESH]]
    set status_lower [string tolower $status]
    set is_failed [expr {[string match "*error*" $status_lower] || [string match "*fail*" $status_lower]}]
    set is_100_percent [string match "100%*" $progress]
    set is_complete [expr {[string match "route_design complete*" $status_lower] || [string match "write_bitstream complete*" $status_lower] || ($is_100_percent && [completion_stamp_is_fresh $run_name impl])}]
    set needs_work [expr {!$is_complete || $is_failed || !$is_100_percent || $needs_refresh}]
    return [list $needs_work $status $progress $needs_refresh]
}

proc hdlforge::project::bitstream_needs_work {run_name} {
    set info [run_info $run_name]
    set status [dict get $info STATUS]
    set progress [dict get $info PROGRESS]
    set needs_refresh [effective_needs_refresh $run_name bitstream [dict get $info NEEDS_REFRESH]]
    set status_lower [string tolower $status]
    set is_failed [expr {[string match "*error*" $status_lower] || [string match "*fail*" $status_lower]}]
    set is_100_percent [string match "100%*" $progress]
    set is_complete [expr {[string match "write_bitstream complete*" $status_lower] || ($is_100_percent && [completion_stamp_is_fresh $run_name bitstream])}]
    set needs_work [expr {!$is_complete || $is_failed || !$is_100_percent || $needs_refresh}]
    return [list $needs_work $status $progress $needs_refresh]
}

proc hdlforge::project::collect_impl_children {synth_runs} {
    set child_runs {}
    foreach run_obj [get_runs] {
        if {[get_property IS_IMPLEMENTATION $run_obj] != 1} {
            continue
        }
        if {[lsearch -exact $synth_runs [get_property PARENT $run_obj]] == -1} {
            continue
        }
        set run_name [get_property NAME $run_obj]
        if {[lsearch -exact $child_runs $run_name] == -1} {
            lappend child_runs $run_name
        }
    }
    return $child_runs
}

proc hdlforge::project::validate_impl_runs {impl_runs synth_runs} {
    set validated {}
    foreach impl_run $impl_runs {
        set run_obj [one_run $impl_run]
        if {[get_property IS_IMPLEMENTATION $run_obj] != 1} {
            error "Run '$impl_run' is not an implementation run"
        }
        if {[lsearch -exact $synth_runs [get_property PARENT $run_obj]] == -1} {
            error "Implementation run '$impl_run' is not a child of requested synth runs: $synth_runs"
        }
        lappend validated $impl_run
    }
    return [unique $validated]
}

proc hdlforge::project::set_synth_more_options {run_name more_options} {
    set run_obj [one_run $run_name]
    if {[get_property IS_SYNTHESIS $run_obj] != 1} {
        error "Run '$run_name' is not a synthesis run"
    }
    set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value $more_options -objects $run_obj
}

proc hdlforge::project::reset_synth {synth_runs} {
    validate_synth_runs $synth_runs
    foreach synth_run $synth_runs {
        reset_runs [one_run $synth_run]
    }
}

proc hdlforge::project::reset_impl {synth_runs} {
    validate_synth_runs $synth_runs
    foreach impl_run [collect_impl_children $synth_runs] {
        reset_runs [one_run $impl_run]
    }
}

proc hdlforge::project::reset_bitstream {synth_runs} {
    validate_synth_runs $synth_runs
    foreach impl_run [collect_impl_children $synth_runs] {
        reset_runs [one_run $impl_run] -from_step write_bitstream
    }
}
