# Task Plan: Rename Tarball Config Keys and Add Path Resolution

## Overview
Rename tarball configuration keys and enhance path resolution:
- **Rename**: `config.base_image.tarball_name` → `config.base_image.tarball_path`
- **Rename**: `config.image.tarball_name` → `config.image.tarball_path`
- **Enhance**: Support environment variables, absolute paths, and relative paths to config file

This follows the single source of truth principle and makes the configuration more flexible and intuitive.

## Task Breakdown

### 1. Analyze Current Tarball Configuration Usage
- **Files**: `helper_functions/config/name_generator.py`, `helper_functions/status_helper.py`, config files
- **Description**: Understand how tarball_name is currently used and where it needs to be updated
- **Status**: ✅ Completed - Found 6 files with tarball_name references across config files, code, and documentation

### 2. Update Config File Examples
- **Files**: `containers/fabrinetes-dev-testing/config.toml`, example configs
- **Description**: Update example config files to use tarball_path instead of tarball_name
- **Status**: ✅ Completed - Updated both config files to use tarball_path instead of tarball_name

### 3. Update ContainerInfo Dataclass
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Update field names and add path resolution logic for environment variables and relative paths
- **Status**: ✅ Completed - Updated ContainerInfo to use tarball_path and integrated path resolution helper function

### 4. Create Path Resolution Helper Function
- **Files**: `helper_functions/config/name_generator.py`
- **Description**: Create helper function to resolve paths with environment variable support
- **Status**: ✅ Completed - Created resolve_tarball_path() method with env var, absolute, and relative path support

### 5. Update Status Helper References
- **Files**: `helper_functions/status_helper.py`
- **Description**: Update TOML key references from tarball_name to tarball_path
- **Status**: ✅ Completed - Updated status helper to use config.base_image.tarball_path and config.image.tarball_path

### 6. Test Path Resolution Features
- **Files**: Manual testing
- **Description**: Test environment variables, absolute paths, and relative paths in tarball configuration
- **Status**: ✅ Completed - Verified all path resolution features work correctly: env vars, absolute paths, relative paths

### 7. Update Documentation
- **Files**: `README.md`, `.cursor/plans/rename-tarball-config-keys.md`
- **Description**: Update documentation to reflect new tarball_path configuration and path resolution features
- **Status**: ✅ Completed - Updated README with tarball_path configuration and path resolution documentation

## Design Guidelines Applied
- **Single Source of Truth**: Tarball paths centralized in ContainerInfo with unified resolution
- **Data Classes**: Path resolution as member function, processed once and passed as reference
- **File Size Management**: Keep files under ~400 lines by creating helper functions

## Expected Configuration Changes
**Before**:
```toml
[config.base_image]
name = "fabrinetes-skeleton"
tag = "latest"
tarball_name = "fabrinetes-skeleton:latest.tar.gz"

[config.image]
name = "fabrinetes-testing"
tag = "latest"
tarball_name = "fabrinetes-testing:latest.tar.gz"
```

**After**:
```toml
[config.base_image]
name = "fabrinetes-skeleton"
tag = "latest"
tarball_path = "fabrinetes-skeleton:latest.tar.gz"  # or "$HOME/tarballs/base.tar.gz" or "/absolute/path.tar.gz"

[config.image]
name = "fabrinetes-testing"
tag = "latest"
tarball_path = "fabrinetes-testing:latest.tar.gz"  # or "$HOME/tarballs/main.tar.gz" or "/absolute/path.tar.gz"
```

## Path Resolution Features
- **Environment Variables**: `$HOME/tarballs/image.tar.gz`
- **Absolute Paths**: `/absolute/path/to/image.tar.gz`
- **Relative Paths**: `relative/path/to/image.tar.gz` (relative to config file)
- **Fallback**: If path doesn't exist, show clear error message
