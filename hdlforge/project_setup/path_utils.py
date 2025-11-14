#!/usr/bin/env python3
"""
Python path management utilities for HDLForge
"""

import os
import sys
from pathlib import Path


def add_python_paths_from_list(path_list, working_path=None):
    """Add paths to PYTHONPATH from a list, resolving relative paths and environment variables"""
    print("\n[i] Updating PYTHONPATH with the following paths:", flush=True)
    
    # Always add working_path first if provided
    if working_path:
        working_path_abs = os.path.abspath(working_path)
        if working_path_abs not in sys.path:
            sys.path.insert(0, working_path_abs)
            print(f"[OK] Added working_path to PYTHONPATH: {working_path_abs}")
        else:
            print(f"[i] working_path already in PYTHONPATH: {working_path_abs}")
    
    # Process additional paths from the list
    for path in path_list:
        # Resolve relative paths relative to working_path if provided
        if working_path and not os.path.isabs(path):
            resolved = str(Path(working_path) / path)
        else:
            # Resolve env vars
            resolved = os.path.expandvars(path)
        
        print(f"[~] Resolving path: {resolved}")
        # Absolute path
        abs_path = os.path.abspath(resolved)

        # Add if not already in sys.path (check for duplication)
        if abs_path not in sys.path:
            sys.path.insert(0, abs_path)
            print(f"[OK] Added to PYTHONPATH: {abs_path}")
        else:
            print(f"[i] Already in PYTHONPATH: {abs_path}")
    print("", flush=True)

"""
Python path management utilities for HDLForge
"""

import os
import sys
from pathlib import Path


def add_python_paths_from_list(path_list, working_path=None):
    """Add paths to PYTHONPATH from a list, resolving relative paths and environment variables"""
    print("\n[i] Updating PYTHONPATH with the following paths:", flush=True)
    
    # Always add working_path first if provided
    if working_path:
        working_path_abs = os.path.abspath(working_path)
        if working_path_abs not in sys.path:
            sys.path.insert(0, working_path_abs)
            print(f"[OK] Added working_path to PYTHONPATH: {working_path_abs}")
        else:
            print(f"[i] working_path already in PYTHONPATH: {working_path_abs}")
    
    # Process additional paths from the list
    for path in path_list:
        # Resolve relative paths relative to working_path if provided
        if working_path and not os.path.isabs(path):
            resolved = str(Path(working_path) / path)
        else:
            # Resolve env vars
            resolved = os.path.expandvars(path)
        
        print(f"[~] Resolving path: {resolved}")
        # Absolute path
        abs_path = os.path.abspath(resolved)

        # Add if not already in sys.path (check for duplication)
        if abs_path not in sys.path:
            sys.path.insert(0, abs_path)
            print(f"[OK] Added to PYTHONPATH: {abs_path}")
        else:
            print(f"[i] Already in PYTHONPATH: {abs_path}")
    print("", flush=True)

