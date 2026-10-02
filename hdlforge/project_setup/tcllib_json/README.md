# Tcllib JSON reader

Unmodified `json.tcl` and `json_tcl.tcl` from Tcllib tag `tcllib-1-21`,
module `modules/json`:
https://github.com/tcltk/tcllib/tree/tcllib-1-21/modules/json

`license.terms` is copied from that same release. HDLForge freezes this directory
in each run's `snapshot/scripts/_hdlforge/json/` so Vivado does not need a
separately installed Tcllib package. The maintained run script sources the shared
runtime, which loads this reader.
