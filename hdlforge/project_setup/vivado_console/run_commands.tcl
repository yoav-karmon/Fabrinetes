# Structured results travel separately from the complete Vivado transcript.
proc lvp_emit {values} {
    if {[info exists ::lvp_data_channel]} {
        set row {}
        dict for {key value} $values {
            lappend row [binary encode base64 -maxlen 0 [encoding convertto utf-8 $key]]
            lappend row [binary encode base64 -maxlen 0 [encoding convertto utf-8 $value]]
        }
        puts $::lvp_data_channel [join $row "\t"]
    } else {puts $values}
}

proc lvp_status {} {
    set info [dict create CONSOLE responsive PROJECT "" XPR "" DIRECTORY "" PART ""]
    if {[llength [get_projects -quiet]]} {
        set project [current_project]
        dict set info PROJECT $project
        dict set info XPR [_lvp_project_path]
        dict set info DIRECTORY [get_property DIRECTORY $project]
        dict set info PART [get_property PART $project]
    }
    lvp_emit $info
}

proc lvp_group_runs {name} {
    set parent [_lvp_run $name]
    if {![get_property IS_SYNTHESIS $parent]} {error "Group must name a synthesis run: $name"}
    set result [list $parent]
    foreach run [lsort [get_runs]] {
        if {[get_property IS_IMPLEMENTATION $run] && [get_property PARENT $run] eq $name} {lappend result $run}
    }
    return $result
}

proc lvp_enabled {run} {
    return [expr {[lsearch -exact [split [get_property DESCRIPTION $run] "\n"] {[HDLForge:disabled]}] < 0}]
}

proc lvp_assert_enabled {run} {
    if {![lvp_enabled $run]} {error "Run is disabled: $run"}
    if {[get_property IS_IMPLEMENTATION $run] && ![lvp_enabled [_lvp_run [get_property PARENT $run]]]} {error "Parent synthesis is disabled: $run"}
}

proc lvp_run_messages {run} {
    set result [dict create WARNINGS - CRITICAL_WARNINGS - ERRORS -]
    set path [file join [get_property DIRECTORY $run] runme.log]
    if {![file isfile $path] || ![file readable $path]} {return $result}
    set handle [open $path r]
    try {set contents [read $handle]} finally {close $handle}
    dict set result WARNINGS [regexp -all -line {^WARNING:} $contents]
    dict set result CRITICAL_WARNINGS [regexp -all -line {^CRITICAL WARNING:} $contents]
    dict set result ERRORS [regexp -all -line {^ERROR:} $contents]
    return $result
}

proc lvp_run_record {run mode} {
    set fields {NAME PARENT IS_SYNTHESIS STATUS PROGRESS CURRENT_STEP NEEDS_REFRESH}
    if {$mode in {list status}} {set fields {NAME PARENT STATUS PROGRESS CURRENT_STEP STATS.ELAPSED STATS.WNS STATS.TNS STATS.WHS STATS.THS STATS.TPWS STATS.FAILED_NETS NEEDS_REFRESH}}
    if {$mode eq "info"} {
        set fields {NAME PARENT PART FLOW STRATEGY SRCSET CONSTRSET DIRECTORY DESCRIPTION}
        # Read only properties this run exposes; stage flags differ by flow/version.
        foreach property [lsort [list_property $run]] {
            if {[string match STEPS.* $property]} {lappend fields $property}
        }
    }
    if {$mode eq "reuse"} {set fields {NAME STATUS NEEDS_REFRESH INCREMENTAL_CHECKPOINT AUTO_INCREMENTAL_CHECKPOINT}}
    if {$mode eq "verbose"} {set fields [lsort [list_property $run]]}
    set result [dict create]
    foreach field $fields {dict set result $field [get_property $field $run]}
    dict set result ENABLED [lvp_enabled $run]
    if {$mode in {list status}} {
        dict set result DIRECTORY [get_property DIRECTORY $run]
        set result [dict merge $result [lvp_run_messages $run]]
    }
    lvp_emit $result
}

proc lvp_get_runs {{mode list}} {
    _lvp_project
    # Each synthesis group stays together, including its child implementations.
    foreach run [lsort [get_runs]] {
        if {[get_property IS_SYNTHESIS $run]} {
            foreach member [lvp_group_runs $run] {lvp_run_record $member $mode}
        }
    }
}
proc lvp_get_groups {} {
    _lvp_project
    foreach run [lsort [get_runs]] {
        if {[get_property IS_SYNTHESIS $run]} {
            lvp_emit [dict create NAME $run CHILDREN [lrange [lvp_group_runs $run] 1 end] STATUS [get_property STATUS $run] ENABLED [lvp_enabled $run]]
        }
    }
}
proc lvp_active_group_status {{name ""}} {
    _lvp_project
    set parents {}
    if {$name ne ""} {
        set parents [list [lindex [lvp_group_runs $name] 0]]
    } else {
        foreach run [lsort [get_runs]] {
            if {[get_property IS_SYNTHESIS $run]} {lappend parents $run}
        }
    }
    foreach parent $parents {
        foreach run [lvp_group_runs $parent] {
            if {[regexp -nocase {running} [get_property STATUS $run]]} {
                lvp_run_status $run
            }
        }
    }
}
proc lvp_run_info {name {verbose 0}} {lvp_run_record [_lvp_run $name] [expr {$verbose ? "verbose" : "info"}]}
proc lvp_run_status {name} {lvp_run_record [_lvp_run $name] status}
proc lvp_group_info {name {verbose 0}} {foreach run [lvp_group_runs $name] {lvp_run_info $run $verbose}}
proc lvp_group_status {name} {foreach run [lvp_group_runs $name] {lvp_run_status $run}}
proc lvp_reuse_status {name} {lvp_run_record [_lvp_run $name] reuse}
proc lvp_clear_refresh {name} {set_property NEEDS_REFRESH false [_lvp_run $name]; lvp_reuse_status $name}

