#!/usr/bin/env python3

import os
import pathlib
from typing import List, Tuple

def setup_x11_support(x11, X11_path, cmd_parts):
    """Helper function to set up X11 support for Docker containers"""
    if x11:
        if X11_path:
            print(f"X11 support enabled at {X11_path}")
            X11_path = os.path.expandvars(X11_path)
            X11_path = pathlib.Path(X11_path)
            if not X11_path.exists():
                print(f"Error: X11 socket {X11_path} does not exist")
                import sys
                sys.exit(1)
        else:
            # Default X11 socket path
            X11_path = pathlib.Path("/tmp/.X11-unix")
            print(f"X11 support enabled at {X11_path}")

        cmd_parts.append("--net=host")
        cmd_parts.append(f"-e DISPLAY={os.environ['DISPLAY']}")
        cmd_parts.append(f"-v {X11_path}:/tmp/.X11-unix")
        cmd_parts.append(f"-v {os.environ['HOME']}/.Xauthority:/home/{os.getenv('USER', 'user')}/.Xauthority:ro")

    return cmd_parts

def check_invocation_method():
    """Check if tasks.py is being called directly and exit with error if so"""
    import sys
    import inspect
    
    # Check if we're being called directly (not from fabrinetes script)
    frame = inspect.currentframe()
    try:
        # Go up the call stack to see how we were called
        caller_frame = frame.f_back
        if caller_frame:
            caller_filename = caller_frame.f_code.co_filename
            # If called directly, the filename will be tasks.py
            if caller_filename.endswith('tasks.py') and 'fabrinetes' not in caller_filename:
                print("Error: tasks.py should not be called directly")
                print("Please use the fabrinetes script instead:")
                print("  ./fabrinetes <command>")
                sys.exit(1)
    finally:
        del frame

def resolve_mounts(mounts: List[str], relative_path: pathlib.Path) -> List[Tuple[str, str]]:
    """Resolve mount paths, expanding environment variables and converting to absolute paths"""
    resolved_mounts = []
    
    for mount in mounts:
        if ':' not in mount:
            print(f"Warning: Invalid mount format '{mount}', skipping")
            continue
            
        host_path, container_path = mount.split(':', 1)
        
        # Expand environment variables in host path
        host_path = os.path.expandvars(host_path)
        
        # Convert to absolute path if relative
        if not os.path.isabs(host_path):
            host_path = str(relative_path / host_path)
        
        resolved_mounts.append((host_path, container_path))
    
    return resolved_mounts

def printlocals(locals_dict, verbose=False):
    """Print local variables for debugging"""
    print("===============================")
    print("Local Variables:")
    for key, value in locals_dict.items():
        if verbose:
            print(f"{key:10} = {value}")
        else:
            if isinstance(value, (str, int, float, bool)) or value is None:
                print(f"{key:10} = {value}")
            else:
                print(f"{key:10} = <{type(value).__name__}>")
    
    print("===============================")
