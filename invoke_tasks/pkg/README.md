# Pkg Task Documentation

## Overview
The `pkg` task manages packages in Docker containers, including listing installed packages and downloading packages with dependencies for offline builds.

## Usage
```bash
# List packages in container
./fabrinetes pkg --container-name <container-name>

# Download packages with dependencies
./fabrinetes pkg --container-name <container-name> --download

# Show help
./fabrinetes pkg
```

## Arguments
- `--container-name`: Name of running container (required)
- `--download`: Download packages with dependencies (optional)

## Features
- **Package Listing**: Shows installed apt packages with descriptions
- **Dependency Download**: Downloads packages with all dependencies
- **Offline Build Support**: Creates package caches for offline builds
- **Pretty Tables**: Displays package information in formatted tables

## Process Flow
1. **Container Validation**: Verify container is running
2. **Package Analysis**: List installed packages
3. **Dependency Resolution**: Find package dependencies
4. **Download**: Download packages and dependencies
5. **Cache Creation**: Create offline package cache

## Files
- `pkg.py`: Main pkg task implementation

## Integration
- Works with `run` task for container access
- Supports offline build workflows
- Integrates with package management systems
