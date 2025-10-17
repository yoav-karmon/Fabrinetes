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

def resolve_mounts(mounts: List[str], working_directory: pathlib.Path) -> List[Tuple[str, str]]:
    """Return mount paths as-is from config file without any resolution"""
    resolved_mounts = []
    
    for mount in mounts:
        if ':' not in mount:
            print(f"Warning: Invalid mount format '{mount}', skipping")
            continue
            
        host_path, container_path = mount.split(':', 1)
        
        # Keep original values from config file (don't expand $HOME or convert paths)
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

