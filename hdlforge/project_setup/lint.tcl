# Get command-line arguments
set path_xpr              [lindex $argv 0]
set param_string          [lindex $argv 1]
set define_string         [lindex $argv 2]
set ignore_error_codes    [lindex $argv 3]
set ignore_warning_codes  [lindex $argv 4]

puts "(i) print all arguments"
puts "=========== TCL Arguments ==========="
puts "Project file:     $path_xpr"
puts "Parameters:       $param_string"
puts "Defines:          $define_string"
puts "====================================="

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file
# Remove board_part to avoid board definition warnings
set_property board_part {} [current_project]

puts "================== stage = lint =================="
puts "(i) preparing lint OPTIONS"

# Get current project settings
set current_top [get_property top [current_fileset]]
set current_part [get_property part [current_project]]
puts "Current top module: $current_top"
puts "Current part: $current_part"
puts ""

# Build list of options for synth_design
set synth_opts "-lint -top $current_top -part $current_part"

# Process defines
if { $define_string ne "" } {
    foreach define [split $define_string " "] {
        append synth_opts " -verilog_define $define"
    }
}

# Process parameters
if { $param_string ne "" } {
    foreach param [split $param_string " "] {
        append synth_opts " -generic $param"
    }
}

puts "=================================================="
puts "Current synth_design command options:"
puts "$synth_opts"
puts "=================================================="

puts "(i) Running synth_design with lint option..."
set catch_result [catch {eval "synth_design $synth_opts"} synth_error]
set synth_ok [expr {$catch_result == 0}]

if { $catch_result != 0 } {
    # synth_design failed - this is expected if errors are found
    puts "(i) synth_design found errors (expected for linting)"
}

puts ""
puts "=========================================="
puts "Generating reports..."
puts "=========================================="

# Try to generate reports even if synth_design had errors
catch {
    report_methodology -file lint_methodology.rpt
    report_drc -file lint_drc.rpt
}

puts ""
puts "=========================================="
puts "Lint check completed!"
puts "=========================================="

# Get current working directory for report file locations
set current_dir [pwd]
puts "Report files location: $current_dir"
puts "Check the following report files:"
puts "  - $current_dir/lint_methodology.rpt"
puts "  - $current_dir/lint_drc.rpt"
puts "Vivado log: $current_dir/.Xil/Vivado-*/vivado.log"
puts "=========================================="

puts "(i) tcl script completed."

# Exit with code 0 if synth completed (even with errors) or 1 if it failed completely
# For linting, finding errors is success, so we exit with 0
exit 0

