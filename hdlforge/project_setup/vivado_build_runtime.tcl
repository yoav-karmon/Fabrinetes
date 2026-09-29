# Shared JSON-driven non-project execution. Python writes config.tcl as Tcl data.
namespace eval ::hdlforge {
    variable copied [dict create]
    variable ran 0
    variable routed 0
}

proc ::hdlforge::status {value} {
    set handle [open [file join [dict get $::hdlforge_config output] info status] w]
    puts $handle $value
    close $handle
}

proc ::hdlforge::collect {} {
    variable copied
    set output [dict get $::hdlforge_config output]
    foreach {pattern folder} {*.dcp checkpoints *.rpt reports *.rpx reports *.bit bitstream *.ltx bitstream *.mmi bitstream} {
        foreach path [glob -nocomplain -directory [file join $output work] $pattern] {
            set signature [list [file size $path] [file mtime $path]]
            if {[dict exists $copied $path] && [dict get $copied $path] eq $signature} {continue}
            set destination [file join $output $folder [file tail $path]]
            file copy -force $path ${destination}.tmp
            file rename -force ${destination}.tmp $destination
            dict set copied $path $signature
        }
    }
}

proc ::hdlforge::artifact_written {command code result operation} {
    variable routed
    if {$code != 0} {return}
    collect
    if {$routed && [namespace tail [lindex $command 0]] eq "write_checkpoint"} {
        set name [file tail [lindex $command end]]
        set output [dict get $::hdlforge_config output]
        if {[file isfile [file join $output checkpoints $name]]} {
            set handle [open [file join $output info last_routed_checkpoint.txt] w]
            puts $handle $name
            close $handle
        }
    }
}

proc ::hdlforge::properties {settings objects} {
    if {[dict exists $settings properties]} {
        dict for {name value} [dict get $settings properties] {
            foreach object $objects {
                set current [get_property $name $object]
                if {$current eq $value} {continue}
                if {[string is boolean -strict $current] && [string is boolean -strict $value]} {
                    if {[expr {!!$current}] == [expr {!!$value}]} {continue}
                }
                set_property $name $value $object
            }
        }
    }
}

proc ::hdlforge::load_files {} {
    set config $::hdlforge_config
    set stage [dict get $config stage]
    if {$stage eq "synth"} {
        foreach entry [dict get $config sources] {
            set path [dict get $entry path]
            set extension [file extension $path]
            set library [get_property default_lib [current_project]]
            if {[dict exists $entry library]} {set library [dict get $entry library]}
            if {$extension in {.vhd .vhdl}} {
                set arguments [list -library $library]
                if {[dict exists $entry language] && [dict get $entry language] eq "vhdl2008"} {lappend arguments -vhdl2008}
                read_vhdl {*}$arguments $path
            } else {
                set arguments [list -library $library]
                if {$extension eq ".sv"} {lappend arguments -sv}
                read_verilog {*}$arguments $path
            }
            properties $entry [get_files $path]
        }
    } elseif {$stage eq "impl"} {
        add_files -quiet [dict get $config input_dcp]
    }
    foreach entry [dict get $config ips] {
        set path [dict get $entry path]
        read_ip $path
        set ip [get_ips -quiet [file rootname [file tail $path]]]
        if {[llength $ip] != 1} {error "Cannot resolve imported IP: $path"}
        if {[dict exists $entry file_properties]} {
            set ip [get_ips -quiet [file rootname [file tail $path]]]
            if {[llength $ip] != 1} {error "Cannot resolve imported IP: $path"}
            set files [get_files -quiet -all -of_objects $ip]
            dict for {relative overrides} [dict get $entry file_properties] {
                set matches {}
                foreach candidate $files {
                    if {[string match "*/$relative" $candidate]} {lappend matches $candidate}
                }
                if {![llength $matches]} {error "Missing IP constraint $relative in $path"}
                dict for {name value} $overrides {set_property $name $value $matches}
            }
        }
        if {[dict exists $entry properties]} {
            # IP settings belong to the XCI configuration, including when the
            # on-disk source is an XCIX container. Use Vivado's IP_FILE mapping.
            set configuration [get_files -all [get_property IP_FILE $ip]]
            if {[llength $configuration] != 1} {error "Cannot resolve IP configuration for $path"}
            if {[catch {properties $entry $configuration} message options]} {
                catch {report_ip_status -file [file join [dict get $config output] reports ip_status_failed.rpt]}
                return -options $options $message
            }
        }
    }
    if {[dict size [dict get $config checkpoint_properties]]} {
        foreach dcp [get_files -quiet -all -filter {file_type == "Design Checkpoint"}] {
            dict for {name value} [dict get $config checkpoint_properties] {set_property $name $value $dcp}
        }
    }
    foreach entry [dict get $config constraints] {
        set path [dict get $entry path]
        read_xdc $path
        dict for {name value} [dict get $config constraint_properties] {set_property $name $value [get_files $path]}
        properties $entry [get_files $path]
    }
}

##############################################################################
## Preserve the whitespace used by Vivado-generated launchOptions settings.
## Without it, Vivado interprets a value beginning with -jobs as an option to
## set_param itself. This also handles existing frozen JSON configurations.
##############################################################################
proc ::hdlforge::apply_parameter {name value} {
    if {$name eq "runs.launchOptions"} {
        set value " $value "
    }
    set_param $name $value
}

proc ::hdlforge::initialize_design {} {
    set config $::hdlforge_config
    dict for {name value} [dict get $config parameters] {apply_parameter $name $value}
    create_project -in_memory -part [dict get $config part]
    dict for {name value} [dict get $config project_properties] {set_property $name $value [current_project]}
    dict for {name value} [dict get $config fileset_properties] {set_property $name $value [current_fileset]}
    load_files
    dict for {name value} [dict get $config post_load_parameters] {apply_parameter $name $value}
}

