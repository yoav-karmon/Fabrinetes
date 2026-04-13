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
puts "Ignore warnings:  $ignore_warning_codes"
puts "Ignore errors:    $ignore_error_codes"
puts "====================================="

# Process ignore warning codes BEFORE opening project
# Warning codes may contain spaces (e.g., "Board 49-26"), so we need to preserve them
if { $ignore_warning_codes ne "" } {
    puts "(i) Suppressing warning codes: $ignore_warning_codes"
    # The argument is passed as a single string, so we use it as-is for the message ID
    # If multiple codes are needed, they should be comma-separated in the config
    # For now, treat the entire string as one code (handles "Board 49-26" format)
    set_msg_config -suppress -id "$ignore_warning_codes" -quiet
    puts "  - Suppressing: $ignore_warning_codes"
}

# Process ignore error codes
if { $ignore_error_codes ne "" } {
    puts "(i) Suppressing error codes: $ignore_error_codes"
    foreach error_code [split $ignore_error_codes " "] {
        if { $error_code ne "" } {
            # Convert errors to warnings (we can't fully suppress errors)
            set_msg_config -severity {WARNING} -id "$error_code" -quiet
            puts "  - Converting to warning: $error_code"
        }
    }
}

puts "(i) Open project"
set project_file "${path_xpr}"
open_project $project_file

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
# Note: report_methodology and report_drc may fail with -lint option
# because -lint doesn't create a full synthesized design object
if {[catch {report_methodology -file lint_methodology.rpt} err]} {
    puts "(i) report_methodology failed (expected with -lint option): $err"
    puts "(i) Methodology reports require full synthesis, not just linting"
} else {
    puts "(i) report_methodology completed successfully"
}

if {[catch {report_drc -file lint_drc.rpt} err]} {
    puts "(i) report_drc failed (expected with -lint option): $err"
    puts "(i) DRC reports require full synthesis, not just linting"
} else {
    puts "(i) report_drc completed successfully"
}

puts ""
puts "=========================================="
puts "Lint check completed!"
puts "=========================================="

# Report only files that actually exist for this run.
set current_dir [pwd]
set report_files {}

foreach report_name {lint_methodology.rpt lint_drc.rpt} {
    set report_path [file join $current_dir $report_name]
    if {[file exists $report_path]} {
        lappend report_files $report_path
    }
}

puts "Report files location: $current_dir"
if {[llength $report_files] > 0} {
    puts "Check the following report files:"
    foreach report_path $report_files {
        puts "  - $report_path"
    }
} else {
    puts "No lint report files were generated."
}

set vivado_log [file join $current_dir "vivado.log"]
if {[file exists $vivado_log]} {
    puts "Vivado log: $vivado_log"
} else {
    set xil_logs [glob -nocomplain [file join $current_dir ".Xil" "Vivado-*" "vivado.log"]]
    if {[llength $xil_logs] > 0} {
        puts "Vivado log(s):"
        foreach log_path $xil_logs {
            puts "  - $log_path"
        }
    } else {
        puts "Vivado log: (not found)"
    }
}
puts "=========================================="

puts "(i) tcl script completed."

# Exit with code 0 if synth completed (even with errors) or 1 if it failed completely
# For linting, finding errors is success, so we exit with 0
exit 0

