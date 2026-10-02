#!/usr/bin/env python3
"""Execute the real HDLForge Tcl driver using libtcl and fake Vivado commands."""

import ctypes
import ctypes.util
import os
from pathlib import Path
import shutil
import sys


library_path = ctypes.util.find_library("tcl8.6")
if not library_path:
    vivado = shutil.which('vivado')
    # HDLForge's test PATH can point at this stub. Use the configured installation
    # from XILINX_VIVADO, or another Vivado executable on the inherited PATH.
    roots = [Path(os.environ['XILINX_VIVADO'])] if os.environ.get('XILINX_VIVADO') else []
    roots.extend(Path(folder).parent for folder in os.get_exec_path()
                 if (Path(folder) / 'vivado').is_file())
    installation = next((root for root in roots if (root / 'lib/lnx64.o/libtcl8.6.so').is_file()), None)
    if installation is None:
        raise RuntimeError('Offline Tcl fixture requires system Tcl 8.6 or a Vivado Tcl library')
    library_path = str(installation / 'lib/lnx64.o/libtcl8.6.so')
    os.environ.setdefault('TCL_LIBRARY', str(installation / 'tps/tcl/tcl8.6'))
library = ctypes.CDLL(library_path)
library.Tcl_CreateInterp.restype = ctypes.c_void_p
library.Tcl_Init.argtypes = [ctypes.c_void_p]
library.Tcl_Eval.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
library.Tcl_EvalFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
library.Tcl_GetStringResult.argtypes = [ctypes.c_void_p]
library.Tcl_GetStringResult.restype = ctypes.c_char_p
interpreter = library.Tcl_CreateInterp()
library.Tcl_Init(interpreter)
for flag in ("-log", "-journal", "-messageDb"):
    if flag in sys.argv:
        Path(sys.argv[sys.argv.index(flag) + 1]).write_text("stub\n")
stub = r'''
proc record {name args} {
    set handle [open calls.log a]
    puts $handle [list $name {*}$args]
    close $handle
    if {[info exists ::env(FAIL_STAGE)] && $name eq $::env(FAIL_STAGE)} {error "injected $name failure"}
}
proc version {args} {return 2025.1}
proc exit {code} {set ::exit_code $code; error stub_exit}
proc current_project {args} {return project}
proc current_design {args} {return design}
proc get_msg_config {args} {return 0}
proc get_property {name args} {
    if {$name eq "default_lib"} {return xil_defaultlib}
    if {$name eq "IP_FILE"} {return [lindex $args end]}
    return ""
}
proc current_fileset {args} {return sources_1}
proc get_debug_cores {args} {return {}}
proc get_files {args} {
    if {[lsearch $args -filter] >= 0} {return {}}
    if {[lsearch $args -of_objects] >= 0} {return {/ip/constraints/impl.xdc /ip/constraints/shared.xdc}}
    return [lindex $args end]
}
proc get_ips {args} {return [lindex $args end]}
foreach command {create_project set_param set_property read_verilog read_vhdl read_ip read_xdc add_files
                 synth_design synth_ip generate_target open_checkpoint link_design opt_design place_design phys_opt_design route_design
                 set_msg_config create_msg_db close_msg_db implement_debug_core} {
    proc $command {args} [format {record %s {*}$args} $command]
}
proc artifact {path} {set f [open $path w]; puts $f artifact; close $f}
proc write_checkpoint {args} {record write_checkpoint {*}$args; artifact [lindex $args end]}
proc write_bitstream {args} {record write_bitstream {*}$args; artifact [lindex $args end]}
proc write_mem_info {args} {artifact [lindex $args end]}
proc write_debug_probes {args} {artifact [lindex $args end].ltx}
proc generate_parallel_reports {args} {
    record generate_parallel_reports {*}$args
    foreach command [lindex $args 1] {
        foreach flag {-file -rpx -pb} {
            set index [lsearch $command $flag]
            if {$index >= 0} {artifact [lindex $command [expr {$index + 1}]]}
        }
    }
}
'''
result = library.Tcl_Eval(interpreter, stub.encode())
if result:
    raise RuntimeError(library.Tcl_GetStringResult(interpreter).decode())
config_path = sys.argv[sys.argv.index("-tclargs") + 1]
# config paths are fixture-generated; escape Tcl special characters anyway.
escaped = config_path.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("[", "\\[")
library.Tcl_Eval(interpreter, f'set argv [list "{escaped}"]'.encode())
arguments = sys.argv[sys.argv.index('-tclargs') + 2:]
if arguments:
    library.Tcl_Eval(interpreter, f'lappend argv {arguments[0]}'.encode())
driver = sys.argv[sys.argv.index("-source") + 1]
status = library.Tcl_EvalFile(interpreter, driver.encode())
if status:
    print(library.Tcl_GetStringResult(interpreter).decode(), file=sys.stderr)
library.Tcl_Eval(interpreter, b"set ::exit_code")
result = library.Tcl_GetStringResult(interpreter).decode()
sys.exit(int(result) if result.isdigit() else 99)
