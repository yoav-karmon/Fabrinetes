# Get command-line arguments
set path_xpr      [lindex $argv 0]
set stage         [lindex $argv 1]
set synth_run     [lindex $argv 2]
set impl_run      [lindex $argv 3]
set param_string  [lindex $argv 4]
set define_string [lindex $argv 5]

puts "(i) print all arguments"
puts "=========== TCL Arguments ==========="
puts "Project file:     $path_xpr"
puts "Stage:            $stage"
puts "Synthesis run:    $synth_run"
puts "Implementation run: $impl_run"
puts "Parameters:       $param_string"
puts "Defines:          $define_string"
puts "====================================="

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file
puts "================== stage = synthesis =================="

if { $stage == "syn" | $stage == "all" } {
    puts "(i) preparing synthesis run OPTIONS"
    set more_opts ""
    set run_obj [get_runs $synth_run]


    if { $define_string ne "" } {
        foreach define [split $define_string " "] {
            append more_opts " -verilog_define $define"
        }
    }

    if { $param_string ne "" } {
        foreach param [split $param_string " "] {
            append more_opts " -generic $param"
        }
    }
    puts "=================================================="
    puts "Current MORE_OPTIONS for synthesis run '$synth_run':"
    puts "$more_opts"
    puts "=================================================="

    puts "(i) Setting MORE_OPTIONS for $synth_run: $more_opts"
    set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value $more_opts -objects $run_obj
    puts "(i) Setting run properties for $synth_run"
    report_property  $run_obj

    puts "(i) processing stages: $stage"



    set progress     [get_property PROGRESS [get_runs $synth_run]]
    set need_refresh [get_property NEEDS_REFRESH [get_runs $synth_run]]
    set status       [get_property STATUS [get_runs $synth_run]]
    set status_lower [string tolower $status]

    puts "(i) $synth_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"

    if { [string match "*complete*" $status_lower] == 0 || $need_refresh == 1 } {
        puts "(!) Resetting and launching synthesis run: $synth_run"
        reset_runs $synth_run
        launch_runs $synth_run -to_step synth_design -jobs 4
        wait_on_run [get_runs -filter {IS_SYNTHESIS == TRUE}]
       
    } else {
        puts "(!) Skipping $synth_run (STATUS: $status)"
    }

} else {
    set run_obj [get_runs $synth_run]
    report_property  $run_obj
    puts "(!) Skipping synthesis stage"
}
puts "======================================================"
puts ""


puts "================== stage = Implementation ============"


if { $stage == "impl" | $stage == "all" } {
    # Implementation
    set progress     [get_property PROGRESS [get_runs $impl_run]]
    set need_refresh [get_property NEEDS_REFRESH [get_runs $impl_run]]
    set status       [get_property STATUS [get_runs $impl_run]]
    set status_lower [string tolower $status]

    puts "$impl_run: $status (PROGRESS: $progress), needs_refresh: $need_refresh"

    if { $need_refresh == 1 || [string match "*complete*" $status_lower] == 0 } {
        puts "Resetting and launching implementation run: $impl_run"
        reset_runs $impl_run
        launch_runs $impl_run -to_step write_bitstream -jobs 4
        wait_on_run [get_runs -filter {IS_IMPLEMENTATION == TRUE}]
    } else {
        puts "Skipping $impl_run (STATUS: $status)"
    }

} elseif { $stage == "bit" } {
    puts "Writing bitstream for: $impl_run"
    write_bitstream -force [get_runs $impl_run]
    wait_on_run [get_runs -filter {IS_IMPLEMENTATION == TRUE}]
} else {
    puts "(!) Skipping implementation / bit stage"
}

puts "======================================================"
puts ""

puts "(i) Final status report"
puts "==================== Final run statuses ===================="
set status       [get_property STATUS [get_runs $synth_run]]
puts "$synth_run: $status"
set status       [get_property STATUS [get_runs $impl_run]]
puts "$impl_run: $status"
puts "============================================================"

puts "(i) tcl script completed."

