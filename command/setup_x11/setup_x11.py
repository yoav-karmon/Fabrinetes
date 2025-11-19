#!/usr/bin/env python3

import os
import time
import shlex
from command.help.help import show_setup_x11_help

def setup_x11(args, container_info):
    """Generate Docker cp commands to copy .Xauthority and create DISPLAY setup file"""
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_setup_x11_help()
        return
    
    # Generate container name
    container_name = container_info.run_name
    if not container_name:
        print("❌ No container name available")
        return
    
    # Get current user and home directory
    current_user = os.getenv('USER', os.getenv('USERNAME', 'user'))
    home_dir = os.path.expanduser('~')
    xauthority_path = os.path.join(home_dir, '.Xauthority')
    display = os.environ.get('DISPLAY', ':0')
    
    # Container paths
    container_home = f"/home/{current_user}"
    container_xauthority = os.path.join(container_home, '.Xauthority')
    container_display_file = os.path.join(container_home, '.display_env')
    
    # Create DISPLAY environment file content
    display_file_content = f"""# X11 Display environment setup
# This file should be sourced in your shell to set the DISPLAY variable
# Usage: source ~/.display_env

export DISPLAY={display}
"""
    
    # Create temporary file with DISPLAY content in /tmp (persists until manually deleted)
    # Using /tmp instead of tempfile so it persists for the docker cp command
    tmp_display_file = f"/tmp/fabrinetes_display_env_{os.getpid()}_{int(time.time())}.display_env"
    tmp_file_created = False
    
    try:
        with open(tmp_display_file, 'w') as tmp_file:
            tmp_file.write(display_file_content)
        tmp_file_created = True
        
        # Print commented version
        print("# Setup X11 for container")
        print(f"# Container: {container_name}")
        print(f"# User: {current_user}")
        print("")
        
        # Copy .Xauthority from host to container
        if os.path.exists(xauthority_path):
            xauthority_cmd = f"docker cp {shlex.quote(xauthority_path)} {container_name}:{shlex.quote(container_xauthority)}"
            print(f"# Copy .Xauthority from host to container")
            print(xauthority_cmd)
        else:
            print(f"# Warning: .Xauthority not found at {xauthority_path}")
            print("# Skipping .Xauthority copy")
        
        print("")
        
        # Copy DISPLAY setup file to container
        display_cmd = f"docker cp {shlex.quote(tmp_display_file)} {container_name}:{shlex.quote(container_display_file)}"
        print(f"# Copy DISPLAY environment setup file to container")
        print(f"# Usage in container: source ~/.display_env")
        print(display_cmd)
        
        # Clean up temporary file after a delay (give time for docker cp to execute)
        # Note: This cleanup happens in the shell after docker cp, so we add it as a command
        print(f"# Clean up temporary file")
        print(f"rm -f {shlex.quote(tmp_display_file)}")
        
    except Exception as e:
        print(f"# Error creating DISPLAY setup file: {e}")
        # Clean up on error
        if tmp_file_created and os.path.exists(tmp_display_file):
            try:
                os.unlink(tmp_display_file)
            except:
                pass