proc lvp_build_run {name {jobs 1} {bitstream 1} {reset 0}} {
    set run [_lvp_run $name]
    lvp_assert_enabled $run
    if {$jobs < 1} {error "jobs must be positive"}
    if {$reset} {reset_run $run}
    set args [list $run -jobs $jobs]
    if {$bitstream && [get_property IS_IMPLEMENTATION $run]} {lappend args -to_step write_bitstream}
    launch_runs {*}$args
    lvp_run_status $name
}
proc lvp_build_group {name {jobs 1} {bitstream 1} {reset 0}} {
    set group [lvp_group_runs $name]
    lvp_assert_enabled [lindex $group 0]
    if {$jobs < 1} {error "jobs must be positive"}
    if {$reset} {reset_run [lindex $group 0]}
    set children {}
    foreach run [lrange $group 1 end] {if {[lvp_enabled $run]} {lappend children $run}}
    if {![llength $children]} {lvp_build_run $name $jobs 0 0; return}
    set args [list $children -jobs $jobs]
    if {$bitstream} {lappend args -to_step write_bitstream}
    launch_runs {*}$args
    lvp_group_status $name
}
proc lvp_build_bitstream {name {jobs 1}} {
    if {![get_property IS_IMPLEMENTATION [_lvp_run $name]]} {error "Bitstream requires an implementation run"}
    lvp_build_run $name $jobs 1
}
proc lvp_stop_run {name} {terminate_runs [_lvp_run $name]; lvp_run_status $name}
proc lvp_run_properties {name} {
    set run [_lvp_run $name]
    foreach property [lsort [list_property $run]] {
        lvp_emit [dict create PROPERTY $property VALUE [get_property $property $run]]
    }
}
proc lvp_edit_run_property {name property value} {
    set run [_lvp_run $name]
    if {[regexp -nocase {running|queued} [get_property STATUS $run]]} {error "Run is active: $name"}
    if {$property ni [list_property $run]} {error "Unknown run property: $property"}
    set_property $property $value $run
    lvp_emit [dict create RUN $name PROPERTY $property VALUE [get_property $property $run]]
}
proc lvp_incremental {name enabled} {
    set run [_lvp_run $name]
    if {[regexp -nocase {running|queued} [get_property STATUS $run]]} {error "Run is active: $name"}
    # Clear a manual checkpoint so automatic on/off is unambiguous.
    set_property INCREMENTAL_CHECKPOINT {} $run
    set_property AUTO_INCREMENTAL_CHECKPOINT $enabled $run
    lvp_emit [dict create RUN $name AUTO_INCREMENTAL_CHECKPOINT [get_property AUTO_INCREMENTAL_CHECKPOINT $run] INCREMENTAL_CHECKPOINT [get_property INCREMENTAL_CHECKPOINT $run]]
}
proc lvp_stop_group {name} {terminate_runs {*}[lvp_group_runs $name]; lvp_group_status $name}
proc lvp_reset_run {name} {reset_run [_lvp_run $name]; lvp_run_status $name}
proc lvp_reset_group {name} {reset_run [lindex [lvp_group_runs $name] 0]; lvp_group_status $name}
proc lvp_set_enabled {name enabled {group 0}} {
    set runs [list [_lvp_run $name]]
    if {$group} {set runs [lvp_group_runs $name]}
    foreach run $runs {
        set lines {}
        foreach line [split [get_property DESCRIPTION $run] "\n"] {
            if {$line ni {{[HDLForge:enabled]} {[HDLForge:disabled]}}} {lappend lines $line}
        }
        lappend lines [expr {$enabled ? {[HDLForge:enabled]} : {[HDLForge:disabled]}}]
        set_property DESCRIPTION [join $lines "\n"] $run
        lvp_run_record $run list
    }
}

proc lvp_close_project {} {
    if {![llength [get_projects -quiet]]} {return}
    foreach run [get_runs] {
        if {[regexp -nocase {running|queued} [get_property STATUS $run]]} {error "Run is active: $run; stop it explicitly first"}
    }
    close_project
}
proc lvp_export {path} {
    _lvp_project
    write_project_tcl -force $path
    set handle [open $path a]
    foreach run [get_runs] {
        set desc [get_property DESCRIPTION $run]
        if {[regexp {\[HDLForge:(enabled|disabled)\]} $desc]} {puts $handle [format {%s [get_runs %s]} [list set_property DESCRIPTION $desc] [list $run]]}
    }
    close $handle
    lvp_emit [dict create EXPORTED [file normalize $path]]
}
proc lvp_generate {script project_dir origin} {
    if {[llength [get_projects -quiet]]} {error "Close the current project before generating"}
    set script [file normalize $script]
    set project_dir [file normalize $project_dir]
    if {[file exists $project_dir]} {
        set backup "${project_dir}.preserved-[clock microseconds]"
        file rename $project_dir $backup
        puts "Preserved existing project: $backup"
    }
    file mkdir [file dirname $project_dir]
    set previous [pwd]
    cd [file dirname $project_dir]
    set ::origin_dir_loc [file normalize $origin]
    set ::user_project_name [file tail $project_dir]
    set ::argv {}
    set ::argc 0
    try {uplevel #0 [list source $script]} finally {cd $previous}
    lvp_status
}
