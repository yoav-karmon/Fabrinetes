#!/usr/bin/env python3

import os
import pathlib
from typing import List, Tuple

def setup_x11_support(x11_enabled: bool, container_info) -> List[str]:
    """Helper function to set up X11 support for Docker containers"""
    x11_args = []
    
    if x11_enabled:
        # Get X11 path from dataclass
        x11_path = container_info.x11_path
        
        if x11_path:
            print(f"X11 support enabled at {x11_path}")
            # Expand environment variables
            expanded_x11_path = os.path.expandvars(x11_path)
            x11_path_obj = pathlib.Path(expanded_x11_path)
            
            if not x11_path_obj.exists():
                print(f"Error: X11 socket {x11_path} does not exist")
                import sys
                sys.exit(1)
        else:
            # Default X11 socket path
            x11_path_obj = pathlib.Path("/tmp/.X11-unix")
            print(f"X11 support enabled at {x11_path_obj}")

        # Add X11-related arguments
        x11_args.append("--net=host")
        x11_args.append(f"-e DISPLAY={os.environ['DISPLAY']}")
        x11_args.append(f"-v {x11_path_obj}:/tmp/.X11-unix")
        x11_args.append(f"-v {os.environ['HOME']}/.Xauthority:/home/{os.getenv('USER', 'user')}/.Xauthority:ro")

    return x11_args

def resolve_mounts(mounts: List[str], working_directory: pathlib.Path) -> List[Tuple[str, str, str, str]]:
    """
    Resolve mount paths from config file, expanding $HOME and converting relative paths to absolute.
    
    Returns:
        List of tuples: (original_host_path, original_container_path, resolved_host_path, resolved_container_path)
    """
    resolved_mounts = []
    
    for mount in mounts:
        if ':' not in mount:
            print(f"Warning: Invalid mount format '{mount}', skipping")
            continue
            
        original_host_path, original_container_path = mount.split(':', 1)
        
        # Expand $HOME environment variable for resolved paths
        resolved_host_path = os.path.expandvars(original_host_path)
        resolved_container_path = os.path.expandvars(original_container_path)
        
        # Convert relative paths to absolute paths for resolved paths
        if not os.path.isabs(resolved_host_path):
            # If host path is relative, make it relative to the working directory
            resolved_host_path = str(working_directory / resolved_host_path)
        
        resolved_mounts.append((original_host_path, original_container_path, resolved_host_path, resolved_container_path))
    
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

