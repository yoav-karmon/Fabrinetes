#!/usr/bin/env python3
"""
Project file detection module for HDLForge.

This module provides functions to automatically detect *.hdlforge.json or *.hdlforge.toml files
in the current directory and handle various detection scenarios.
"""

from pathlib import Path
from typing import Optional, List
import sys


def detect_project_file(current_dir: Path) -> Optional[Path]:
    """
    Detect a single *.hdlforge.json or *.hdlforge.toml file in the specified directory.
    Prefers JSON files over TOML files if both exist.
    
    Args:
        current_dir: Directory to search for project files
        
    Returns:
        Path to the project file if exactly one is found, None otherwise
    """
    # Look for JSON files first (preferred format)
    hdlforge_json_files = list(current_dir.glob("*.hdlforge.json"))
    hdlforge_toml_files = list(current_dir.glob("*.hdlforge.toml"))
    
    # Combine lists, JSON files first
    hdlforge_files = hdlforge_json_files + hdlforge_toml_files
    
    if len(hdlforge_files) == 1:
        return hdlforge_files[0]
    
    return None


def handle_project_detection_errors(hdlforge_files: List[Path]) -> None:
    """
    Handle errors when project file detection fails.
    
    Prints appropriate error messages and exits based on the number of files found.
    
    Args:
        hdlforge_files: List of *.hdlforge.json or *.hdlforge.toml files found
    """
    if len(hdlforge_files) == 0:
        print("❌ No .hdlforge.json or .hdlforge.toml files found in current directory")
        print("Please create a project file or navigate to a project directory")
        print("Or specify the project file explicitly: --project addr_32bit.hdlforge.json")
        sys.exit(1)
    
    elif len(hdlforge_files) > 1:
        print("❌ Multiple project files found in current directory:")
        for file in hdlforge_files:
            print(f"  {file.name}")
        print("")
        print("Please specify which project file to use: --project addr_32bit.hdlforge.json")
        sys.exit(1)


def get_project_files(current_dir: Path) -> List[Path]:
    """
    Get all *.hdlforge.json and *.hdlforge.toml files in the specified directory.
    JSON files are returned first, then TOML files.
    
    Args:
        current_dir: Directory to search for project files
        
    Returns:
        List of Path objects for all *.hdlforge.json and *.hdlforge.toml files found
    """
    json_files = list(current_dir.glob("*.hdlforge.json"))
    toml_files = list(current_dir.glob("*.hdlforge.toml"))
    return json_files + toml_files

