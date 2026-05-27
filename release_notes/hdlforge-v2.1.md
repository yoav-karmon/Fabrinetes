# Release Notes - hdlforge-v2.1

**Release Date:** 2025-11-25  
**Git Tag:** hdlforge-v2.1  
**Commit:** 9ed7150143a3318c0fcaecb3108464d5447c172c

## Summary
This release focuses on improving the HDLForge help system, enhancing Vivado task handling, and expanding the utility tools with network packet testing and VCD waveform analysis. The help system now provides consistent, comprehensive documentation across all commands. Vivado tasks have been improved with better output handling, progress indicators, and bug fixes for run management. The toolbox has been restructured into a unified 'tool' command with separate network and VCD analyzer sub-tools for better organization and extensibility.

## Added
- Comprehensive help system for all HDLForge commands
- Tool-specific help functions for `vivado` and `Verilator` commands
- Progress messages and spinner indicator for `list_runs` command
- File management commands for Vivado projects (`--file_add`, `--file_remove`)
- Environment variable capture and validation utilities
- Flag-based run_name syntax for command-line interface
- Setup-x11 command for X11 container setup
- **New unified 'tool' command** for utility tools:
  - `--network` sub-tool for sending raw packets (ARP, ICMP, UDP)
  - `--vcd_analyzer` sub-tool for VCD waveform analysis
- **Network utilities** (`hdlforge tool --network`):
  - `send_raw` - Send raw bytes to network interface
  - `send_arp` - Send ARP packets (request/reply)
  - `send_icmp` - Send ICMP packets (ping/echo)
  - `send_udp` - Send UDP packets
- **VCD analyzer integration** (`hdlforge tool --vcd_analyzer`):
  - Professional VCD parsing with signal hierarchy support
  - Timestamp and signal name listing with wildcard filtering
  - Signal value extraction at specific timestamps with multiple radices (hex, int, bin)
  - Edge detection and counting with verbose metadata output
  - Automatic signal validation and error handling
- Automatic network interface listing when interface not specified
- Automatic interface MAC address detection and use as default Ethernet source MAC
- Separate Ethernet MAC address arguments (`--eth_dst_mac`, `--eth_src_mac`) for ARP packets
- Default values display for network commands
- Test script (`test_toolbox.sh`) for verifying network functionality
- VCD analyzer copied from FPGA tools repository and integrated as standalone module

## Changed
- Updated help output format to industry-standard usage syntax: `hdlforge [--project <project_file>] <tool> [--arg value --arg value...]`
- Help system now shows consistent output for `hdlforge`, `hdlforge --help`, and `hdlforge <tool> --help`
- Removed examples sections from help output (replaced with general command structure)
- Made display table more compact with reduced column widths (40 chars for values, 35 for allowed)
- Removed task arguments display table (help section is sufficient)
- Improved `list_runs` output to show formatted table instead of raw TCL output
- Updated bash wrapper to show available tools section (now includes 'tool' command)
- Refactored task handlers into separate modules (`vivado_tasks.py`, `verilator_tasks.py`, `network_tasks.py`, `vcd_analyzer_tasks.py`)
- Refactored helper utilities into separate modules (`display.py`, `environment.py`, `path_utils.py`)
- Renamed `ProjectLoader` to `ProjectFile` for clarity
- Simplified TCL scripts for better maintainability
- Network commands now display default values being used
- Network commands list available network interfaces when interface not specified
- Network ARP packets now default to broadcast destination MAC (FF:FF:FF:FF:FF:FF) for requests
- Network tools automatically use interface MAC address as Ethernet source MAC when not specified
- Command structure changed from `hdlforge toolbox <tool>` to `hdlforge tool --network <tool>`
- Added `--vcd_analyzer` flag to `tool` command for waveform analysis
- Updated all help documentation to reflect new command structure

## Fixed
- Fixed `compile.tcl` to set `$run_obj` variable before use (resolved "can't read run_obj" error)
- Fixed `get_child_runs` output capture to filter Vivado messages and only capture run names
- Fixed duplicate headers in `list_runs` output
- Fixed bitstream command to run full flow with proper skip logic
- Fixed JSON file merging and saving after Vivado property updates
- Improved XPR to JSON update logic to preserve HDLForge properties and handle files not in XPR
- Fixed table display formatting in `print_task_args`
- Fixed symlink path resolution in bash wrapper to work correctly when called via symlink (e.g., `/usr/local/bin/hdlforge`)

