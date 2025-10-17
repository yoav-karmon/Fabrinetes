# Task Plan: Add --help Command to fabrinetes.py

## Overview
Add a `--help` command that prints usage information without requiring a config file argument. This will be the only command that doesn't need the `--config-file` parameter.

## Task Breakdown

### 1. Analyze Current Help System
- **Files**: `fabrinetes.py`, `helper_functions/config/name_generator.py`
- **Description**: Understand how the current help system works and where to integrate the new `--help` command
- **Status**: ✅ Completed - Analyzed argparse parser structure and help system

### 2. Add --help Argument to Parser
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Add `--help` as a new command choice in the argument parser
- **Status**: ✅ Completed - Added 'help' to command choices and updated help text

### 3. Implement Help Command Logic
- **Files**: `fabrinetes.py`
- **Description**: Add logic to handle the `--help` command and print usage information
- **Status**: ✅ Completed - Added help command handler that calls parser.print_help()

### 4. Update Command Validation
- **Files**: `fabrinetes.py`
- **Description**: Ensure `--help` command doesn't require `--config-file` argument
- **Status**: ✅ Completed - Moved help command handling before container_info creation

### 5. Test Help Command
- **Files**: Test scripts or manual testing
- **Description**: Verify that `./fabrinetes.py --help` works correctly and prints usage information
- **Status**: ✅ Completed - All tests pass, help command works without config file

### 6. Update Documentation
- **Files**: `README.md`, `command/README.md`
- **Description**: Update documentation to reflect the new `--help` command
- **Status**: ✅ Completed - Added Fabrinetes Usage section with help command examples

## Design Guidelines Applied
- **Single Source of Truth**: All help information will be centralized in the argument parser
- **File Size Management**: Keep files under ~400 lines by reusing existing functions
- **Code Reuse**: Leverage existing parser and help infrastructure

## Expected Behavior
- `./fabrinetes.py --help` should print usage information
- `./fabrinetes.py --help` should NOT require `--config-file` argument
- Help output should be consistent with current help format
