#!/usr/bin/env python3

import os
import shlex
from helper_functions.command_builder import CommandBuilder, CmdPartFlag, CmdPartArg, CmdPartName
from command.help.help import show_exec_help

def exec_cmd(args, container_info):
    """Generate Docker exec command for running container"""
    # Extract arguments
    exec_cmd_args = args.exec_cmd
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_exec_help()
        return
    
    # Generate container name
    container_name = container_info.run_name
    if not container_name:
        print("❌ No container name available")
        return
    
    # Get current user dynamically (same as run.py)
    current_user = os.getenv('USER', os.getenv('USERNAME', 'user'))
    
    # Create command builder
    builder = CommandBuilder("Exec")
    builder.set_base_command(["docker", "exec"])
    
    # Add user flag
    builder.add_part("user", CmdPartFlag(f"--user {current_user}", 
                                       comment="# Execute as current user"))
    
    # Add container name
    builder.add_part("container_name", CmdPartName("run_name", 
                                                  comment="# Container name (from config.container.name)"))
    
    # Add bash command with interactive mode
    if exec_cmd_args:
        # Join command arguments and escape properly
        cmd_string = " ".join(exec_cmd_args)
        bash_cmd = f"bash -i -c \"{cmd_string}\""
        builder.add_part("bash_command", CmdPartFlag(bash_cmd, 
                                                    comment="# Interactive bash with user command"))
    else:
        # Default to interactive shell
        builder.add_part("bash_command", CmdPartFlag("bash -i", 
                                                    comment="# Interactive bash shell"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    if errors:
        print("❌ Errors in command generation:")
        for error in errors:
            print(f"  - {error}")
        return
    
    print(commented_str)
    print(execution_str)