## Removed
- Removed emojis from code output (replaced with text markers: `[+]`, `[!]`, `[-]`, `[i]`)
- Removed unused `clean-vivado-logs.sh` script
- Removed Vivado property management functionality (replaced with file management commands)
- Removed obsolete cursor rules
- Removed unused/redundant files
- Removed standalone `toolbox` command (replaced with unified `tool` command)

## Known Issues
None at this time.

## Migration Guide
### Breaking Changes
- Command structure change: `hdlforge toolbox <tool>` → `hdlforge tool --network <tool>`
- The `--step` flag for Vivado commands is deprecated. Use direct step flags instead:
  - `--syn <run_name>` instead of `--step syn`
  - `--impl <run_name>` instead of `--step impl`
  - `--bit <run_name>` instead of `--step bit`
  - `--list_runs` instead of `--step list_runs`
  - etc.

### Deprecations
- The standalone `toolbox` command is deprecated in favor of the unified `tool` command with `--network` flag

## Technical Details
- Help system uses argparse with custom help handlers for consistent output
- Vivado tasks now use `pty=False, hide='stdout'` for cleaner output capture
- Progress indicators use threading for non-blocking spinner display
- Display table uses `tabulate` with `grid` format for compact output
- Network tools use raw sockets (AF_PACKET) for direct network interface access
- Network tools implement proper packet construction with Ethernet, IP, ARP, ICMP, and UDP headers
- Network interface detection reads from `/proc/net/dev` or uses `ip` command
- Interface MAC address detection reads from `/sys/class/net/<interface>/address` or uses `ip` command
- Network tools require root privileges for raw socket operations
- VCD analyzer uses professional parsing with signal hierarchy support and multiple output formats
- VCD analyzer supports wildcard signal matching and edge detection with timestamp filtering
- Bash wrapper uses `readlink -f` to resolve symlinks for correct path detection when called via symlink
- VCD analyzer requires `typeguard` library for type checking (may need installation: `pip install typeguard`)

## Related Commits
- 9ed7150 - Update release notes for hdlforge-v2.1
- f239b9c - Fix symlink path resolution in bash wrapper
- 312cf2b - Add cursor command for tag-with-release-notes
- 48a82ee - Add hardware server scripts for FPGA programming and DNA reading
- 616bc6c - Update .gitignore to ignore Vivado temporary files
- 6466111 - Update release notes for hdlforge-v2.1
- 32ee646 - Fix toolbox ARP to use broadcast MAC and interface MAC detection
- ee94b1e - Add cursor commands for release notes workflow
- 09f874e - Update release notes for hdlforge-v2.1
- dafbcc7 - Add toolbox tool for network packet testing (ARP, ICMP, UDP)
- ad68080 - Update HDLForge help system and improve Vivado task handling
- 0b73efc - Update HDLForge help system and fix Vivado tasks
- 545e728 - Refactor compile.tcl to separate stage handling and improve bit stage logic
- b9a9b49 - Fix HDLForge bitstream command to run full flow with proper skip logic
- 1b9c65f - Update command-line interface for flag-based run_name syntax
- b487f02 - Add file management commands for Vivado
- dc4b34c - Add environment variable capture and validation utilities for HDLForge
- 81ba827 - Rename ProjectLoader to ProjectFile
- bbc2a8e - Refactor task handlers into separate modules
- 5f115a4 - Refactor helper utilities into separate modules

## Files Changed
### Core HDLForge Files
- `hdlforge/project_setup/tasks.py` - Main entry point with updated help system, new tool command structure, and VCD analyzer integration
- `hdlforge/project_setup/vivado_tasks.py` - Vivado task improvements and fixes
- `hdlforge/project_setup/network_tasks.py` - Network utilities (raw packet sending: ARP, ICMP, UDP)
- `hdlforge/project_setup/vcd_analyzer_tasks.py` - VCD waveform analysis wrapper
- `hdlforge/project_setup/vcd_analyzer.py` - Professional VCD parsing and analysis engine
- `hdlforge/project_setup/toolbox_tasks.py` - Legacy network utilities (maintained for backward compatibility)
- `hdlforge/project_setup/display.py` - Compact table display improvements
- `hdlforge/project_setup/hdlforge` - Bash wrapper with updated help format (now includes 'tool' command) and symlink resolution fix
- `hdlforge/project_setup/compile.tcl` - Fixed run_obj variable initialization
- `hdlforge/project_setup/test_toolbox.sh` - Test script for network functionality

### Documentation
- `doc/hdlforge-doc/HDLForge.md` - Updated documentation
- `doc/hdlforge-doc/HDLForge_v2_Migration_Guide.md` - Migration guide updates
