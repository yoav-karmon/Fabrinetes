# ============================================================================
# ILA Reading Helper Functions
# ============================================================================

# Read ILA values from FPGA
# Arguments:
#   hw_device - Hardware device object
#   bit_file - Path to bitstream file (.bit)
#   ltx_file - Path to probe file (.ltx)
# Returns: List of ILA probe values
proc read_ila_values {hw_device bit_file ltx_file} {
    # Program the device with bitstream
    puts "Programming device with bitstream: $bit_file"
    if { [catch {program_hw_devices $hw_device -bit_file $bit_file} result] } {
        puts "ERROR: Failed to program device: $result"
        exit 1
    }
    puts "Device programmed successfully"
    
    # Open ILA hardware manager
    puts "Opening ILA hardware manager..."
    if { [catch {open_hw_ila_manager -quiet} result] } {
        puts "WARNING: Failed to open ILA manager: $result"
    }
    
    # Read ILA probe data
    puts "Reading ILA probe data from: $ltx_file"
    if { [catch {read_hw_ila_data $ltx_file} result] } {
        puts "ERROR: Failed to read ILA data: $result"
        exit 1
    }
    
    # Get all ILA probes
    set ila_probes [get_hw_ila_probes]
    if { [llength $ila_probes] == 0 } {
        puts "WARNING: No ILA probes found"
        return {}
    }
    
    puts "Found [llength $ila_probes] ILA probe(s)"
    
    # Read values from each probe
    set probe_values {}
    foreach probe $ila_probes {
        set probe_name [get_property NAME $probe]
        # Try to get probe value - may need to use different property
        if { [catch {set probe_value [get_property VALUE $probe]} result] } {
            # Try alternative property names
            if { [catch {set probe_value [get_property C_DATA $probe]} result] } {
                set probe_value "N/A"
            }
        }
        lappend probe_values [list $probe_name $probe_value]
    }
    
    return $probe_values
}

# Display ILA values in a formatted way
proc display_ila_values {probe_values} {
    if { [llength $probe_values] == 0 } {
        puts "No ILA probe values to display"
        return
    }
    
    puts "=========================================="
    puts "ILA Probe Values:"
    puts "=========================================="
    foreach probe_entry $probe_values {
        set probe_name [lindex $probe_entry 0]
        set probe_value [lindex $probe_entry 1]
        puts "  $probe_name: $probe_value"
    }
    puts "=========================================="
}

