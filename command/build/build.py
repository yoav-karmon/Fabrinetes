#!/usr/bin/env python3

import os
from helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartArg, CmdPartFile, CmdPartName
from command.help.help import show_build_help

def build(args, container_info):
    """Generate Docker build command for image"""
    # Extract arguments
    tarball = args.tarball
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_build_help()
        return
    
    # Handle tarball generation
    if tarball:
        generate_tarball_command(container_info)
        return
    
    # Create command builder
    builder = CommandBuilder("Build (Image)")
    builder.set_base_command(["docker", "build"])
    
    # Add image name argument
    builder.add_part("image_name", CmdPartArg("-t", "image_docker", 
                                             "# Image name:tag (from config.image.name:tag)"))
    
    # Add dockerfile argument
    builder.add_part("dockerfile", CmdPartFile("-f", "image_dockerfile", 
                                              "# Dockerfile path (from config.image.dockerfile)"))
    
    # Add build context
    builder.add_part("context", CmdPartName("working_directory", 
                                           "# Build context (from config file directory)"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    print(execution_str)

def generate_tarball_command(container_info):
    """Generate docker save command to create tarball"""
    # Create command builder
    builder = CommandBuilder("Save (Image)")
    builder.set_base_command(["docker", "save", "-o"])
    
    # Add output path
    builder.add_part("output", CmdPartFile("-o", "image_tarball_resolved", 
                                           comment="# Output tarball path (from config.image.tarball_path)"))
    
    # Add image name
    builder.add_part("image_name", CmdPartName("image_docker", 
                                              comment="# Image name:tag (from config.image.name:tag)"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    print(execution_str)
