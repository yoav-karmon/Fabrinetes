#!/usr/bin/env python3
"""
Restore Docker images from tar.gz files
"""

import os
import pathlib
import subprocess
from invoke import task
from command.help.help import show_restore_help
from helper_functions.config.name_generator import get_container_info

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")

def restore(args, container_info):
    """Generate a Docker load command to restore from tar.gz without executing it"""
    
    # Extract arguments from args object
    base_image = getattr(args, 'base_image', False)
    image = getattr(args, 'image', False)
    help_flag = getattr(args, 'help', False)
    
    if help_flag:
        show_restore_help()
        return
    
    # Validate arguments
    if not base_image and not image:
        print("❌ Error: Restore command requires either --restore-base-image or --restore-image flag")
        print("Usage: ./fabrinetes --cmd restore --config-file <config.toml> [--base-image|--image]")
        print("")
        print("Options:")
        print("  --base-image    Restore base image from tarball")
        print("  --image         Restore main image from tarball")
        return
    
    if base_image and image:
        print("❌ Error: Cannot restore both base image and main image at the same time")
        print("Please specify either --base-image or --image")
        return
    
    # Determine which tar.gz file to restore from using ContainerInfo paths
    if base_image:
        tar_path = container_info.base_image_tarball_resolved
        image_name = container_info.base_image_docker
        restore_type = "base-image"
    elif image:
        tar_path = container_info.image_tarball_resolved
        image_name = container_info.image_docker
        restore_type = "image"
    else:
        print("Error: Must specify either --base-image or --image flag")
        return
    
    # Build docker load command parts
    cmd_parts = ["docker", "load", "-i", tar_path]
    
    # Add WORKDIR environment variable (always)
    cmd_parts.insert(0, f"WORKDIR={container_info.working_directory}")
    cmd_parts.insert(0, "env")
    
    # Calculate max width for aligned comments
    lines_to_measure = []
    lines_to_measure.append("env WORKDIR=...")
    lines_to_measure.append("docker load -i")
    lines_to_measure.append(f"    {tar_path}")
    
    max_width = 0
    for line in lines_to_measure:
        if len(line) > max_width:
            max_width = len(line)
    comment_column = max_width + 4
    
    print("# Docker Restore Command:")
    print("# " + "=" * 50)
    
    print_aligned_comment(f"# env WORKDIR={container_info.working_directory}", "# Set working directory for relative paths (hardcoded)", comment_column)
    print_aligned_comment("# docker load -i", "# Base Docker load command (hardcoded)", comment_column)
    print_aligned_comment(f"#     {tar_path}", f"# Tarball path (from {'--base-image' if base_image else '--image'} flag, {'config.base_image.tarball' if base_image else 'config.image.tarball'})", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    
    # Check if tar.gz file exists using resolve function, try working directory if not found
    tarball_found = False
    original_tar_path = tar_path  # Keep original path for display
    resolved_tar_path = container_info.resolve(tar_path)
    if resolved_tar_path is None:
        # Try looking for the tarball in the working directory
        tarball_name = container_info.image_tarball if image else container_info.base_image_tarball
        current_dir_path = os.path.join(container_info.working_directory, tarball_name)
        current_dir_resolved = container_info.resolve(current_dir_path)
        if current_dir_resolved is not None:
            tar_path = current_dir_resolved
            tarball_found = True
        else:
            # Generate echo command when tarball not found
            error_msg = f"Error: Tarball not found at {original_tar_path}"
            print(f"echo '{error_msg}'")
            return
    
    if tarball_found:
        # Update command with found tarball path
        cmd_parts = ["env", f"WORKDIR={container_info.working_directory}", "docker", "load", "-i", tar_path]
    
    print(" ".join(cmd_parts))