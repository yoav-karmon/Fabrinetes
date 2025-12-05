# Release Notes - hdlforge-v2.2

**Release Date:** 2025-12-05  
**Git Tag:** hdlforge-v2.2  
**Commit:** c65f1204264b7d3d1538e970988406df9c38d103

## Summary
This release introduces LLM orchestration mode, enabling HDLForge to execute commands from project JSON configuration files without requiring the `--tool` flag. This allows for simplified command invocation using natural language paths (e.g., `hdlforge arp_test sim build`). Additional improvements include bash completion support, tshark wrapper tool for packet analysis, hardware manager for FPGA programming, enhanced VCD analyzer documentation, and improved path resolution for VCD filenames.

## Added
- **LLM Orchestration Mode**: When `--tool` is not provided, HDLForge automatically enters orchestration mode:
  - Reads command paths from `LLM_orch` section in project JSON files
  - Supports natural language command paths (e.g., `hdlforge arp_test sim build`)
  - Automatically resolves and executes commands from JSON configuration
  - Generic implementation using `jq` for flexible JSON path parsing
  - Works with any JSON structure under `LLM_orch`
  - Lists available command paths when path not found
- **Bash Completion Script** (`hdlforge_completion.bash`):
  - Tab completion support for HDLForge commands
  - Tool name completion
  - Argument completion for various tools
  - Project file auto-detection and completion
- **tshark Wrapper Tool** (`hdlforge --tool tsharkWrapper`):
  - Wrapper for tshark packet analysis tool
  - Integrated into HDLForge tool ecosystem
  - Consistent command-line interface
- **Hardware Manager Tool** (`hdlforge --tool hw_manager`):
  - FPGA programming and hardware management
  - Integrated into HDLForge tool ecosystem
- **VCD Filename Path Resolution**:
  - Automatic resolution of relative VCD filenames to absolute paths
  - Preserves invocation directory context for relative paths
  - Works correctly when changing directories during execution
- **Enhanced VCD Analyzer Documentation**:
  - Comprehensive documentation updates in `HDLForge-VCD-Analyzer.md`
  - Improved examples and usage patterns
  - Better integration guidance

## Changed
- **Command Structure**: All commands now require `--tool` flag (or use LLM orchestration mode)
- **VCD Analyzer Arguments**: Renamed for consistency across all commands
- **Help Output**: Updated to show new tools (tsharkWrapper, hw_manager)
- **Bash Completion**: Updated to reflect new command structure and tools
- **VCD Analyzer Implementation**: Refactored for better maintainability and performance
- **tshark Wrapper**: Enhanced with improved argument handling

## Fixed
- **VCD Filename Path Resolution**: Fixed relative path handling when changing directories
- **Bash Completion**: Updated to work with new `--tool` flag structure
- **VCD Analyzer**: Improved argument consistency and error handling

## Removed
- None

## Known Issues
None at this time.

## Migration Guide
### Breaking Changes
- **LLM Orchestration Mode**: When `--tool` is not provided, HDLForge now enters orchestration mode instead of showing help. To show help, use `hdlforge --help` or `hdlforge --tool <tool> --help`
- **Command Structure**: All direct tool commands now require `--tool` flag:
  - Old: `hdlforge vivado --syn <run>` (if tool was optional)
  - New: `hdlforge --tool vivado --syn <run>`
- **LLM Orchestration Alternative**: Use natural language paths instead:
  - `hdlforge <profile> <category> <action>` (e.g., `hdlforge arp_test sim build`)
  - Commands are read from `LLM_orch` section in project JSON files

### New Features
- **LLM Orchestration Mode**: Configure commands in project JSON under `LLM_orch`:
  ```json
  {
    "LLM_orch": {
      "arp_test": {
        "sim": {
          "build": "hdlforge --tool verilator --step build --SimTargetName arp_test"
        }
      }
    }
  }
  ```
- **Bash Completion**: Source the completion script for tab completion:
  ```bash
  source /path/to/hdlforge_completion.bash
  ```

## Technical Details
- LLM orchestration mode uses `jq` for JSON parsing (requires `jq` to be installed)
- JSON path building skips flags (e.g., `--project`) and only uses positional arguments
- Commands are executed recursively (fetched command can call `hdlforge` again)
- VCD filename resolution happens before directory changes to preserve relative path context
- Bash completion script uses dynamic command discovery
- tshark wrapper provides consistent interface to tshark functionality
- Hardware manager integrates FPGA programming workflows

## Related Commits
- c65f120 - Add bash completion script for hdlforge
- 9cfe6a3 - Add VCD analyzer documentation
- 4b25b12 - Add tshark wrapper tool
- 763f09e - Rename VCD analyzer arguments for consistency
- 29c221d - Refactor hdlforge CLI to use --tool flag and add LLM orchestration mode
- 1021216 - Update release notes for hdlforge-v2.1
- 9dda26c - Add unified tool command with network and VCD analyzer integration
- 9ed7150 - Update release notes for hdlforge-v2.1
- f239b9c - Fix symlink path resolution in bash wrapper
- 312cf2b - Add cursor command for tag-with-release-notes
- 48a82ee - Add hardware server scripts for FPGA programming and DNA reading

## Files Changed
### Core HDLForge Files
- `hdlforge/project_setup/hdlforge` - Added LLM orchestration mode, VCD filename path resolution
- `hdlforge/project_setup/tasks.py` - Updated for new tool structure, added tsharkWrapper and hw_manager
- `hdlforge/project_setup/hdlforge_completion.bash` - Bash completion script for HDLForge
- `hdlforge/project_setup/tshark_wrapper_tasks.py` - tshark wrapper tool implementation
- `hdlforge/project_setup/vcd_analyzer_tasks.py` - VCD analyzer argument consistency updates
- `hdlforge/project_setup/vcd_analyzer.py` - VCD analyzer refactoring and improvements

### Documentation
- `doc/hdlforge-doc/HDLForge-VCD-Analyzer.md` - Enhanced VCD analyzer documentation

### New Files
- `hdlforge/project_setup/hw_manager_tasks.py` - Hardware manager tool (new)
- `hdlforge/project_setup/test_dir/test_packets.pcap.tshark_output.txt` - Test output file

