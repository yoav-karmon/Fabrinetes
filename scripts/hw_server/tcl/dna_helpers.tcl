# ============================================================================
# DNA Reading Helper Functions
# ============================================================================

# Format DNA value (remove 0x prefix and leading zeros)
proc format_dna {dna_value} {
    set dna [string trim $dna_value]
    if { [string match "0x*" $dna] } {
        set dna [string range $dna 2 end]
    }
    set dna [string trimleft $dna "0"]
    return [string toupper $dna]
}

# Try to read DNA using REGISTER.EFUSE.FUSE_DNA
proc read_dna_fuse {hw_device} {
    if { [catch {set chip_dna [get_property REGISTER.EFUSE.FUSE_DNA $hw_device]} result] } {
        # Try report_property as fallback
        if { ! [catch {set report_output [report_property $hw_device REGISTER.EFUSE.FUSE_DNA]} report_result] } {
            if { [regexp {Value:\s*([0-9A-Fa-f]+)} $report_output match chip_dna] } {
                return [string toupper $chip_dna]
            }
        }
        return ""
    }
    
    set chip_dna [string trim $chip_dna]
    if { [string match "0x*" $chip_dna] } {
        set chip_dna [string range $chip_dna 2 end]
    }
    set chip_dna [string toupper $chip_dna]
    
    if { [string length $chip_dna] > 0 && $chip_dna != "" && $chip_dna != "UNREADABLE" } {
        return $chip_dna
    }
    return ""
}

# Try to read DNA using REGISTER.DNA.SLR0
proc read_dna_slr0 {hw_device} {
    if { [catch {set chip_dna [get_property REGISTER.DNA.SLR0 $hw_device]} result] } {
        return ""
    }
    set chip_dna [string trim $chip_dna]
    if { [string length $chip_dna] > 0 && $chip_dna != "" && $chip_dna != "Unreadable" } {
        return $chip_dna
    }
    return ""
}

# Read all SLR DNA values
proc read_all_slr_dna {hw_device} {
    set all_dna_values {}
    foreach slr {SLR0 SLR1 SLR2 SLR3} {
        if { ! [catch {set slr_dna [get_property REGISTER.DNA.$slr $hw_device]} result] } {
            set slr_dna [string trim $slr_dna]
            if { [string length $slr_dna] > 0 && $slr_dna != "" } {
                lappend all_dna_values "$slr: $slr_dna"
            }
        }
    }
    return $all_dna_values
}

# Main DNA reading function - tries all methods
proc read_chip_dna {hw_device} {
    puts "Reading chip DNA..."
    
    # Method 1: Try REGISTER.EFUSE.FUSE_DNA
    set chip_dna [read_dna_fuse $hw_device]
    if { $chip_dna != "" } {
        puts "Successfully read DNA using REGISTER.EFUSE.FUSE_DNA"
        set all_dna_values [read_all_slr_dna $hw_device]
        return [list $chip_dna $all_dna_values]
    }
    
    # Method 2: Try REGISTER.DNA.SLR0
    set chip_dna [read_dna_slr0 $hw_device]
    if { $chip_dna != "" } {
        puts "Successfully read DNA using REGISTER.DNA.SLR0"
        set all_dna_values [read_all_slr_dna $hw_device]
        return [list $chip_dna $all_dna_values]
    }
    
    # Method 3: Search all DNA properties
    puts "Searching for DNA in all register properties..."
    set all_props [list_property $hw_device]
    set dna_props {}
    foreach prop $all_props {
        if { [string match "*DNA*" $prop] } {
            lappend dna_props $prop
        }
    }
    
    if { [llength $dna_props] > 0 } {
        foreach prop $dna_props {
            if { ! [catch {set prop_value [get_property $prop $hw_device]} result] } {
                if { [string length $prop_value] > 0 && $prop_value != "" && $prop_value != "Unreadable" } {
                    set chip_dna $prop_value
                    set all_dna_values [read_all_slr_dna $hw_device]
                    return [list $chip_dna $all_dna_values]
                }
            }
        }
    }
    
    return [list "" {}]
}

# Display DNA result
proc display_dna_result {chip_dna all_dna_values hw_device} {
    if { $chip_dna != "" } {
        set formatted_dna [format_dna $chip_dna]
        puts "=========================================="
        if { [llength $all_dna_values] > 1 } {
            puts "Chip DNA (Multiple SLRs detected):"
            foreach dna_entry $all_dna_values {
                if { [regexp {^(SLR\d+):\s*(.+)$} $dna_entry match slr_name slr_value] } {
                    puts "  $slr_name: [format_dna $slr_value]"
                } else {
                    puts "  $dna_entry"
                }
            }
            puts ""
            puts "Primary DNA (SLR0 / REGISTER.EFUSE.FUSE_DNA): $formatted_dna"
        } else {
            puts "Chip DNA (REGISTER.EFUSE.FUSE_DNA): $formatted_dna"
        }
        puts "=========================================="
        return 1
    } else {
        puts "=========================================="
        puts "WARNING: Unable to read chip DNA"
        puts "=========================================="
        puts "Possible reasons:"
        puts "  1. Device may need to be opened/programmed first"
        puts "  2. Device family may not support DNA reading"
        puts "  3. Hardware target may need to be refreshed"
        puts ""
        puts "Device information:"
        puts "  Name: [get_property NAME $hw_device]"
        catch {puts "  Programmed: [get_property PROGRAM.IS_PROGRAMMED $hw_device]"} result
        puts ""
        puts "Try running this command manually in Vivado Hardware Manager:"
        puts "  get_property REGISTER.EFUSE.FUSE_DNA \[lindex \[get_hw_devices\] 0\]"
        return 0
    }
}

