# List Task Documentation

## Overview
The `list` task displays Docker containers and images in a pretty table format, grouped by image for easy management.

## Usage
```bash
./fabrinetes list
```

## Features
- **Pretty Table Formatting**: Uses tabulate for clean output
- **Grouped by Image**: Shows multiple containers per image
- **Status Information**: Displays running/stopped status
- **Image Details**: Shows image tags and sizes

## Output Format
- **Image Column**: Docker image name and tag
- **Container Names**: All containers using that image
- **Status**: Running/stopped state
- **Created**: Container creation time

## Integration
- Works with all container management tasks
- Provides overview of Docker environment
- Helps with container identification

## Files
- `list.py`: Main list task implementation
