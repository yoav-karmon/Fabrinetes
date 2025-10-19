#!/usr/bin/env python3
"""
Restore Docker images from tar.gz files
"""

import os
import pathlib
from helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartFile, CmdPartHardcoded
from command.help.help import show_restore_help

def restore(args, container_info):
    """Generate a Docker load command to restore from tar.gz without executing it"""
    # Extract arguments
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_restore_help()
        return
    
    # Create command builder
    builder = CommandBuilder("Restore")
    builder.set_base_command(["env", "docker", "load", "-i"])
    
    # Add WORKDIR environment variable
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory", 
                                          comment="# Set working directory for relative paths"))
    
    # Add tarball path
    builder.add_part("tarball", CmdPartFile("", "image_tarball_resolved", 
                                           comment="# Tarball path (from config.image.tarball_path)"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    print(execution_str)