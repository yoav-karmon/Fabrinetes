#!/usr/bin/env python3
"""
File validation module for HDLForge.

This module provides functions to validate that all source files referenced
in project configurations actually exist on the filesystem.
"""

from pathlib import Path
from typing import List, Dict, Tuple
import sys


def validate_source_files(sources_dict_list: List[Dict], tool_name: str = "vivado") -> Tuple[bool, List[str]]:
    """
    Validate that all source files in the sources_dict_list actually exist.
    
    Args:
        sources_dict_list: List of file dictionaries from get_file_list_for_tool()
        tool_name: Name of the tool (for error messages)
        
    Returns:
        Tuple of (is_valid: bool, missing_files: List[str])
        - is_valid: True if all files exist, False otherwise
        - missing_files: List of file paths that don't exist
    """
    missing_files = []
    
    for file_dict in sources_dict_list:
        file_path_str = file_dict.get("file")
        if file_path_str is None:
            continue
            
        file_path = Path(file_path_str)
        
        # Check if file exists
        if not file_path.exists():
            missing_files.append(str(file_path))
            continue
            
        # Check if it's actually a file (not a directory)
        if not file_path.is_file():
            missing_files.append(f"{file_path} (exists but is not a file)")
    
    return (len(missing_files) == 0, missing_files)


def validate_and_exit_on_missing(sources_dict_list: List[Dict], tool_name: str = "vivado") -> None:
    """
    Validate source files and exit with error if any are missing.
    
    This function checks all files in sources_dict_list and if any are missing,
    it prints a detailed error message listing all missing files and exits
    with error code 1.
    
    Args:
        sources_dict_list: List of file dictionaries from get_file_list_for_tool()
        tool_name: Name of the tool (for error messages)
        
    Exits:
        If any files are missing, prints error message and exits with code 1
    """
    is_valid, missing_files = validate_source_files(sources_dict_list, tool_name)
    
    if not is_valid:
        print("=" * 80)
        print(f"❌ ERROR: Missing source files for {tool_name} project")
        print("=" * 80)
        print(f"\nFound {len(missing_files)} missing file(s):\n")
        
        for idx, missing_file in enumerate(missing_files, 1):
            print(f"  [{idx}] {missing_file}")
        
        print("\n" + "=" * 80)
        print("Please check your project configuration file and ensure all source")
        print("files exist and paths are correct.")
        print("=" * 80)
        sys.exit(1)
    
    # If we get here, all files exist
    print(f"✅ All {len(sources_dict_list)} source file(s) validated successfully")

