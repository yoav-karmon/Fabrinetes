# Shared runtime sourced explicitly by each maintained run.tcl.
namespace eval ::hdlforge {
    variable copied [dict create]
    variable ran 0
    variable routed 0
    variable design_declared 0
}

# The runner owns manifest writes. Encode fields to keep multiline Tcl values
# on one stdout line without a second journal or a concurrent JSON writer.
proc ::hdlforge::emit {kind args} {
    set fields [list HDLFORGE_EVENT $kind]
    foreach value $args {lappend fields [binary encode hex [encoding convertto utf-8 $value]]}
    puts [join $fields "\t"]
    flush stdout
}

proc ::hdlforge::status {value} {emit status $value}

proc ::hdlforge::collect {} {
    variable copied
    set output [dict get $::hdlforge_config output]
    foreach {pattern folder} {*.dcp artifacts *.rpt artifacts *.rpx artifacts *.pb artifacts *.bit artifacts *.ltx artifacts *.mmi artifacts} {
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
        if {[file isfile [file join $output artifacts $name]]} {
            emit last_routed_checkpoint $name
        }
    }
}

# Run scripts declare the design; JSON carries only launch/snapshot inputs.
proc ::hdlforge::design {top part} {
    variable design_declared
    foreach value [list $top $part] {
        if {![regexp {^[A-Za-z0-9_-]+$} $value]} {error "Invalid design identity: $value"}
    }
    foreach key {top part} {
        set value [set $key]
        if {[dict exists $::hdlforge_config parent_$key] &&
            [dict get $::hdlforge_config parent_$key] ne $value} {
            error "Implementation $key differs from the selected synthesis"
        }
        dict set ::hdlforge_config $key $value
        emit $key $value
    }
    set design_declared 1
}

# Resolve a declared logical input to its frozen file, including producer latest
# selections. The caller chooses read_verilog/read_ip/read_xdc/source and options.
proc ::hdlforge::source_path {name} {
    foreach entry [dict get $::hdlforge_config sources] {
        if {[dict get $entry name] eq $name} {return [dict get $entry path]}
    }
    error "Undeclared snapshot source: $name"
}

proc ::hdlforge::event {event stage elapsed command} {
    emit stage [clock format [clock seconds] -gmt 1 -format %Y-%m-%dT%H:%M:%SZ] $event $stage $elapsed $command
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
    emit bitstream_timestamp $epoch $userid
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

proc ::hdlforge::run {script arguments} {
    set base [file dirname $script]
    source [file join $base _hdlforge json json.tcl]
    if {[llength $arguments] > 2} {error "Expected manifest.json path and optional run ID"}
    set path [expr {[llength $arguments] ? [lindex $arguments 0] : [file join $base .. .. manifest.json]}]
    set path [file normalize $path]
    set base [file dirname $path]
    set handle [open $path r]
    fconfigure $handle -encoding utf-8
    set ::hdlforge_config [::json::json2dict [read $handle]]
    close $handle
    if {[llength $arguments] == 2} {
        set identity [lindex $arguments 1]
        if {$identity ne [dict get $::hdlforge_config run_id]} {
            error "Manifest run identity does not match selected attempt"
        }
    }
    foreach key {script output output_root project_root input_dcp bitstream_source logs_dir artifacts_dir work_dir} {
        if {[dict exists $::hdlforge_config $key] && [dict get $::hdlforge_config $key] ne ""} {
            dict set ::hdlforge_config $key [file normalize [file join $base [dict get $::hdlforge_config $key]]]
        }
    }
    foreach key {sources} {
        set entries {}
        foreach entry [dict get $::hdlforge_config $key] {
            dict set entry path [file normalize [file join $base [dict get $entry path]]]
            lappend entries $entry
        }
        dict set ::hdlforge_config $key $entries
    }
    foreach key {bitstream_probes} {
        if {![dict exists $::hdlforge_config $key]} {continue}
        set entries {}
        foreach entry [dict get $::hdlforge_config $key] {
            lappend entries [file normalize [file join $base $entry]]
        }
        dict set ::hdlforge_config $key $entries
    }
    set ::np_project_root [dict get $::hdlforge_config project_root]
    set output [dict get $::hdlforge_config output]
    set code [catch {
    ::hdlforge::status initializing
    if {[dict get $::hdlforge_config stage] eq "ip"} {
        set entries {}
        set index 0
        foreach entry [dict get $::hdlforge_config sources] {
            set original [dict get $entry path]
            if {[file extension $original] ni {.xci .xcix}} {
                lappend entries $entry
                continue
            }
            set destination [file join $output work ip_sources $index]
            file mkdir $destination
            if {[file extension $original] eq ".xci"} {
                set destination [file join $destination [file rootname [file tail $original]]]
                file copy -force [file dirname $original] $destination
            } else {
                file copy -force $original [file join $destination [file tail $original]]
            }
            dict set entry path [file join $destination [file tail $original]]
            lappend entries $entry
            incr index
        }
        dict set ::hdlforge_config sources $entries
    }
    # Also enforce the frozen hash when a snapshot is launched without Python.
    if {[dict get $::hdlforge_config stage] in {impl bitstream}} {
        set checkpoint [dict get $::hdlforge_config input_dcp]
        set actual [regexp -inline {[a-f0-9]{64}} [exec sha256sum -- $checkpoint]]
        if {$actual ne [dict get $::hdlforge_config input_dcp_sha256]} {
            error "Parent checkpoint changed; create a new implementation run"
        }
    }
    cd [dict get $::hdlforge_config work_dir]
    emit tool_version [version]
    set expected [dict get $::hdlforge_config vivado_version]
    if {$expected ne "" && [version -short] ne $expected} {error "Expected Vivado $expected; found [version -short]"}
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
    uplevel #0 [list source $script]
    if {[dict get $::hdlforge_config stage] ne "bitstream" && !$::hdlforge::design_declared} {
        error "Run Tcl must declare its identity with ::hdlforge::design TOP PART"
    }
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
    emit failure [dict get $options -errorinfo]
    puts stderr [dict get $options -errorinfo]
    puts stderr "HDLFORGE_BUILD_FAILED: $result"
    exit 1
}
::hdlforge::status complete
puts "HDLFORGE_BUILD_COMPLETE: $output"
exit 0

}
