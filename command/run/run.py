#!/usr/bin/env python3

import os
import pathlib
from helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartFlag, CmdPartMounts, CmdPartX11, CmdPartArg, CmdPartName
from helper_functions.image_management import convert_to_docker_format
from command.help.help import show_run_help

def run(args, container_info):
    """Run a Docker container with the specified configuration"""
    # Extract arguments
    rm = args.rm
    verbose = args.verbose
    x11 = args.x11
    usb = args.usb
    ask = args.ask
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_run_help()
        return
    
    # Generate container name
    container_name = container_info.run_name
    if not container_name:
        return
    
    # Create command builder
    builder = CommandBuilder("Run")
    builder.set_base_command(["docker", "run", "-dit"])
    
    # Add WORKDIR environment variable
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory", 
                                          comment="# Set working directory for relative paths"))
    
    # Add user creation environment variables
    current_user = os.getenv('USER', os.getenv('USERNAME', 'user'))
    builder.add_part("container_user", CmdPartEnv("CONTAINER_USER", current_user, 
                                                 comment="# Set container username for entrypoint"))
    builder.add_part("container_uid", CmdPartEnv("CONTAINER_UID", str(os.getuid()), 
                                                comment="# Set container user ID for entrypoint"))
    builder.add_part("container_gid", CmdPartEnv("CONTAINER_GID", str(os.getgid()), 
                                                comment="# Set container group ID for entrypoint"))
    builder.add_part("container_home", CmdPartEnv("CONTAINER_HOME", f"/home/{current_user}", 
                                                 comment="# Set container home directory for entrypoint"))
    
    # Add flags
    if rm:
        builder.add_part("rm", CmdPartFlag("--rm", comment="# Remove container when it exits (from --rm flag)"))
    
    # Add X11 support
    if x11:
        builder.add_part("x11", CmdPartX11(True, comment="# Enable X11 GUI support"))
    
    # Add USB support
    if usb:
        builder.add_part("usb", CmdPartFlag("-v /dev/bus/usb:/dev/bus/usb", comment="# Mount USB devices (from --usb flag)"))
    
    # Add mounts
    if container_info.mounts:
        builder.add_part("mounts", CmdPartMounts(container_info.mounts, 
                                                comment="# Mount from config.mounts array"))
    
    # Add container name
    builder.add_part("container_name", CmdPartArg("--name", "run_name", 
                                                 comment="# Container name (from config.container.name)"))
    
    # Add image name
    builder.add_part("image_name", CmdPartName("image_docker", 
                                              comment="# Docker image (from config.image.name:tag)"))
    
    # Add command
    builder.add_part("command", CmdPartFlag("bash", comment="# Command to keep container running with interactive shell"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    print(execution_str)
