# Archive Directory

This directory contains legacy utility scripts and standalone tools that are not currently integrated into the HDLForge system.

## Archived Files

### TCL Scripts
- **`check_timing.tcl`** - Standalone Vivado timing analysis utility
- **`compile_generic.tcl`** - Generic compilation script
- **`embed.tcl`** - Vivado embedding utility for reading/writing data
- **`generate_sources.tcl`** - Vivado source generation script
- **`implement.tcl`** - Vivado implementation script
- **`list_files.tcl`** - Vivado file listing utility
- **`reset_all.tcl`** - Vivado reset utility
- **`synth.tcl`** - Vivado synthesis script

### Python Scripts
- **`compile_vunit.py`** - VUnit compilation utility
- **`diff_file.py`** - File comparison utility
- **`extract_and_plot.py`** - Data extraction and plotting utility
- **`generate_sources.py`** - Source generation utility
- **`get_file_list.py`** - File listing utility
- **`list_files.py`** - File listing utility
- **`vivado_prj_mng.py`** - Vivado project management utility
- **`warning.py`** - Warning utility

### Shell Scripts
- **`get_project_files.sh`** - Project file extraction script
- **`log_step.sh`** - Logging utility script

## Status

These files were moved to archive on $(date) because they are not referenced by the main HDLForge system (`tasks.py`) or the main entry point (`hdlforge` script).

## Current HDLForge Files

The following files remain in the main directory as they are actively used:
- `tasks.py` - Main HDLForge script
- `compile.tcl` - Referenced by tasks.py
- `project_tool.tcl` - Referenced by tasks.py
- `hdlforge` - Main entry point script
- `HDLForge_Documentation.toml` - Documentation

## Future Use

These archived files may be useful as standalone utilities or could potentially be integrated into HDLForge in the future. They are preserved here for reference and potential future development.