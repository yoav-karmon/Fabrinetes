# Run Task Documentation

## Overview
The `run` task executes Docker containers with configuration from TOML files, providing X11 support, mount management, and duplicate container prevention.

## Usage
```bash
# Run container from config
./fabrinetes run --file <config-file> [--rm] [--usb] [--host-net] [--no-ask]

# Show help
./fabrinetes run
```

## Arguments
- `--file`: Path to TOML config file (required)
- `--rm`: Remove container when it stops (optional)
- `--usb`: Enable USB support (optional)
- `--host-net`: Enable host networking (optional, required for NIC access)
- `--no-ask`: Skip confirmation prompts (optional)

## Features
- **Configuration-Driven**: Uses TOML config files
- **X11 Support**: GUI application support
- **Mount Management**: Flexible volume mounting
- **Duplicate Prevention**: Prevents multiple instances
- **Environment Variables**: Custom environment setup

## Process Flow
1. **Config Loading**: Load and parse TOML config
2. **Image Availability**: Check/restore image if needed
3. **Container Check**: Verify no duplicate containers
4. **X11 Setup**: Configure X11 forwarding
5. **Container Start**: Start container with configuration
6. **Status Report**: Display container information

## Files
- `run.py`: Main run task implementation
- `helpers.py`: Helper functions for X11 and mounts

## Integration
- Uses `gen_image` for image building
- Works with `exec` and `shell` for container access
- Integrates with configuration system
