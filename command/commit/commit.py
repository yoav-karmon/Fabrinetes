#!/usr/bin/env python3

import time
import subprocess
from helper_functions.command_builder import CommandBuilder, CmdPartHardcoded, CmdPartName
from command.help.help import show_commit_help

def commit(args, container_info):
    """Generate a Docker commit command to stdout without executing it"""
    # Extract arguments
    tag = args.tag
    message = args.message
    help_flag = args.show_help
    
    # Check for help flag first
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
    
    # Create command builder
    builder = CommandBuilder("Commit")
    builder.set_base_command(["docker", "commit", "-m"])
    
    # Add commit message
    builder.add_part("message", CmdPartHardcoded(f'"{message}"', 
                                                comment="# Commit message (from --message flag or auto-generated)"))
    
    # Add container name
    builder.add_part("container_name", CmdPartName("run_name", 
                                                  comment="# Container name (from config.container.run_name)"))
    
    # Add target image
    builder.add_part("target_image", CmdPartHardcoded(f"{container_info.image_full}:{tag}",
                                                     comment="# Target image name:tag (from config.image.name:tag)"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    
    # Check if container exists and is running
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            # Container not running
            error_msg = f"Container '{container_name}' is not running"
            print(f"echo 'error: {error_msg}'")
        else:
            # Container is running, show the actual command
            print(execution_str)
    except subprocess.CalledProcessError:
        # Docker command failed
        error_msg = f"Could not check container status for '{container_name}'"
        print(f"echo 'error: {error_msg}'")