# Usage:
# vivado -mode batch -source project_tool.tcl -tclargs <command> <project.xpr> [optional_run_name]

if { $argc < 2 } {
    puts "Usage:"
    puts "  vivado -mode batch -source project_tool.tcl -tclargs list_synth_runs <project.xpr>"
    puts "  vivado -mode batch -source project_tool.tcl -tclargs list_impl_runs <project.xpr>"
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

# Command dispatcher
switch -- $cmd {
    "list_synth_runs" {
        foreach run [get_runs -filter {IS_SYNTHESIS == 1}] {
            puts "SYNTH: $run\t[get_property STATUS $run]"
        }
    }
    "list_impl_runs" {
        foreach run [get_runs -filter {IS_IMPLEMENTATION == 1}] {
            puts "IMPL : $run\t[get_property STATUS $run]"
        }
    }
    "list_all_runs" {
        foreach run [get_runs] {
            set synth [get_property IS_SYNTHESIS $run]
            set impl  [get_property IS_IMPLEMENTATION $run]
            set status [get_property STATUS $run]
            puts "$run\tSynth=$synth Impl=$impl Status=$status"
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
        puts "Available commands: list_synth_runs, list_impl_runs, list_all_runs, reset_run"
        close_project
        exit 1
    }
}

# Cleanup
close_project
exit 0
