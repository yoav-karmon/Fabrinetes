set project_xpr [lindex $argv 0]

if {$project_xpr == ""} {
    puts "Usage: vivado -mode tcl -source list_files.tcl -tclargs <project.xpr>"
    exit 1
}

open_project $project_xpr

set files [get_files]
set output_file "vivado_files.txt"
set fp [open $output_file w]

set file_col_width 40
set type_col_width 18
set hier_col_width 10
set path_col_width 80

puts $fp "------------------------------------------------------------------------------------------------------------------------------------"
puts $fp [format "| %-*s | %-*s | %-*s | %-*s |" \
    $file_col_width "File Name" \
    $type_col_width "Type" \
    $hier_col_width "Hierarchy" \
    $path_col_width "Path"]
puts $fp "------------------------------------------------------------------------------------------------------------------------------------"

foreach file $files {
    set file_name [file tail $file]  
    set file_path [file normalize $file]  
    set file_type [get_property FILE_TYPE $file]  
    set in_hierarchy [get_property USED_IN $file]  
    
    if {$in_hierarchy == ""} {
        set in_hierarchy "No"
    } else {
        set in_hierarchy "Yes"
    }

    if {[string length $file_path] > $path_col_width} {
        set file_path "[string range $file_path 0 [expr {$path_col_width - 5}]]..."
    }

    puts $fp [format "| %-*s | %-*s | %-*s | %-*s |" \
        $file_col_width $file_name \
        $type_col_width $file_type \
        $hier_col_width $in_hierarchy \
        $path_col_width $file_path]
}

puts $fp "------------------------------------------------------------------------------------------------------------------------------------"

close $fp
close_project

puts "File list saved to: $output_file"
exit

