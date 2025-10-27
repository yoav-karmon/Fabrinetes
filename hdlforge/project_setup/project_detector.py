#!/usr/bin/env python3
"""
Project file detection module for HDLForge.

This module provides functions to automatically detect *.hdlforge.toml files
in the current directory and handle various detection scenarios.
"""

from pathlib import Path
from typing import Optional, List
import sys


def detect_project_file(current_dir: Path) -> Optional[Path]:
    """
    Detect a single *.hdlforge.toml file in the specified directory.
    
    Args:
        current_dir: Directory to search for project files
        
    Returns:
        Path to the project file if exactly one is found, None otherwise
    """
    hdlforge_files = list(current_dir.glob("*.hdlforge.toml"))
    
    if len(hdlforge_files) == 1:
        return hdlforge_files[0]
    
    return None


def handle_project_detection_errors(hdlforge_files: List[Path]) -> None:
    """
    Handle errors when project file detection fails.
    
    Prints appropriate error messages and exits based on the number of files found.
    
    Args:
        hdlforge_files: List of *.hdlforge.toml files found
    """
    if len(hdlforge_files) == 0:
        print("❌ No .hdlforge.toml files found in current directory")
        print("Please create a project file or navigate to a project directory")
        print("Or specify the project file explicitly: --project addr_32bit.hdlforge.toml")
        sys.exit(1)
    
    elif len(hdlforge_files) > 1:
        print("❌ Multiple project files found in current directory:")
        for file in hdlforge_files:
            print(f"  {file.name}")
        print("")
        print("Please specify which project file to use: --project addr_32bit.hdlforge.toml")
        sys.exit(1)


def get_project_files(current_dir: Path) -> List[Path]:
    """
    Get all *.hdlforge.toml files in the specified directory.
    
    Args:
        current_dir: Directory to search for project files
        
    Returns:
        List of Path objects for all *.hdlforge.toml files found
    """
    return list(current_dir.glob("*.hdlforge.toml"))

