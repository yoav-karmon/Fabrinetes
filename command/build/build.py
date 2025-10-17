#!/usr/bin/env python3

import os

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")

def build(args, container_info):
    """Generate Docker build command for image"""
    
    # Extract arguments from args object
    tarball = getattr(args, 'tarball', False)
    help_flag = getattr(args, 'help', False)
    
    # Check for help flag
    if help_flag:
        from command.help.help import show_build_help
        show_build_help()
        return
    
    # Handle tarball generation
    if tarball:
        generate_tarball_command(container_info)
        return
    
    # Generate image build command using dockerfile from dataclass
    image_name = container_info.image_docker
    
    # Build the docker build command parts
    cmd_parts = ["docker", "build", "-t", image_name, "-f", container_info.image_dockerfile, f"{container_info.working_directory}/"]
    
    # Add WORKDIR environment variable (always)
    cmd_parts.insert(0, f"WORKDIR={container_info.working_directory}")
    cmd_parts.insert(0, "env")
    
    # Calculate max width for aligned comments
    lines_to_measure = []
    lines_to_measure.append("env WORKDIR=...")
    lines_to_measure.append("docker build")
    lines_to_measure.append(f"    -t {image_name}")
    lines_to_measure.append(f"    -f {container_info.image_dockerfile}")
    lines_to_measure.append(f"    {container_info.working_directory}/")
    
    max_width = 0
    for line in lines_to_measure:
        if len(line) > max_width:
            max_width = len(line)
    comment_column = max_width + 4
    
    print("# Docker Build Command (Image):")
    print("# " + "=" * 50)
    
    print_aligned_comment(f"# env WORKDIR={container_info.working_directory}", "# Set working directory for relative paths", comment_column)
    print_aligned_comment("# docker build", "# Docker build command", comment_column)
    print_aligned_comment(f"#     -t {image_name}", "# Image name:tag (from config.image.name:tag)", comment_column)
    print_aligned_comment(f"#     -f {container_info.image_dockerfile}", "# Dockerfile path (from config.image.dockerfile)", comment_column)
    print_aligned_comment(f"#     {container_info.working_directory}/", "# Build context (from config file directory)", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    
    # Check if Dockerfile path could be resolved
    if container_info.image_dockerfile_resolved is None:
        error_msg = f"Error: Dockerfile not found at {container_info.image_dockerfile}"
        print(f"echo '{error_msg}'")
    else:
            print(" ".join(cmd_parts))

def generate_tarball_command(container_info):
    """Generate docker save command to create tarball"""
    
    # Generate tarball for image
    image_name = container_info.image_docker
    tarball_path = container_info.image_tarball_resolved
    image_type = "Image"
    config_key = "config.image"
    
    # Build the docker save command parts
    cmd_parts = ["docker", "save", "-o", tarball_path, image_name]
    
    # Calculate max width for aligned comments
    lines_to_measure = []
    lines_to_measure.append("docker save")
    lines_to_measure.append(f"    -o {tarball_path}")
    lines_to_measure.append(f"    {image_name}")
    
    max_width = 0
    for line in lines_to_measure:
        if len(line) > max_width:
            max_width = len(line)
    comment_column = max_width + 4
    
    print(f"# Docker Save Command ({image_type}):")
    print("# " + "=" * 50)
    
    print_aligned_comment("# docker save", "# Docker save command", comment_column)
    print_aligned_comment(f"#     -o {tarball_path}", f"# Output tarball path (from {config_key}.tarball_path)", comment_column)
    print_aligned_comment(f"#     {image_name}", f"# Image name:tag (from {config_key}.name:tag)", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    print(" ".join(cmd_parts))
