# ============================================================================
# Hardware Server Helper Functions
# ============================================================================

# Connect to hardware server (exits on failure)
proc connect_to_hw_server {server_ip} {
    set hw_server_url "$server_ip:3121"
    puts "Connecting to hardware server at $hw_server_url..."
    if { [catch {connect_hw_server -url $hw_server_url} result] } {
        puts "ERROR: Failed to connect to hardware server: $result"
        puts "Please ensure hardware server is running at $server_ip"
        exit 1
    }
    puts "Successfully connected to hardware server"
}

# Discover and open hardware target (exits on failure)
proc discover_and_open_target {} {
    puts "Discovering hardware targets..."
    set hw_targets [get_hw_targets]
    if { [llength $hw_targets] == 0 } {
        puts "ERROR: No hardware targets found"
        puts "Please ensure FPGA is connected and powered on"
        exit 1
    }
    
    puts "Found [llength $hw_targets] hardware target(s):"
    foreach target $hw_targets {
        puts "  - [get_property NAME $target]"
    }
    
    set hw_target [lindex $hw_targets 0]
    puts "Using target: [get_property NAME $hw_target]"
    current_hw_target $hw_target
    
    puts "Opening hardware target..."
    if { [catch {open_hw_target $hw_target} result] } {
        puts "ERROR: Failed to open hardware target: $result"
        exit 1
    }
    
    puts "Refreshing hardware target..."
    catch {refresh_hw_target} result
    puts "Hardware target ready"
}

# Discover and select hardware device (exits on failure, returns device object)
proc discover_and_select_device {} {
    puts "Discovering hardware devices..."
    set hw_devices [get_hw_devices]
    if { [llength $hw_devices] == 0 } {
        puts "ERROR: No hardware devices found on target"
        exit 1
    }
    
    puts "Found [llength $hw_devices] hardware device(s):"
    foreach device $hw_devices {
        set device_name [get_property NAME $device]
        if { [catch {set device_type [get_property TYPE $device]} result] } {
            set device_type "unknown"
        }
        puts "  - $device_name ($device_type)"
    }
    
    set hw_device [lindex $hw_devices 0]
    puts "Using device: [get_property NAME $hw_device]"
    current_hw_device $hw_device
    return $hw_device
}

# Initialize hardware server connection and discover device (exits on failure, returns device object)
proc init_hw_server {server_ip} {
    open_hw_manager
    connect_to_hw_server $server_ip
    puts ""
    
    discover_and_open_target
    puts ""
    
    set hw_device [discover_and_select_device]
    puts ""
    
    return $hw_device
}

# Program FPGA device with bitstream and probes file (exits on failure)
proc program_fpga_device {hw_device bitstream_path {probes_path ""}} {
    puts "=========================================="
    puts "Programming FPGA Device"
    puts "=========================================="
    
    # Verify bitstream file exists
    if { $bitstream_path == "" } {
        puts "ERROR: Bitstream path not provided"
        exit 1
    }
    
    if { ! [file exists $bitstream_path] } {
        puts "ERROR: Bitstream file not found: $bitstream_path"
        exit 1
    }
    
    # Set bitstream file property
    puts "Setting bitstream file: $bitstream_path"
    if { [catch {set_property PROGRAM.FILE $bitstream_path $hw_device} result] } {
        puts "ERROR: Failed to set bitstream file: $result"
        exit 1
    }
    
    # Set probes file property if provided
    if { $probes_path != "" } {
        if { ! [file exists $probes_path] } {
            puts "ERROR: Probes file not found: $probes_path"
            exit 1
        }
        puts "Setting probes file: $probes_path"
        if { [catch {set_property PROBES.FILE $probes_path $hw_device} result] } {
            puts "ERROR: Failed to set probes file: $result"
            exit 1
        }
    }
    
    # Program the device
    puts "Programming device..."
    if { [catch {program_hw_devices $hw_device} result] } {
        puts "ERROR: Failed to program device: $result"
        exit 1
    }
    
    puts "Device programmed successfully"
    puts "=========================================="
}

