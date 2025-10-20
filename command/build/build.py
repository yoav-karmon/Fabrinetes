#!/usr/bin/env python3

import os
from command.helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartArg, CmdPartFile, CmdPartName
from command.help.help import show_build_help

def build(args, container_info):
    """Generate Docker build command for image"""
    # Extract arguments
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_build_help()
        return
    
    # Create command builder
    builder = CommandBuilder("Build (Image)")
    builder.set_base_command(["docker", "build"])
    
    # Add image name argument
    builder.add_part("image_name", CmdPartArg("-t", "image_docker", 
                                             "# Image name:tag (from config.image.name:tag)"))
    
    # Add dockerfile argument
    builder.add_part("dockerfile", CmdPartFile("-f", "image_dockerfile_resolved", 
                                              "# Dockerfile path (from config.image.dockerfile)"))
    
    # Add build context
    builder.add_part("context", CmdPartName("working_directory", 
                                           "# Build context (from config file directory)"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    print(execution_str)
