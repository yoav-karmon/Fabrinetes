# Task Plan: Update No-Argument Display to Show Only Usage

## Overview
Update the behavior when `fabrinetes.py` is run with no arguments to display only the usage part (like `usage: fabrinetes.py [-h] [--cmd ...]`) instead of the full help message with examples and descriptions.

## Task Breakdown

### 1. Analyze Current No-Argument Behavior
- **Files**: `fabrinetes.py`
- **Description**: Understand how the current no-argument behavior works and what it displays
- **Status**: ✅ Completed - Analyzed that no-args shows full help, need to change to usage-only

### 2. Identify Usage-Only Display Method
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Find or create a method to display only the usage line without full help text
- **Status**: ✅ Completed - Found `parser.print_usage()` method for usage-only display

### 3. Update No-Argument Handler
- **Files**: `fabrinetes.py`
- **Description**: Modify the no-argument condition to call usage-only display instead of full help
- **Status**: ✅ Completed - Changed `parser.print_help()` to `parser.print_usage()`

### 4. Test Updated Behavior
- **Files**: Manual testing
- **Description**: Verify that `./fabrinetes.py` (no args) shows only usage line
- **Status**: ✅ Completed - No-args now shows only usage line as requested

### 5. Ensure Help Command Still Works
- **Files**: Manual testing
- **Description**: Verify that `./fabrinetes.py --cmd help` still shows full help
- **Status**: ✅ Completed - All help methods work correctly (--cmd help, -h)

### 6. Update Documentation
- **Files**: `README.md`, `.cursor/plans/update-no-arg-display.md`
- **Description**: Update documentation to reflect the new no-argument behavior
- **Status**: ✅ Completed - Updated README with new help command behavior

## Design Guidelines Applied
- **Single Source of Truth**: Usage information centralized in argparse parser
- **File Size Management**: Keep files under ~400 lines by reusing existing functions
- **Code Reuse**: Leverage existing argparse functionality

## Expected Behavior
- `./fabrinetes.py` (no args) → Shows only: `usage: fabrinetes.py [-h] [--cmd ...]`
- `./fabrinetes.py --cmd help` → Shows full help with examples and descriptions
- `./fabrinetes.py -h` → Shows full help (argparse default behavior)
