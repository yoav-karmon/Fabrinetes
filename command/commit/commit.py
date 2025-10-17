#!/usr/bin/env python3

import time
import subprocess
from invoke import task
from helper_functions.name_generator import get_container_info

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")

def commit(args, container_info):
    """Generate a Docker commit command to stdout without executing it"""
    from command.help.help import show_commit_help
    
    # Extract arguments from args object
    tag = getattr(args, 'tag', None)
    message = getattr(args, 'message', None)
    help_flag = getattr(args, 'help', False)
    
    # Check for help flag
    if help_flag:
        show_commit_help()
        return
    
    # Use container name from config
    container_name = container_info.run_name
    
    # Generate tag if not provided
    if not tag:
        tag = container_info.image_tag
    
    # Generate commit message if not provided
    if not message:
        message = f"Committed {container_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Build docker commit command parts
    cmd_parts = ["docker", "commit", "-m", f'"{message}"', container_name, f"{container_info.image_full}:{tag}"]
    
    # Calculate max width for aligned comments
    lines_to_measure = []
    lines_to_measure.append("docker commit -m")
    lines_to_measure.append(f'    "{message}"')
    lines_to_measure.append(f"    {container_name}")
    lines_to_measure.append(f"    {container_info.image_full}:{tag}")
    
    max_width = 0
    for line in lines_to_measure:
        if len(line) > max_width:
            max_width = len(line)
    comment_column = max_width + 4
    
    print("# Docker Commit Command:")
    print("# " + "=" * 50)
    
    print_aligned_comment("# docker commit -m", "# Base Docker commit command (hardcoded)", comment_column)
    print_aligned_comment(f'#     "{message}"', "# Commit message (from --message flag or auto-generated)", comment_column)
    print_aligned_comment(f"#     {container_name}", "# Container name (from config.container.run_name)", comment_column)
    print_aligned_comment(f"#     {container_info.image_full}:{tag}", "# Target image name:tag (from config.image.name:tag)", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    
    # Check if container exists and is running
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            # Container not running
            error_msg = f"Error: Container '{container_name}' is not running"
            print(f"echo '{error_msg}'")
        else:
            # Container is running, show the actual command
            print(" ".join(cmd_parts))
    except subprocess.CalledProcessError:
        # Docker command failed
        error_msg = f"Error: Could not check container status for '{container_name}'"
        print(f"echo '{error_msg}'")