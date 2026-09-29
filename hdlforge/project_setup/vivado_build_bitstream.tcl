##############################################################################
## Bitstream-only run: open the frozen final implementation checkpoint.
## HDLForge supplies USERID from the source implementation's launch epoch.
## No synthesis, placement, routing, or optimization commands are executed.
##############################################################################
dict for {name value} [dict get $::hdlforge_config parameters] {
    ::hdlforge::apply_parameter $name $value
}
open_checkpoint [dict get $::hdlforge_config input_dcp]
set top [dict get $::hdlforge_config top]
set ::ACTIVE_STEP write_bitstream
write_bitstream -force ${top}.bit
# The design is unchanged. Preserve its original (potentially repaired) LTX
# rather than replacing it with newly generated probe descriptions.
foreach probes [dict get $::hdlforge_config bitstream_probes] {
    file copy -force $probes [file tail $probes]
}
## Force the collector to pick up the original paired probes after any auto-LTX.
set ::hdlforge::copied [dict create]
unset ::ACTIVE_STEP
