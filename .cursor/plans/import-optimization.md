# Import Optimization Task Plan

## Overview
Ensure all Python files follow the code design guideline: "import: all import done on top of file"

## Code Design Guidelines
- Single source of truth: consolidate queries into one source using single data class
- Data classes: put all functions as member functions, call process once then pass as reference
- Import: all import done on top of file

## Task List

### Phase 1: Analysis
1. **Analyze current import patterns across all Python files**
   - Files: All `.py` files in the repository
   - Identify import patterns and violations

2. **Identify files with imports not at the top**
   - Files: Command files, helper files, main files
   - Document specific import issues

### Phase 2: Fixes
3. **Fix imports in command files (build, run, commit, restore)**
   - Files: `command/build/build.py`, `command/run/run.py`, `command/commit/commit.py`, `command/restore/restore.py`
   - Move all imports to top of files

4. **Fix imports in helper_functions files**
   - Files: `helper_functions/command_builder.py`, `helper_functions/config/name_generator.py`
   - Ensure proper import organization

5. **Fix imports in main fabrinetes.py file**
   - Files: `fabrinetes.py`
   - Verify main file imports are correct

### Phase 3: Verification
6. **Verify all imports follow Python best practices**
   - Standard library imports first
   - Third-party imports second
   - Local imports last
   - Alphabetical ordering within groups

7. **Test all files to ensure imports work correctly**
   - Run all commands to verify functionality
   - Check for import errors

### Phase 4: Optimization
8. **Review file sizes and optimize if needed**
   - Keep files under ~400 lines
   - Consolidate common imports if needed

9. **Update README if needed**
   - Document any import-related changes

## Expected Benefits
- Cleaner, more maintainable code
- Better adherence to Python best practices
- Easier debugging and code review
- Consistent code style across the project
