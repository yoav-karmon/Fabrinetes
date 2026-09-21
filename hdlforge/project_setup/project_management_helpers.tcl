namespace eval hdlforge::project {}

proc hdlforge::project::idr_owner {run_obj} {
    # Vivado 2025 exposes the synthesis PARENT for IDR children too, and
    # does not expose the XPR IsChild flag as a run property. Match generated
    # child names against an existing IDR flow owner, not a global i_* prefix.
    set run_name [get_property NAME $run_obj]
    foreach owner [get_runs -quiet -filter {FLOW =~ "Vivado IDR Flow*"}] {
        set owner_name [get_property NAME $owner]
        set prefix "${owner_name}_"
        if {[string first $prefix $run_name] != 0} {
            continue
        }
        set suffix [string range $run_name [string length $prefix] end]
        if {[regexp {^(rqs|ml_strat_[0-9]+|eco_flow)$} $suffix]} {
            return $owner_name
        }
    }
    return ""
}
