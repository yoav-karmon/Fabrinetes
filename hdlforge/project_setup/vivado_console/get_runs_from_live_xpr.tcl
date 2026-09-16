proc _runs_export_b64 {value} {
    return [binary encode base64 -maxlen 0 [encoding convertto utf-8 $value]]
}

if {$argc != 2 && !($argc == 3 && [lindex $argv 2] eq "reuse")} {
    error "usage: get_runs_from_live_xpr.tcl <project.xpr> <output-records>"
}

set xpr_path [file normalize [lindex $argv 0]]
set output_path [file normalize [lindex $argv 1]]

if {![file isfile $xpr_path]} {
    error "XPR does not exist: $xpr_path"
}

set reuse [expr {$argc == 3}]
if {!$reuse} {
    open_project -read_only $xpr_path
} elseif {[_lvp_project_path] ne $xpr_path} {
    error "Wrong project open for inventory"
}
set output [open $output_path w]

try {
    set project [current_project]
    puts $output [join [list \
        PROJECT \
        [_runs_export_b64 [get_property NAME $project]] \
        [_runs_export_b64 $xpr_path]] "\t"]

    foreach run [lsort [get_runs]] {
        puts $output [join [list RUN [_runs_export_b64 $run]] "\t"]

        foreach property_name [lsort [list_property $run]] {
            if {[catch {get_property $property_name $run} property_value]} {
                puts $output [join [list \
                    PROPERTY_ERROR \
                    [_runs_export_b64 $property_name] \
                    [_runs_export_b64 $property_value]] "\t"]
            } else {
                puts $output [join [list \
                    PROPERTY \
                    [_runs_export_b64 $property_name] \
                    [_runs_export_b64 $property_value]] "\t"]
            }
        }

        puts $output ENDRUN
    }
} finally {
    close $output
    if {!$reuse} {close_project}
}
