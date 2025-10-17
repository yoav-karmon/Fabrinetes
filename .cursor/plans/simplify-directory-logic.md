# Task Plan: Simplify Directory Logic - Remove Redundant Directories

## Overview
Simplify the directory logic by removing redundant directory concepts:
- **Remove Tarball Directory**: Each tarball path and name is set in config_file, relative or absolute to config_file path
- **Remove Config Directory**: It's the same as Working Directory, use Working Directory instead in code

This follows the single source of truth principle - tarball paths come from config, working directory is the project directory.

## Task Breakdown

### 1. Analyze Current Directory Structure
- **Files**: `helper_functions/config/name_generator.py`, `helper_functions/status_helper.py`
- **Description**: Understand current directory fields and how they're used
- **Status**: ✅ Completed - Found tarball_directory, tarball_directory_resolved, and config_directory fields to remove

### 2. Remove Tarball Directory Fields
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Remove tarball_directory and tarball_directory_resolved fields from ContainerInfo
- **Status**: ✅ Completed - Removed tarball_directory and tarball_directory_resolved fields

### 3. Update Tarball Path Logic
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Update tarball path resolution to be relative/absolute to config file path
- **Status**: ✅ Completed - Updated tarball paths to resolve relative to working directory, added resolved paths for base and main tarballs

### 4. Remove Config Directory Fields
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Remove config_directory field and use working_directory instead
- **Status**: ✅ Completed - Removed config_directory field and updated resolve method to use working_directory

### 5. Update Status Display
- **Files**: `helper_functions/status_helper.py`
- **Description**: Update status display to remove Tarball Directory and Config Directory sections
- **Status**: ✅ Completed - Updated ContainerStatus dataclass and format_status_output to show only Working Directory

### 6. Test Simplified Directory Logic
- **Files**: Manual testing
- **Description**: Test status command to verify simplified directory display works correctly
- **Status**: ✅ Completed - Verified status shows only Working Directory and tarball paths resolve correctly

### 7. Update Documentation
- **Files**: `README.md`, `.cursor/plans/simplify-directory-logic.md`
- **Description**: Update documentation to reflect simplified directory structure
- **Status**: ✅ Completed - Updated README with simplified directory logic explanation

## Design Guidelines Applied
- **Single Source of Truth**: Tarball paths from config, working directory is project directory
- **File Size Management**: Keep files under ~400 lines by removing redundant fields
- **Code Reuse**: Use working_directory instead of separate config_directory

## Expected Directory Structure
**Before (Complex)**:
- Working Directory: `/DATA/repo/Fabrinetes/containers/fabrinetes-dev-testing/`
- Tarball Directory: `/DATA/repo/Fabrinetes/`
- Config Directory: `/DATA/repo/Fabrinetes/containers/fabrinetes-dev-testing/`

**After (Simplified)**:
- Working Directory: `/DATA/repo/Fabrinetes/containers/fabrinetes-dev-testing/`
- Tarball paths: Resolved relative to config file path (from config)

## Expected Status Output
```
Directory Status:
  Working Directory: ✅ (exists, writable)
```
