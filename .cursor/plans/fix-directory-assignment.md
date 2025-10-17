# Task Plan: Fix Directory Assignment Logic

## Overview
Fix the directory assignment logic in ContainerInfo where:
- **Tarball Directory** should be the working directory (where tarballs are stored)
- **Working Directory** should be where the config file is located (the project directory)

Currently the logic is backwards - tarball directory is pointing to a nested path that doesn't exist, and working directory is pointing to the wrong location.

## Task Breakdown

### 1. Analyze Current Directory Assignment Logic
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Understand how tarball_directory_resolved and working_directory are currently calculated
- **Status**: ✅ Completed - Found working_directory = os.getcwd() and tarball_directory_resolved = nested path

### 2. Identify Correct Directory Logic
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Determine the correct logic for directory assignments based on user requirements
- **Status**: ✅ Completed - Working directory should be config directory, tarball directory should be current working directory

### 3. Update Directory Assignment Logic
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Fix the directory assignment logic to swap tarball and working directories
- **Status**: ✅ Completed - Updated working_directory to config directory and tarball_directory_resolved to current working directory

### 4. Test Updated Directory Logic
- **Files**: Manual testing
- **Description**: Test status command to verify directories are now assigned correctly
- **Status**: ✅ Completed - Verified all directories now show ✅ (exists, writable)

### 5. Update Documentation
- **Files**: `README.md`, `.cursor/plans/fix-directory-assignment.md`
- **Description**: Update documentation to reflect corrected directory logic
- **Status**: ✅ Completed - Updated README with directory logic explanation

## Design Guidelines Applied
- **Single Source of Truth**: Directory logic centralized in ContainerInfo dataclass
- **File Size Management**: Keep files under ~400 lines by reusing existing functions
- **Code Reuse**: Leverage existing path resolution logic

## Expected Directory Assignment
**Current (Incorrect)**:
- Working Directory: `/DATA/repo/Fabrinetes/containers/fabrinetes-dev-testing/` (config file location)
- Tarball Directory: `/DATA/repo/Fabrinetes/containers/fabrinetes-dev-testing/containers/fabrinetes-testing/` (nested path)

**Fixed (Correct)**:
- Working Directory: `/DATA/repo/Fabrinetes/containers/fabrinetes-dev-testing/` (config file location)
- Tarball Directory: `/DATA/repo/Fabrinetes/` (working directory where tarballs should be stored)
