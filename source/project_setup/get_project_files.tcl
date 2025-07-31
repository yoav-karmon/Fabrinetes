proc list_vhdl_2008_sim_files {} {
    foreach f [get_files -compile_order sources  -used_in synthesis -of_objects [get_fileset sources_1]] {
        if {[file extension $f] eq ".vhd"} {
            set lib       [get_property library [get_files $f]]
            set file_type [get_property file_type [get_files $f]]

            if {[string equal $lib "xil_defaultlib"] &&
                [string match *VHDL* $file_type] &&
                [string match *2008* $file_type]} {

                # Only proceed if 'used_in' property exists and includes "synthesis"
                if {[catch {get_property used_in [get_files $f]} used_in] == 0 &&
                    [lsearch -exact $used_in "synthesis"] >= 0} {
                    puts "vivado_file:$f"
                }
            }
        }
    }
}

# Use the function after opening the project
set xpr_file [lindex $argv 0]
open_project $xpr_file

list_vhdl_2008_sim_files

close_project
exit
