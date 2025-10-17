# Task Plan: Add TOML Key Paths to Status Display

## Overview
Update the status command display to show the TOML key paths for each item being inspected, making it clear which configuration values are being checked. For example, show "Base Image (config.base_image)" instead of just "Base Image".

## Task Breakdown

### 1. Analyze Current Status Display Structure
- **Files**: `helper_functions/status_helper.py`
- **Description**: Understand current status display format and identify where to add TOML key paths
- **Status**: ✅ Completed - Analyzed StatusInfo dataclass and display functions

### 2. Map ContainerInfo Properties to TOML Keys
- **Files**: `helper_functions/config/name_generator.py`, `containers/fabrinetes-dev-testing/config.toml`
- **Description**: Create mapping between ContainerInfo properties and their corresponding TOML key paths
- **Status**: ✅ Completed - Mapped all properties to TOML keys (config, config.base_image, config.image, etc.)

### 3. Create TOML Key Path Mapping Function
- **Files**: `helper_functions/status_helper.py`
- **Description**: Create function to get TOML key path for each status item
- **Status**: ✅ Completed - Added toml_key field to StatusInfo dataclass and updated all status functions

### 4. Update Status Display Labels
- **Files**: `helper_functions/status_helper.py`
- **Description**: Update status display to include TOML key paths in labels
- **Status**: ✅ Completed - Updated format_status_output() to display TOML keys in parentheses

### 5. Test Updated Status Display
- **Files**: Manual testing
- **Description**: Test status command to verify TOML key paths are displayed correctly
- **Status**: ✅ Completed - Verified TOML keys display correctly for all status items

### 6. Update Documentation
- **Files**: `README.md`, `.cursor/plans/add-toml-keys-to-status.md`
- **Description**: Update documentation to reflect new status display format
- **Status**: ✅ Completed - Updated README with TOML key mapping documentation

## Design Guidelines Applied
- **Single Source of Truth**: TOML key mapping centralized in status helper
- **File Size Management**: Keep files under ~400 lines by reusing existing functions
- **Code Reuse**: Leverage existing ContainerInfo structure

## Expected Status Output
```
Config Status:
  Config File (config): ✅ (exists)
    Size: 996.0B
    Modified: 2025-01-15 13:49:22

Image Status:
  Base Image (config.base_image): ✅ (exists)
    Size: 1.2GB
    Created: 2025-01-14 10:30:25
  Main Image (config.image): ❌ (not found)

Tarball Status:
  Base Tarball (config.base_image.tarball_name): ✅ (exists)
    Size: 800MB
    Modified: 2025-01-14 10:30:25
  Main Tarball (config.image.tarball_name): ❌ (not found)

Container Status:
  Container (config.container.name): ✅ (running)
    Created: 2025-01-15 09:15:30

Directory Status:
  Working Directory: ✅ (exists, writable)
  Tarball Directory: ✅ (exists, writable)
  Config Directory: ✅ (exists, writable)
```
