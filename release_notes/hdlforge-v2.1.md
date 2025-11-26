# Release Notes - hdlforge-v2.1

**Release Date:** 2025-11-25  
**Git Tag:** hdlforge-v2.1  
**Commit:** 312cf2bc9f8bc1689011487180c735fd53de807f

## Summary
This release focuses on improving the HDLForge help system, enhancing Vivado task handling, and adding a new toolbox tool for network packet testing. The help system now provides consistent, comprehensive documentation across all commands. Vivado tasks have been improved with better output handling, progress indicators, and bug fixes for run management. A new toolbox tool has been added for sending raw network packets (ARP, ICMP, UDP) for testing and debugging purposes.

## Added
- Comprehensive help system for all HDLForge commands
- Tool-specific help functions for `vivado` and `Verilator` commands
- Progress messages and spinner indicator for `list_runs` command
- File management commands for Vivado projects (`--file_add`, `--file_remove`)
- Environment variable capture and validation utilities
- Flag-based run_name syntax for command-line interface
- Setup-x11 command for X11 container setup
- **New toolbox tool** for network packet testing:
  - `send_raw` - Send raw bytes to network interface
  - `send_arp` - Send ARP packets (request/reply)
  - `send_icmp` - Send ICMP packets (ping/echo)
  - `send_udp` - Send UDP packets
- Automatic network interface listing when interface not specified
- Automatic interface MAC address detection and use as default Ethernet source MAC
- Separate Ethernet MAC address arguments (`--eth_dst_mac`, `--eth_src_mac`) for ARP packets
- Default values display for toolbox commands
- Test script (`test_toolbox.sh`) for verifying toolbox functionality

## Changed
- Updated help output format to industry-standard usage syntax: `hdlforge [--project <project_file>] <tool> [--arg value --arg value...]`
- Help system now shows consistent output for `hdlforge`, `hdlforge --help`, and `hdlforge <tool> --help`
- Removed examples sections from help output (replaced with general command structure)
- Made display table more compact with reduced column widths (40 chars for values, 35 for allowed)
- Removed task arguments display table (help section is sufficient)
- Improved `list_runs` output to show formatted table instead of raw TCL output
- Updated bash wrapper to show available tools section (includes new toolbox tool)
- Refactored task handlers into separate modules (`vivado_tasks.py`, `verilator_tasks.py`, `toolbox_tasks.py`)
- Refactored helper utilities into separate modules (`display.py`, `environment.py`, `path_utils.py`)
- Renamed `ProjectLoader` to `ProjectFile` for clarity
- Simplified TCL scripts for better maintainability
- Toolbox commands now display default values being used
- Toolbox commands list available network interfaces when interface not specified
- Toolbox ARP packets now default to broadcast destination MAC (FF:FF:FF:FF:FF:FF) for requests
- Toolbox automatically uses interface MAC address as Ethernet source MAC when not specified

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

## Known Issues
None at this time.

## Migration Guide
### Breaking Changes
None - this is a backward-compatible release.

### Deprecations
- The `--step` flag for Vivado commands is deprecated. Use direct step flags instead:
  - `--syn <run_name>` instead of `--step syn`
  - `--impl <run_name>` instead of `--step impl`
  - `--bit <run_name>` instead of `--step bit`
  - `--list_runs` instead of `--step list_runs`
  - etc.

## Technical Details
- Help system uses argparse with custom help handlers for consistent output
- Vivado tasks now use `pty=False, hide='stdout'` for cleaner output capture
- Progress indicators use threading for non-blocking spinner display
- Display table uses `tabulate` with `grid` format for compact output
- Toolbox tool uses raw sockets (AF_PACKET) for direct network interface access
- Toolbox implements proper packet construction with Ethernet, IP, ARP, ICMP, and UDP headers
- Network interface detection reads from `/proc/net/dev` or uses `ip` command
- Interface MAC address detection reads from `/sys/class/net/<interface>/address` or uses `ip` command
- Toolbox requires root privileges for raw socket operations
- Bash wrapper uses `readlink -f` to resolve symlinks for correct path detection when called via symlink

## Related Commits
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
- `hdlforge/project_setup/tasks.py` - Main entry point with updated help system and toolbox integration
- `hdlforge/project_setup/vivado_tasks.py` - Vivado task improvements and fixes
- `hdlforge/project_setup/toolbox_tasks.py` - New toolbox tool for network packet sending
- `hdlforge/project_setup/display.py` - Compact table display improvements
- `hdlforge/project_setup/hdlforge` - Bash wrapper with updated help format (includes toolbox) and symlink resolution fix
- `hdlforge/project_setup/compile.tcl` - Fixed run_obj variable initialization
- `hdlforge/project_setup/test_toolbox.sh` - Test script for toolbox functionality

### Documentation
- `doc/hdlforge-doc/HDLForge.md` - Updated documentation
- `doc/hdlforge-doc/HDLForge_v2_Migration_Guide.md` - Migration guide updates

### Scripts
- `setup.sh` - Container operations refactoring

