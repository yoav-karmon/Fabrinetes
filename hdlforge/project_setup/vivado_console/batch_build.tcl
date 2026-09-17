lassign $argv project target kind jobs reset reset_only bitstream
if {[catch {
    open_project $project
    set selected [get_runs $target]
    if {$reset || $reset_only} {reset_runs $selected}
    if {!$reset_only} {
        if {$kind eq "group"} {
            source [file join [file dirname [info script]] .. project_management_helpers.tcl]
            set selected {}
            foreach run [get_runs] {
                if {[get_property IS_IMPLEMENTATION $run] && [get_property PARENT $run] eq $target} {
                    if {[hdlforge::project::idr_owner $run] ne ""} {continue}
                    if {[string match "Vivado IDR Flow*" [get_property FLOW $run]]} {continue}
                    if {[string first {[HDLForge:disabled]} [get_property DESCRIPTION $run]] >= 0} {continue}
                    lappend selected $run
                }
            }
            if {[llength $selected] == 0} {set selected [get_runs $target]}
        }
        if {[get_property IS_IMPLEMENTATION [lindex $selected 0]]} {
            set stage [expr {$bitstream ? "write_bitstream" : "route_design"}]
            launch_runs $selected -to_step $stage -jobs $jobs
        } else {
            launch_runs $selected -jobs $jobs
        }
        foreach run $selected {wait_on_run $run}
    }
    close_project
} message]} {
    puts stderr "HDLFORGE_BATCH_FAILED: $message"
    exit 1
}
puts "HDLFORGE_BATCH_COMPLETED"
exit 0
