# Usage:
# vivado -mode batch -source project_tool.tcl -tclargs list_all_runs <project.xpr>
# vivado -mode batch -source project_tool.tcl -tclargs reset_run <project.xpr> <run_name>

if { $argc < 2 } {
    puts "Usage:"
    puts "  vivado -mode batch -source project_tool.tcl -tclargs list_all_runs <project.xpr>"
    puts "  vivado -mode batch -source project_tool.tcl -tclargs reset_run <project.xpr> <run_name>"
    exit 1
}

# Parse arguments
set cmd [lindex $argv 0]
set project_path [lindex $argv 1]
set run_name [lindex $argv 2]

# Check project file exists
if {![file exists $project_path]} {
    puts "Error: Project file '$project_path' not found."
    exit 1
}

# Open project
open_project $project_path
# Remove board_part to avoid board definition warnings
set_property board_part {} [current_project]

# Command dispatcher
switch -- $cmd {
    "list_all_runs" {
        foreach run [get_runs] {
            set synth [get_property IS_SYNTHESIS $run]
            set impl  [get_property IS_IMPLEMENTATION $run]
            set status [get_property STATUS $run]
            
            # Get defines and parameters from MORE_OPTIONS for synthesis runs
            set defines ""
            set parameters ""
            if { $synth == 1 } {
                catch {
                    set more_opts [get_property {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} $run]
                    if { $more_opts ne "" } {
                        # Parse -verilog_define and -generic options
                        set opts_list [split $more_opts " "]
                        set i 0
                        while { $i < [llength $opts_list] } {
                            set opt [lindex $opts_list $i]
                            if { $opt == "-verilog_define" } {
                                incr i
                                if { $i < [llength $opts_list] } {
                                    if { $defines ne "" } {
                                        append defines " "
                                    }
                                    append defines [lindex $opts_list $i]
                                }
                            } elseif { $opt == "-generic" } {
                                incr i
                                if { $i < [llength $opts_list] } {
                                    if { $parameters ne "" } {
                                        append parameters " "
                                    }
                                    append parameters [lindex $opts_list $i]
                                }
                            }
                            incr i
                        }
                    }
                }
            }
            
            if { $impl == 1 } {
                set parent [get_property PARENT $run]
                puts "$run\tSynth=$synth Impl=$impl Status=$status Parent=$parent Defines=$defines Parameters=$parameters"
            } else {
                puts "$run\tSynth=$synth Impl=$impl Status=$status Parent= Defines=$defines Parameters=$parameters"
            }
        }
    }
    "reset_run" {
        if { $argc < 3 } {
            puts "Error: reset_run requires a run name. Usage:"
            puts "  vivado -mode batch -source project_tool.tcl -tclargs reset_run <project.xpr> <run_name>"
            close_project
            exit 1
        }
        if { [lsearch [get_runs] $run_name] == -1 } {
            puts "Error: Run '$run_name' not found in project."
            close_project
            exit 1
        }
        
        puts "\n===> Run status before reset:"
        foreach run [get_runs] {
            set synth [get_property IS_SYNTHESIS $run]
            set impl  [get_property IS_IMPLEMENTATION $run]
            set status [get_property STATUS $run]
            puts "$run\tSynth=$synth Impl=$impl Status=$status"
        }

        puts "\n===> Resetting run: $run_name"
        reset_run $run_name

        puts "\n===> Run status after reset:"
        foreach run [get_runs] {
            set synth [get_property IS_SYNTHESIS $run]
            set impl  [get_property IS_IMPLEMENTATION $run]
            set status [get_property STATUS $run]
            puts "$run\tSynth=$synth Impl=$impl Status=$status"
        }
        puts "\n"
    }

    default {
        puts "Unknown command: $cmd"
        puts "Available commands: list_all_runs, reset_run"
        close_project
        exit 1
    }
}

# Cleanup
close_project
exit 0
