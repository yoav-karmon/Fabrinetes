proc _lvp_project {} {
    set projects [get_projects -quiet]
    if {[llength $projects] == 0} {
        error "no project is open"
    }
    return [current_project]
}

proc _lvp_project_path {} {
    set project [_lvp_project]
    return [file normalize [file join \
        [get_property DIRECTORY $project] \
        "[get_property NAME $project].xpr"]]
}

proc _lvp_run {run_name} {
    set run [get_runs -quiet $run_name]
    if {$run eq ""} {
        error "run not found: $run_name"
    }
    return $run
}

proc _lvp_missing_run {run_name} {
    if {[get_runs -quiet $run_name] ne ""} {
        error "run already exists: $run_name"
    }
}

proc _lvp_reference_run {run_name type_property} {
    if {$run_name ne ""} {
        set run [_lvp_run $run_name]
        if {![get_property $type_property $run]} {
            error "run $run_name does not match required type $type_property"
        }
        return $run
    }

    foreach run [get_runs] {
        if {[get_property $type_property $run]} {
            return $run
        }
    }
    error "no reference run matches $type_property"
}

proc lvp_open_project {xpr_path} {
    if {[llength [get_projects -quiet]] != 0} {
        error "a project is already open: [current_project]"
    }

    set normalized_path [file normalize $xpr_path]
    if {![file isfile $normalized_path]} {
        error "XPR does not exist: $normalized_path"
    }

    open_project $normalized_path
    puts "opened project: $normalized_path"
}

proc lvp_info {} {
    set project [_lvp_project]
    puts "project: $project"
    puts "xpr: [_lvp_project_path]"
    puts "directory: [get_property DIRECTORY $project]"
    puts "part: [get_property PART $project]"
    puts "runs: [get_runs]"
}

proc lvp_runs {} {
    foreach run [get_runs] {
        if {[get_property IS_SYNTHESIS $run]} {
            set run_type "synth"
        } elseif {[get_property IS_IMPLEMENTATION $run]} {
            set run_type "impl"
        } else {
            set run_type "unknown"
        }

        puts [format "%-24s type=%-10s strategy=%s status=%s" \
            $run \
            $run_type \
            [get_property STRATEGY $run] \
            [get_property STATUS $run]]
    }
}

proc lvp_get_run_properties {run_name {property_names {}}} {
    set run [_lvp_run $run_name]
    if {[llength $property_names] == 0} {
        report_property $run
        return
    }

    foreach property_name $property_names {
        puts "$property_name=[get_property $property_name $run]"
    }
}

proc lvp_set_run_property {run_name property_name value} {
    set run [_lvp_run $run_name]
    set_property $property_name $value $run
    puts "$run_name $property_name=[get_property $property_name $run]"
}

proc lvp_create_synth_run {run_name {reference_run ""}} {
    _lvp_missing_run $run_name
    set reference [_lvp_reference_run $reference_run IS_SYNTHESIS]
    set project [_lvp_project]

    create_run \
        -name $run_name \
        -part [get_property PART $project] \
        -flow [get_property FLOW $reference] \
        -strategy [get_property STRATEGY $reference] \
        -report_strategy [get_property REPORT_STRATEGY $reference] \
        -constrset [get_property CONSTRSET $reference]
    puts "created synthesis run $run_name from $reference"
}

proc lvp_create_impl_run {run_name parent_run {reference_run ""}} {
    _lvp_missing_run $run_name
    set parent [_lvp_run $parent_run]
    if {![get_property IS_SYNTHESIS $parent]} {
        error "implementation parent is not a synthesis run: $parent_run"
    }

    set reference [_lvp_reference_run $reference_run IS_IMPLEMENTATION]
    set project [_lvp_project]
    create_run \
        -name $run_name \
        -part [get_property PART $project] \
        -flow [get_property FLOW $reference] \
        -strategy [get_property STRATEGY $reference] \
        -report_strategy [get_property REPORT_STRATEGY $reference] \
        -constrset [get_property CONSTRSET $reference] \
        -parent_run $parent
    puts "created implementation run $run_name under $parent_run from $reference"
}

proc lvp_delete_run {run_name} {
    set run [_lvp_run $run_name]
    set child_runs {}
    foreach candidate [get_runs] {
        if {[get_property IS_IMPLEMENTATION $candidate] &&
            [get_property PARENT $candidate] eq $run_name} {
            lappend child_runs $candidate
        }
    }
    if {[llength $child_runs] != 0} {
        error "delete implementation children first: $child_runs"
    }

    delete_runs $run
    puts "deleted run $run_name"
}

proc lvp_save_project {} {
    set xpr_path [_lvp_project_path]
    close_project
    open_project $xpr_path
    puts "saved and reopened project: $xpr_path"
}

proc lvp_write_tcl {path} {
    _lvp_project
    write_project_tcl -force $path
    puts "wrote project Tcl: $path"
}

proc lvp_set_synth_more_options {run_name more_options} {
    lvp_set_run_property \
        $run_name \
        {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} \
        $more_options
}

proc lvp_set_run_strategy {run_name strategy} {
    lvp_set_run_property $run_name STRATEGY $strategy
}

puts "Loaded live Vivado project helpers:"
puts "  lvp_open_project, lvp_info, lvp_runs, lvp_get_run_properties"
puts "  lvp_set_run_property, lvp_set_synth_more_options, lvp_set_run_strategy"
puts "  lvp_create_synth_run, lvp_create_impl_run, lvp_delete_run"
puts "  lvp_save_project, lvp_write_tcl"
