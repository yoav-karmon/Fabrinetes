#!/usr/bin/env python3

from helper_functions.command_builder import CommandBuilder, CmdPartArg, CmdPartName, CmdPartHardcoded
from command.help.help import show_push_help

def push(args, container_info):
    """Generate Docker push commands for GitHub Container Registry"""
    # Extract arguments
    github_username = args.github_username
    registry = args.registry
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_push_help()
        return
    
    # Validate required parameters
    if not github_username:
        print("error: GitHub username is required")
        return
    
    # Set default registry if not provided
    if not registry:
        registry = "ghcr.io"
    
    # Create local and remote image tags
    local_image = f"{container_info.image_name}:{container_info.image_tag}"
    remote_image = f"{registry}/{github_username}/{container_info.image_name}:{container_info.image_tag}"
    
    # Generate docker tag command
    print("# Docker Tag Command:")
    print("# ==================================================")
    print(f"# Tagging local image for GHCR push")
    print(f"# Local image: {local_image}")
    print(f"# Remote tag: {remote_image}")
    print("# ==================================================")
    print("")
    print("# Executable command:")
    print(f"docker tag {local_image} {remote_image}")
    print("")
    
    # Generate docker push command
    print("# Docker Push Command:")
    print("# ==================================================")
    print(f"# Pushing image to GitHub Container Registry")
    print(f"# Registry: {registry}")
    print(f"# Username: {github_username}")
    print(f"# Image: {remote_image}")
    print("# ==================================================")
    print("")
    print("# Executable command:")
    print(f"docker push {remote_image}")
    print("")
    
    # Show success information
    print("# Success Information:")
    print("# ==================================================")
    print(f"# Image will be available at: {remote_image}")
    print(f"# Pull command: docker pull {remote_image}")
    print(f"# View package at: https://github.com/{github_username}/packages")
    print("# ==================================================")















