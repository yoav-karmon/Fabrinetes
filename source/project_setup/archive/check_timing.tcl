if {$argc != 1} {
    puts "❌ Error: Missing project file argument."
    puts "Usage: vivado -mode tcl -source check_timing.tcl -tclargs <project.xpr>"
    exit 1
}

set xpr_file [lindex $argv 0]

if {![file exists $xpr_file]} {
    puts "❌ Error: Project file '$xpr_file' not found."
    exit 1
}

open_project $xpr_file

puts "\n### ⏱ Timing Report for $xpr_file ###"

set all_runs [get_runs]
set impl_runs {}

foreach run $all_runs {
    if {[get_property IS_IMPLEMENTATION $run]} {
        lappend impl_runs $run
    }
}

if {[llength $impl_runs] == 0} {
    puts "❌ No implementation runs found."
} else {
    foreach run $impl_runs {
        set status [get_property STATUS $run]
        set wns [get_property STATS.WNS $run]
        set tns [get_property STATS.TNS $run]

        puts "\n  Run: $run"
        puts "   - Status: $status"

        if {$wns != "" && $tns != ""} {
            puts "   - Worst Negative Slack (WNS): $wns ns"
            puts "   - Total Negative Slack (TNS): $tns ns"

            if {$wns >= 0 && $tns >= 0} {
                puts "   ✅ Timing PASSED"
            } else {
                puts "   ❌ Timing FAILED"
            }
        } else {
            puts "   ⚠️  WNS/TNS not available"
        }
    }
}

close_project

