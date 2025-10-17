#!/usr/bin/env python3

import os

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")

def clean_images(args, container_info):
    """Generate Docker rmi command to remove existing images"""
    
    # Extract arguments from args object
    base_image = getattr(args, 'base_image', False)
    help_flag = getattr(args, 'help', False)
    
    # Check for help flag
    if help_flag:
        from command.help.help import show_clean_images_help
        show_clean_images_help()
        return
    
    # Determine which image to clean based on --base-image flag
    if base_image:
        # Clean base image
        image_name = container_info.base_image_docker
        image_type = "Base Image"
        config_key = "config.base_image"
    else:
        # Clean main image
        image_name = container_info.image_docker
        image_type = "Main Image"
        config_key = "config.image"
    
    # Build the docker rmi command parts
    cmd_parts = ["docker", "rmi", "-f", image_name]
    
    # Calculate max width for aligned comments
    lines_to_measure = []
    lines_to_measure.append("docker rmi -f")
    lines_to_measure.append(f"    {image_name}")
    
    max_width = 0
    for line in lines_to_measure:
        if len(line) > max_width:
            max_width = len(line)
    comment_column = max_width + 4
    
    print(f"# Docker Remove Command ({image_type}):")
    print("# " + "=" * 50)
    
    print_aligned_comment("# docker rmi -f", "# Force remove Docker image", comment_column)
    print_aligned_comment(f"#     {image_name}", f"# Image name:tag (from {config_key}.name:tag)", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    print(" ".join(cmd_parts))
