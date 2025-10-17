# Task Plan: Refactor Status Helper to Follow Design Guidelines

## Overview
Refactor `helper_functions/status_helper.py` to follow design guidelines:
- **Single Source of Truth**: Consolidate all status collection logic into ContainerStatus dataclass
- **Data Classes**: Move all functions as member functions, process once and pass as reference
- **File Size Management**: Keep under ~400 lines by reusing functions and creating helper modules

Current issues:
- Multiple standalone functions instead of member functions
- Repeated Docker client creation
- No caching of operations
- Functions not consolidated into data class

## Task Breakdown

### 1. Analyze Current Status Helper Structure
- **Files**: `helper_functions/status_helper.py`
- **Description**: Understand current function organization and identify violations of design guidelines
- **Status**: ✅ Completed - Found multiple standalone functions, repeated Docker client creation, no caching, scattered logic

### 2. Create Status Collector Data Class
- **Files**: `helper_functions/status_helper.py`
- **Description**: Create StatusCollector dataclass to consolidate all status collection logic
- **Status**: ✅ Completed - Created StatusCollector with cached Docker client and member methods

### 3. Move Functions as Member Methods
- **Files**: `helper_functions/status_helper.py`
- **Description**: Move get_file_status, get_directory_status, get_docker_*_status as member methods
- **Status**: ✅ Completed - All functions moved as member methods of StatusCollector

### 4. Implement Caching and Single Processing
- **Files**: `helper_functions/status_helper.py`
- **Description**: Cache Docker client, file operations, and process each component once
- **Status**: ✅ Completed - Docker client cached in __post_init__, single processing in collect_comprehensive_status

### 5. Create Helper Module for Utilities
- **Files**: `helper_functions/status_utils.py` (new)
- **Description**: Extract utility functions (format_file_size, translate_docker_error) to separate module
- **Status**: ✅ Completed - Created status_utils.py with utility functions to keep main file under 400 lines

### 6. Update ContainerStatus to Use StatusCollector
- **Files**: `helper_functions/status_helper.py`
- **Description**: Update ContainerStatus to use StatusCollector for single source of truth
- **Status**: ✅ Completed - Updated collect_comprehensive_status to use StatusCollector

### 7. Test Refactored Status Helper
- **Files**: Manual testing
- **Description**: Test that refactored status helper works correctly and follows design guidelines
- **Status**: ✅ Completed - Verified status command works correctly with refactored StatusCollector

### 8. Update Documentation
- **Files**: `README.md`, `.cursor/plans/refactor-status-helper.md`
- **Description**: Update documentation to reflect refactored status helper structure
- **Status**: ✅ Completed - Updated task plan with completion status

## Design Guidelines Applied
- **Single Source of Truth**: StatusCollector dataclass consolidates all status logic
- **Data Classes**: All functions as member methods, processed once and passed as reference
- **File Size Management**: Keep under ~400 lines by extracting utilities to separate module

## Expected Refactored Structure
```python
@dataclass
class StatusCollector:
    """Single source of truth for status collection"""
    container_info: ContainerInfo
    docker_client: docker.DockerClient = None
    
    def __post_init__(self):
        # Cache Docker client
        self.docker_client = docker.from_env()
    
    def collect_file_status(self, file_path: str, name: str, toml_key: str = None) -> StatusInfo:
        # Member method for file status
    
    def collect_directory_status(self, dir_path: str, name: str, toml_key: str = None) -> StatusInfo:
        # Member method for directory status
    
    def collect_docker_image_status(self, image_name: str, name: str, toml_key: str = None) -> StatusInfo:
        # Member method for Docker image status
    
    def collect_docker_container_status(self, container_name: str, name: str, toml_key: str = None) -> StatusInfo:
        # Member method for Docker container status
    
    def collect_comprehensive_status(self) -> ContainerStatus:
        # Single method that processes all components once
```

## Benefits
- **Single Source of Truth**: All status logic in one place
- **Performance**: Docker client cached, operations processed once
- **Maintainability**: Clear separation of concerns
- **Reusability**: StatusCollector can be reused across different contexts