proc ::hdlforge::event {event stage elapsed command} {
    set handle [open [file join [dict get $::hdlforge_config output] info stages.tsv] a]
    puts $handle "[clock format [clock seconds] -gmt 1 -format %FT%TZ]\t$event\t$stage\t$elapsed\t[string map [list \t { } \n { }] $command]"
    close $handle
    puts "HDLFORGE_STAGE_$event $stage: $command"
}

# Stamp bitstreams with this implementation launch's identity before writing.
proc ::hdlforge::stamp_bitstream {} {
    set config $::hdlforge_config
    if {[dict get $config stage] ni {impl bitstream}} {return}
    set epoch [dict get $config launch_epoch]
    if {[dict get $config stage] eq "bitstream"} {set epoch [dict get $config bitstream_epoch]}
    if {![string is wideinteger -strict $epoch] || $epoch < 0 || $epoch > 0xffffffff} {
        error "Implementation launch_epoch must fit the 32-bit bitstream USERID"
    }
    set userid [format "0x%08X" $epoch]
    set_property BITSTREAM.CONFIG.USERID $userid [current_design]
    set handle [open [file join [dict get $config output] info bitstream_timestamp.json] w]
    puts $handle [format {{"launch_epoch": %s, "userid": "%s"}} $epoch $userid]
    close $handle
    puts "Bitstream USERID timestamp: $userid"
}

# Observe native Vivado commands; stamp USERID before write_bitstream.
proc ::hdlforge::command_enter {command operation} {
    variable ran
    variable started
    variable observed_stage
    set ran 1
    set observed_stage [lindex $command 0]
    if {[namespace tail $observed_stage] eq "write_bitstream"} {stamp_bitstream}
    if {[info exists ::ACTIVE_STEP]} {set observed_stage $::ACTIVE_STEP}
    set started [clock milliseconds]
    status running:$observed_stage
    event start $observed_stage {} $command
}

proc ::hdlforge::command_leave {command code result operation} {
    variable routed
    variable started
    variable observed_stage
    set elapsed [expr {([clock milliseconds] - $started) / 1000.0}]
    set outcome [expr {$code == 0 ? "done" : "failed"}]
    event $outcome $observed_stage $elapsed $command
    if {$code == 0 && [namespace tail [lindex $command 0]] eq "route_design"} {set routed 1}
}

##############################################################################
## Vivado can emit XDC errors without returning a Tcl error. Compare ERROR
## counts around immediate reads and link_design (deferred XDC evaluation).
## A stack handles nested constraint reads without losing the outer count.
##############################################################################
set ::hdlforge::constraint_error_counts {}
proc ::hdlforge::constraint_enter {command operation} {
    lappend ::hdlforge::constraint_error_counts [get_msg_config -count -severity ERROR]
}
proc ::hdlforge::constraint_leave {command code result operation} {
    set before [lindex $::hdlforge::constraint_error_counts end]
    set ::hdlforge::constraint_error_counts [lrange $::hdlforge::constraint_error_counts 0 end-1]
    if {$code == 0 && [get_msg_config -count -severity ERROR] > $before} {
        error "Constraint loading emitted ERROR messages during $command; see the original XDC file and line diagnostics above."
    }
}

if {[llength $argv] != 1} {error "Expected a generated config.tcl path"}
source [lindex $argv 0]
set ::np_project_root [dict get $::hdlforge_config project_root]
set output [dict get $::hdlforge_config output]
set code [catch {
    ::hdlforge::status initializing
    set handle [open [file join $output info vivado_version.txt] w]
    puts $handle [version]
    close $handle
    set expected [dict get $::hdlforge_config vivado_version]
    if {$expected ne "" && [version -short] ne $expected} {error "Expected Vivado $expected; found [version -short]"}
    set handle [open [file join $output info stages.tsv] w]
    puts $handle "utc\tevent\tstage\telapsed_seconds\tcommand"
    close $handle
    foreach command {write_checkpoint generate_parallel_reports write_bitstream} {
        trace add execution $command leave ::hdlforge::artifact_written
    }
    foreach command {synth_design link_design opt_design place_design phys_opt_design route_design write_bitstream generate_target synth_ip} {
        trace add execution $command enter ::hdlforge::command_enter
        trace add execution $command leave ::hdlforge::command_leave
    }
    foreach command {read_xdc link_design} {
        trace add execution $command enter ::hdlforge::constraint_enter
        trace add execution $command leave ::hdlforge::constraint_leave
    }
    set errors_before_run [get_msg_config -count -severity ERROR]
    source [dict get $::hdlforge_config script]
    # synth_ip can catch a failed nested synth_design and still return success.
    # An IP with those errors must never be advertised as a completed producer.
    if {[dict get $::hdlforge_config stage] eq "ip" &&
        [get_msg_config -count -severity ERROR] > $errors_before_run} {
        error "IP generation emitted ERROR messages; generated products are incomplete. See the preceding diagnostics."
    }
    if {!$::hdlforge::ran} {error "Run script did not execute any native build commands"}
    ::hdlforge::collect
} result options]
if {$code} {
    ::hdlforge::status failed
    set handle [open [file join $output info failure.txt] w]
    puts $handle [dict get $options -errorinfo]
    close $handle
    puts stderr "HDLFORGE_BUILD_FAILED: $result"
    exit 1
}
::hdlforge::status complete
puts "HDLFORGE_BUILD_COMPLETE: $output"
exit 0
