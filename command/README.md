# Invoke Tasks Documentation

## Overview

The `command` directory contains all the core functionality of Fabrinetes, organized as modular Python tasks using the `invoke` framework. Each task is responsible for a specific aspect of container and image management.

## Directory Structure

```
command/
├── __init__.py          # Package initialization
├── clean_image/         # Image cleanup operations
├── commit/              # Container commit operations
├── exec/                # Container execution commands
├── gen_image/           # Image generation from configs
├── help/                # Help system and documentation
├── kill/                # Container termination
├── list/                # Container and image listing
├── pkg/                 # Package management
├── run/                 # Container execution
├── shell/               # Interactive shell access
└── test/                # Comprehensive testing framework
```

## Core Tasks

### Build Tasks

#### `gen_image/`
- **Purpose**: Modern image generation from TOML configs
- **Features**:
  - Build from base images
  - Restore from tarballs
  - Package installation via `docker exec`
  - Support for both base and regular images
- **Files**: `gen_image.py`

### Container Management

#### `run/`
- **Purpose**: Execute Docker containers with configuration
- **Features**:
  - X11 support for GUI applications
  - Mount management
  - Environment variable handling
  - Duplicate container prevention
- **Files**: `run.py`, `helpers.py`

#### `exec/`
- **Purpose**: Execute commands in running containers
- **Features**:
  - Command execution with output capture
  - Interactive and non-interactive modes
- **Files**: `exec.py`

#### `shell/`
- **Purpose**: Open interactive shells in containers
- **Features**:
  - Interactive bash access
  - Pretty table display of available containers
- **Files**: `shell.py`

#### `kill/`
- **Purpose**: Terminate and remove containers
- **Features**:
  - Force removal of running containers
  - Clean container cleanup
- **Files**: `kill.py`

### Image Management

#### `commit/`
- **Purpose**: Commit running containers to images
- **Features**:
  - Container state validation
  - Image tagging and saving
  - Tarball export
- **Files**: `commit.py`

#### `clean_image/`
- **Purpose**: Remove images and associated containers
- **Features**:
  - Image removal with dependency checking
  - Container cleanup
  - Tarball management
- **Files**: `clean_image.py`

### Information and Help

#### `list/`
- **Purpose**: Display containers and images
- **Features**:
  - Pretty table formatting
  - Grouped by image
  - Status information
- **Files**: `list.py`

#### `help/`
- **Purpose**: Command help and documentation
- **Features**:
  - Command-specific help
  - Argument validation
  - Usage examples
- **Files**: `help.py`

### Package Management

#### `pkg/`
- **Purpose**: Package management and analysis
- **Features**:
  - Package listing from containers
  - Package download with dependencies
  - Offline image creation support
- **Files**: `pkg.py`

### Testing

#### `test/`
- **Purpose**: Comprehensive testing framework
- **Features**:
  - Automated test generation
  - State management
  - Comprehensive coverage
  - Detailed reporting
- **Files**: `test.py`, `README.md`

## Shared Components

### Helper Functions

The tasks use shared helper functions located in `helper_functions/`:

- **`config/`**: Configuration parsing and name generation
- **`image_management.py`**: Image operations (save, load, restore)
- **`package_management.py`**: Package installation and management

### Configuration System

All tasks use TOML configuration files with the following structure:

```toml
[config]
image_name = "container-name:tag"
base_image = "base-image:tag"
mounts = ["host:container", ...]
environment = {VAR = "value"}
network = "host"
command = "bash"
init_env = "path/to/init_env.sh"
```

## Task Execution Flow

### 1. Command Parsing
- Arguments are parsed and validated
- Help is displayed for missing required arguments
- Command-specific help is shown for invalid usage

### 2. Configuration Loading
- TOML config files are loaded and parsed
- Image and container names are generated
- Mounts and environment variables are resolved

### 3. State Management
- Docker images are checked for existence
- Tarballs are located and restored if needed
- Containers are managed (started, stopped, removed)

### 4. Operation Execution
- The specific task operation is performed
- Output is captured and processed
- Results are validated and reported

## Integration Points

### Docker Integration
- All tasks interact with Docker through `ctx.run()` calls
- Image and container operations use Docker CLI
- Mount management handles volume mounting

### File System Integration
- TOML config files define container behavior
- Tarball management for image persistence
- Package lists for reproducible image creation

### User Interface Integration
- Pretty table formatting for lists and help
- Color-coded output for status information
- Interactive prompts for user confirmation

## Error Handling

### Graceful Degradation
- Tasks fail gracefully with informative error messages
- Exit codes are properly set for script integration
- Error details are captured and displayed

### Validation
- Input validation prevents invalid operations
- State validation ensures operations are safe
- Configuration validation catches setup errors

## Best Practices

### Task Design
1. **Single Responsibility**: Each task has one clear purpose
2. **Consistent Interface**: All tasks follow similar argument patterns
3. **Error Handling**: Proper error handling and user feedback
4. **Documentation**: Clear help text and usage examples

### Code Organization
1. **Modular Structure**: Tasks are organized by functionality
2. **Shared Utilities**: Common functionality is shared via helper functions
3. **Configuration Driven**: Behavior is controlled by TOML configs
4. **Test Coverage**: All tasks have comprehensive test coverage

## Development Guidelines

### Adding New Tasks
1. Create new directory under `command/`
2. Implement task function with proper decorators
3. Add help text and argument validation
4. Create comprehensive tests
5. Update documentation

### Modifying Existing Tasks
1. Maintain backward compatibility
2. Update tests for any behavior changes
3. Update help text and documentation
4. Test thoroughly before committing

## Testing Integration

All tasks are tested through the comprehensive test framework:

- **Unit Tests**: Individual task functionality
- **Integration Tests**: Task interaction with Docker
- **State Tests**: Various container and image states
- **Error Tests**: Failure scenarios and error handling

The test framework ensures all tasks work correctly across all supported scenarios and edge cases.

## Performance Considerations

### Optimization Strategies
- **Lazy Loading**: Images and configs are loaded only when needed
- **Caching**: Tarballs provide image persistence
- **Parallel Operations**: Multiple operations can run concurrently
- **Resource Management**: Proper cleanup prevents resource leaks

### Monitoring
- **Execution Time**: Tasks report execution duration
- **Resource Usage**: Docker resource consumption is tracked
- **Error Rates**: Test framework monitors success/failure rates

This modular architecture provides a robust, maintainable, and extensible foundation for Fabrinetes container management operations.
