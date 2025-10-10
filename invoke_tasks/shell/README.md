# Shell Task Documentation

## Overview
The `shell` task opens interactive bash shells in running Docker containers, providing a convenient way to work inside containers.

## Usage
```bash
# Open shell in container
./fabrinetes shell --container-name <container-name>

# Show help
./fabrinetes shell
```

## Arguments
- `--container-name`: Name of running container (required)

## Features
- **Interactive Access**: Opens bash shell in container
- **Container Validation**: Verifies container is running
- **Pretty Display**: Shows available containers in table format
- **Easy Selection**: Lists containers with ready-to-use commands

## Process Flow
1. **Container Check**: Verify container exists and is running
2. **Shell Launch**: Start interactive bash session
3. **Environment**: Preserve container environment
4. **Exit Handling**: Return to host when shell exits

## Files
- `shell.py`: Main shell task implementation

## Integration
- Works with `run` task for container access
- Provides alternative to `exec` for interactive work
- Integrates with container management system
