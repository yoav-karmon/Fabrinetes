#!/usr/bin/env python3

import os
import datetime
import pathlib
from invoke import task
from .helpers import setup_x11_support, resolve_mounts, printlocals
from helper_functions.name_generator import get_container_info
from helper_functions.image_management import ensure_image_available, convert_to_docker_format

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")

def run(args, container_info):
    """Run a Docker container with the specified configuration"""
    from invoke_tasks.help.help import show_run_help
    
    # Extract arguments from args object
    rm = getattr(args, 'rm', False)
    verbose = getattr(args, 'verbose', False)
    x11 = getattr(args, 'x11', True)
    no_x11 = getattr(args, 'no_x11', False)
    usb = getattr(args, 'usb', False)
    ask = getattr(args, 'ask', True)
    help_flag = getattr(args, 'help', False)
    
    # Handle x11 flag logic
    x11_enabled = x11 and not no_x11
    
    # Check for help flag
    if help_flag:
        show_run_help()
        return
    
    # Generate container name
    container_name = container_info.run_name
    if not container_name:
        return
    
    command = 'bash'  # Default command
    mounts = container_info.mounts
    environment = {}  # Default empty environment
    X11_path = container_info.x11_path
    image_name = container_info.image_docker
    
    # Build docker command
    cmd_parts = ["docker", "run", "-dit"]
    
    # Add WORKDIR environment variable (always)
    cmd_parts.extend(["-e", f"WORKDIR={container_info.config_directory}"])
    
    if rm:
        cmd_parts.append("--rm")
    
    # Set up X11 support using helper function
    cmd_parts = setup_x11_support(x11, X11_path, cmd_parts)
    
    if usb:
        cmd_parts.append("-v /dev/bus/usb:/dev/bus/usb")
    
    # Add environment variables
    for key, value in environment.items():
        cmd_parts.append(f"-e {key}={value}")
    
    # Resolve and add mounts
    relative_path = pathlib.Path(container_info.config_directory)
    resolved_mounts = resolve_mounts(mounts, relative_path)
    
    for host_path, container_path in resolved_mounts:
        cmd_parts.append(f"-v {host_path}:{container_path}")
    
    # Add container name and image
    cmd_parts.extend(["--name", container_name, convert_to_docker_format(image_name)])
    
    # Add command
    cmd_parts.append(command)
    
    # Print configuration if verbose
    if verbose:
        printlocals(locals(), verbose=True)
    
    # Output the Docker command to stdout in a readable format with comments
    docker_command = " ".join(cmd_parts)
    
    # Print formatted version for readability with aligned comments
    print("Docker Command:")
    print("=" * 50)
    
    # Calculate the maximum width for alignment
    max_width = 0
    lines = []
    
    # Build all lines first to calculate max width
    lines.append("docker run -dit")
    lines.append("    -e WORKDIR=...")
    
    if rm:
        lines.append("    --rm")
    
    if x11 and X11_path:
        lines.append(f"    --net=host")
        lines.append(f"    -e DISPLAY=:0")
        lines.append(f"    -v {X11_path}:/tmp/.X11-unix")
        lines.append(f"    -v /home/ykarmon/.Xauthority:/home/ykarmon/.Xauthority:ro")
    
    if usb:
        lines.append("    -v /dev/bus/usb:/dev/bus/usb")
    
    for key, value in environment.items():
        lines.append(f"    -e {key}={value}")
    
    for host_path, container_path in resolved_mounts:
        lines.append(f"    -v {host_path}:{container_path}")
    
    lines.append(f"    --name {container_name}")
    lines.append(f"    {convert_to_docker_format(image_name)}")
    lines.append(f"    {command}")
    
    # Find the maximum width for alignment
    for line in lines:
        if len(line) > max_width:
            max_width = len(line)
    
    # Add padding to align comments
    comment_column = max_width + 4
    
    # Print base command
    print_aligned_comment("# docker run -dit", "# Base Docker run command with detached, interactive, tty", comment_column)
    print_aligned_comment(f"#     -e WORKDIR={container_info.config_directory}", "# Set working directory for relative paths (hardcoded)", comment_column)
    
    # Print flags with comments
    if rm:
        print_aligned_comment("#     --rm", "# Remove container when it exits (from --rm flag)", comment_column)
    
    # Print X11 support with comment
    if x11 and X11_path:
        print_aligned_comment("#     --net=host", "# Enable host networking for X11 (hardcoded)", comment_column)
        print_aligned_comment("#     -e DISPLAY=:0", "# Set display for X11 forwarding (from --x11 flag, DISPLAY=:0 from $DISPLAY env var, means display 0 on localhost)", comment_column)
        print_aligned_comment(f"#     -v {X11_path}:/tmp/.X11-unix", "# Mount X11 socket (from --x11 flag, config.X11_path)", comment_column)
        print_aligned_comment("#     -v /home/ykarmon/.Xauthority:/home/ykarmon/.Xauthority:ro", "# Mount X11 auth file (from --x11 flag)", comment_column)
    
    # Print USB support with comment
    if usb:
        print_aligned_comment("#     -v /dev/bus/usb:/dev/bus/usb", "# Mount USB devices (from --usb flag)", comment_column)
    
    # Print environment variables with comments
    for key, value in environment.items():
        print_aligned_comment(f"#     -e {key}={value}", "# Environment variable (hardcoded)", comment_column)
    
    # Print mounts with individual comments
    for host_path, container_path in resolved_mounts:
        # Determine the source of each mount
        if host_path.startswith("$HOME"):
            comment = "# Mount from config.mounts array (from $HOME)"
        elif host_path.startswith("/home/ykarmon"):
            comment = "# Mount from config.mounts array (from $HOME)"
        elif host_path.startswith("containers/"):
            comment = "# Mount from config.mounts array (relative to config file)"
        elif host_path.startswith("../"):
            comment = "# Mount from config.mounts array (relative to config file)"
        elif host_path.startswith("/"):
            comment = "# Mount from config.mounts array (absolute path)"
        else:
            comment = "# Mount from config.mounts array (relative to config file)"
        
        print_aligned_comment(f"#     -v {host_path}:{container_path}", comment, comment_column)
    
    # Print container name and image with comments
    print_aligned_comment(f"#     --name {container_name}", "# Container name (from config.container.name)", comment_column)
    print_aligned_comment(f"#     {convert_to_docker_format(image_name)}", "# Docker image (from config.image.name:tag)", comment_column)
    print_aligned_comment(f"#     {command}", "# Default command to run (hardcoded)", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    print(docker_command)
