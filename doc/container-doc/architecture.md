# Fabrinetes Architecture Documentation

## Overview
Fabrinetes is a Docker container management system that provides a unified API for building, running, committing, and restoring containers with consistent naming and configuration management.

## Core Architecture

### 1. ContainerInfo Dataclass
**Location**: `helper_functions/config/name_generator.py` (403 lines)

The `ContainerInfo` dataclass serves as the single source of truth for all container configuration:

```python
@dataclass
class ContainerInfo:
    # Core configuration
    config_file: str
    working_directory: str
    
    # Image configuration
    image_name: str
    image_tag: str
    image_dockerfile: str
    image_tarball: str
    
    # Container configuration
    run_name: str
    
    # Path validation and resolution
    def validate_paths(self) -> List[str]
    def resolve(self, path: str) -> Optional[str]
```

**Key Features**:
- **Path Validation**: Validates all path-related data members
- **Dual Path Display**: Preserves original TOML values for comments, provides resolved paths for execution
- **Error Handling**: Returns clear error messages when validation fails
- **Centralized Naming**: Consistent container and image naming across all commands

### 2. Unified Command Building System
**Location**: `helper_functions/command_builder.py` (427 lines)

The `CommandBuilder` system provides a unified approach to Docker command generation:

```python
class CommandBuilder:
    def __init__(self, command_type: str)
    def set_base_command(self, command: List[str])
    def add_part(self, name: str, cmd_part: CmdPart)
    def build_command(self, container_info) -> Tuple[str, str, List[str]]
```

**CmdPart Class Hierarchy**:
- `CmdPartFlag`: Boolean flags like `--rm`, `--x11`
- `CmdPartArg`: Arguments with values like `-t image_name`
- `CmdPartFile`: File paths with validation like `-f Dockerfile`
- `CmdPartMounts`: Multiple volume mounts from config
- `CmdPartEnv`: Environment variables like `-e WORKDIR=path`
- `CmdPartX11`: X11 support with socket validation
- `CmdPartName`: Container/image names
- `CmdPartHardcoded`: Fixed values without resolution

**Key Features**:
- **Consistent Output**: All commands follow the same format
- **Error Handling**: Unified error handling with `echo` statements
- **Dual Path Display**: Original TOML values in comments, resolved paths in executable commands
- **Reusable Components**: Common command parts can be reused across commands

### 3. Command Structure
**Location**: `command/` directory

Each command follows a consistent pattern:

```python
def command_name(args, container_info):
    """Generate Docker command for specific operation"""
    # Extract arguments
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_command_help()
        return
    
    # Create command builder
    builder = CommandBuilder("Command Type")
    builder.set_base_command(["docker", "command"])
    
    # Add parts
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory"))
    builder.add_part("image_name", CmdPartArg("-t", "image_docker"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    print(commented_str)
    print(execution_str)
```

**Command Files**:
- `build/build.py` (69 lines): Docker build command generation
- `run/run.py` (70 lines): Docker run command generation
- `commit/commit.py` (69 lines): Docker commit command generation
- `restore/restore.py` (37 lines): Docker load command generation

### 4. Dynamic User Setup
**Location**: `containers/*/entrypoint.sh`

Containers use dynamic user creation at runtime:

```bash
#!/bin/bash
# Dynamic user creation based on environment variables
CONTAINER_USER=${CONTAINER_USER:-$(whoami)}
CONTAINER_UID=${CONTAINER_UID:-$(id -u)}
CONTAINER_GID=${CONTAINER_GID:-$(id -g)}
CONTAINER_HOME=${CONTAINER_HOME:-/home/$CONTAINER_USER}

# Create user and group dynamically
groupadd -g $CONTAINER_GID $CONTAINER_USER
useradd -u $CONTAINER_UID -g $CONTAINER_GID -d $CONTAINER_HOME -s /bin/bash $CONTAINER_USER
```

**Key Features**:
- **Runtime User Creation**: Users created dynamically based on environment variables
- **Passwordless Sudo**: Automatic sudo setup for container users
- **Hostname Configuration**: Dynamic hostname setting
- **User Switching**: Proper user switching with gosu

## Design Principles

### 1. Single Source of Truth
- All configuration managed through `ContainerInfo` dataclass
- Consistent naming and path resolution across all commands
- Centralized validation and error handling

### 2. Code Design Guidelines
- **Data Classes**: Put all functions as member functions, call process once then pass as reference
- **Import Organization**: All imports done at top of file
- **File Size Management**: Keep files under ~400 lines by reusing functions

### 3. Error Handling
- **Consistent Error Messages**: All errors use `echo 'error: ...'` format
- **Command Structure Display**: Always show full command structure even on validation failure
- **Piped Execution Support**: Commands designed to work with `| bash` piping

### 4. Dual Path Display
- **Comments**: Show original TOML values (e.g., `cursor/.config:$HOME/.config`)
- **Executable Commands**: Show resolved absolute paths
- **Clear Separation**: Configuration vs execution clearly distinguished

## File Organization

### Core Files
- `fabrinetes.py` (57 lines): Main script entry point
- `helper_functions/config/name_generator.py` (403 lines): ContainerInfo dataclass
- `helper_functions/command_builder.py` (427 lines): Unified command building system

### Command Files
- `command/build/build.py` (69 lines): Build command
- `command/run/run.py` (70 lines): Run command
- `command/commit/commit.py` (69 lines): Commit command
- `command/restore/restore.py` (37 lines): Restore command

### Helper Files
- `command/run/helpers.py` (82 lines): Run command helpers
- `command/help/help.py`: Help system
- `helper_functions/image_management.py`: Image management utilities

## Benefits

### 1. Maintainability
- **Single Source of Truth**: All configuration in one place
- **Consistent Patterns**: All commands follow the same structure
- **Reusable Components**: Common functionality shared across commands

### 2. Reliability
- **Path Validation**: All paths validated before command execution
- **Error Handling**: Clear error messages for troubleshooting
- **Testing**: Comprehensive testing across all commands

### 3. Usability
- **Unified API**: Single command interface for all Docker operations
- **Consistent Output**: Predictable command format and error messages
- **Documentation**: Comprehensive help system and documentation

### 4. Performance
- **Optimized Imports**: All imports at module level for better performance
- **Cached Operations**: Frequently used operations cached at function start
- **Efficient File Sizes**: Files kept under 400 lines for better maintainability

## Future Enhancements

### 1. Additional Commands
- **Clean Images**: Remove unused Docker images
- **Status**: Check container and image status
- **Test**: Run tests in containers

### 2. Enhanced Features
- **Multi-Container Support**: Manage multiple containers simultaneously
- **Configuration Templates**: Pre-built configuration templates
- **Advanced Mounting**: More sophisticated volume mounting options

### 3. Integration
- **CI/CD Integration**: Seamless integration with build pipelines
- **Cloud Support**: Support for cloud container platforms
- **Monitoring**: Container health monitoring and alerting

This architecture provides a solid foundation for Docker container management with consistent patterns, reliable error handling, and maintainable code structure.

---

## Document History

**Last Updated:** Commit `0dfcbd30f42c9be4be92bcdbfb1507dd1fad77f3` - Reorganize container documentation into container-doc/ subdirectory (2025-11-11)
