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
