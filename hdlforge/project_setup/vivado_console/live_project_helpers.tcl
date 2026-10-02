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

# Console state does not inspect project runs or derive an XPR path.
proc lvp_status {} {
    set design ""
    catch {set design [current_design -quiet]}
    lvp_emit [dict create CONSOLE responsive DESIGN $design]
}
