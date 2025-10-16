#!/usr/bin/env python3

import os

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")

def build(args, container_info):
    """Generate Docker build command for base image only"""
    
    # Extract arguments from args object
    buildbase = getattr(args, 'buildbase', False)
    help_flag = getattr(args, 'help', False)
    
    # Check for help flag or missing required arguments
    if help_flag:
        from invoke_tasks.help.help import show_build_help
        show_build_help()
        return
    
    # Validate buildbase flag is required
    if not buildbase:
        print("❌ Error: Build command now only works for base images")
        print("Usage: ./fabrinetes --cmd build --config-file <config.toml> --buildbase")
        print("")
        print("The build command is now dedicated to building base images only.")
        print("For main images, use the future 'install' command (not implemented yet).")
        return
    
    # Generate base image build command using dockerfile from dataclass
    image_name = container_info.base_image_docker
    
    # Build the docker build command parts
    cmd_parts = ["docker", "build", "--build-arg", f"USERNAME={os.environ.get('USER', 'user')}", "-t", image_name, "-f", container_info.base_image_dockerfile, f"{container_info.config_directory}/"]
    
    # Add WORKDIR environment variable (always)
    cmd_parts.insert(0, f"WORKDIR={container_info.config_directory}")
    cmd_parts.insert(0, "env")
    
    # Calculate max width for aligned comments
    lines_to_measure = []
    lines_to_measure.append("env WORKDIR=...")
    lines_to_measure.append("docker build --build-arg")
    lines_to_measure.append(f"    USERNAME={os.environ.get('USER', 'user')}")
    lines_to_measure.append(f"    -t {image_name}")
    lines_to_measure.append(f"    -f {container_info.base_image_dockerfile}")
    lines_to_measure.append(f"    {container_info.config_directory}/")
    
    max_width = 0
    for line in lines_to_measure:
        if len(line) > max_width:
            max_width = len(line)
    comment_column = max_width + 4
    
    print("# Docker Build Command (Base Image):")
    print("# " + "=" * 50)
    
    print_aligned_comment(f"# env WORKDIR={container_info.config_directory}", "# Set working directory for relative paths (hardcoded)", comment_column)
    print_aligned_comment("# docker build --build-arg", "# Base Docker build command (hardcoded)", comment_column)
    print_aligned_comment(f"#     USERNAME={os.environ.get('USER', 'user')}", "# Build argument (from $USER env var)", comment_column)
    print_aligned_comment(f"#     -t {image_name}", "# Image name:tag (from config.base_image.name:tag)", comment_column)
    print_aligned_comment(f"#     -f {container_info.base_image_dockerfile}", "# Dockerfile path (from config.base_image.dockerfile)", comment_column)
    print_aligned_comment(f"#     {container_info.config_directory}/", "# Build context (from config file directory)", comment_column)
    
    print("# " + "=" * 50)
    print()
    print("# Executable command:")
    
    # Check if Dockerfile path could be resolved
    if container_info.base_image_dockerfile_resolved is None:
        error_msg = f"Error: Dockerfile not found at {container_info.base_image_dockerfile}"
        print(f"echo '{error_msg}'")
    else:
            print(" ".join(cmd_parts))
