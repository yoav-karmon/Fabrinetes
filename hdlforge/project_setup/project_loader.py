#!/usr/bin/env python
"""
Project Loader - Single source of truth for HDLForge project data

This module provides a ProjectLoader class that loads and provides access
to project configuration from JSON or TOML files.
"""

import os
import json
import tomllib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from project_detector import detect_project_file, handle_project_detection_errors, get_project_files
from json_file_handler import JSONFileHandler


class ProjectLoader:
    """
    Loads and provides access to HDLForge project configuration.
    
    This class serves as a single source of truth for all project information,
    ensuring consistent access to project settings, source files, and tool configurations.
    """
    
    def __init__(self, project_file: Optional[Union[str, Path]] = None):
        """
        Initialize the ProjectLoader.
        
        Args:
            project_file: Optional project file path. If None, auto-detects from current directory.
        """
        # Load basic project data
        self._project_file_path = self._get_project_file_path(project_file)
        self._project_data = self._load_project_data()
        self._working_path = self._resolve_working_path()
        self._repo_top = Path(os.environ.get("REPO_TOP", ""))
        
        # Extract settings
        self.settings = self._project_data.get("settings", {})
        self.vivado_settings = self._project_data.get("vivado_settings", {})
        self.verilator_settings = self._project_data.get("verilator_settings", {})
        self.sources = self._project_data.get("sources", {})
        
        # Project settings
        self.project_name = self.settings.get("project_name", "").strip()
        self.project_path = self.settings.get("project_path", "")
        
        # Vivado settings - compute all values
        vivado_build_dir_str = self.vivado_settings.get("build_dir", "_vivado")
        self.vivado_build_dir = self._working_path / vivado_build_dir_str
        self.vivado_project_name = self.vivado_settings.get("project_name", "").strip()
        self.vivado_top_module = self.vivado_settings.get("top_module", "")
        self.vivado_part = self.vivado_settings.get("part", "")
        self.vivado_runs_flow = self.vivado_settings.get("runs_flow", {})
        self.vivado_lint_ignore_error_codes = self.vivado_settings.get("lint_ignore_error_codes", [])
        self.vivado_lint_ignore_warning_codes = self.vivado_settings.get("lint_ignore_warning_codes", [])
        
        # Vivado paths
        project_tcl = self.vivado_settings.get("project_tcl", "")
        if project_tcl:
            self.vivado_project_tcl = self._working_path / project_tcl
        else:
            self.vivado_project_tcl = self._working_path / f"{self.vivado_project_name}.tcl"
        
        self.vivado_project_xpr_path = self.vivado_build_dir / self.vivado_project_name / f"{self.vivado_project_name}.xpr"
        self.vivado_project_xpr_relative = f"{self.vivado_project_name}/{self.vivado_project_name}.xpr"
        self.vivado_output_tcl_path = self.vivado_build_dir / f"{self.vivado_project_name}.tcl"
        
        # Verilator settings
        verilator_build_dir_str = self.verilator_settings.get("build_dir", "_verilator")
        self.verilator_build_dir = self._working_path / verilator_build_dir_str
        self.verilator_sim_targets = self.verilator_settings.get("sim_targets", [])
        self.verilator_includes_paths = self.verilator_settings.get("includes_paths", [])
    
    def _get_project_file_path(self, project_file: Optional[Union[str, Path]]) -> Path:
        """
        Get the project file path, either from argument or by auto-detection.
        
        Args:
            project_file: Optional project file name or None for auto-detection
            
        Returns:
            Path to the project file
        """
        ROOT_FOLDER = Path(os.environ["ROOT_FOLDER"])
        
        if project_file is None:
            # Auto-detection mode
            detected_file = detect_project_file(ROOT_FOLDER)
            
            if detected_file is None:
                # Detection failed - get all files and show error
                hdlforge_files = get_project_files(ROOT_FOLDER)
                handle_project_detection_errors(hdlforge_files)
            
            print(f"ℹ️  Auto-detected project file: {detected_file.name}")
            return detected_file
        else:
            # Explicit project file specified
            if isinstance(project_file, str):
                project_file_path = ROOT_FOLDER / project_file
            else:
                project_file_path = project_file
            
            if not project_file_path.exists():
                print(f"❌ Project file not found: {project_file_path}")
                hdlforge_files = get_project_files(ROOT_FOLDER)
                if hdlforge_files:
                    print("Available project files in current directory:")
                    for file in hdlforge_files:
                        print(f"  {file.name}")
                print("Or specify with: --project addr_32bit.hdlforge.json (or .toml)")
                exit(1)
            
            print(f"ℹ️  Using project file: {project_file_path.name}")
            return project_file_path
    
    def _load_project_data(self) -> dict:
        """
        Load project data from JSON or TOML file.
        
        Returns:
            Dictionary containing project configuration
        """
        if not self._project_file_path.exists():
            exit(f"Project file not found: {self._project_file_path}")
        
        # Detect file format by extension
        file_ext = self._project_file_path.suffix.lower()
        
        if file_ext == '.json':
            project_data = JSONFileHandler.read_json_file(self._project_file_path)
        elif file_ext == '.toml':
            with open(self._project_file_path, "rb") as f:
                project_data = tomllib.load(f)
        else:
            exit(f"Unsupported project file format: {file_ext}. Supported formats: .json, .toml")
        
        return project_data
    
    def _resolve_working_path(self) -> Path:
        """
        Resolve the working path from project settings.
        
        Returns:
            Resolved absolute path to project working directory
        """
        project_path_str = self._project_data["settings"]["project_path"]
        project_path_expanded = os.path.expandvars(project_path_str)
        return Path(project_path_expanded).resolve()
    
    # Properties for backward compatibility (return stored values)
    @property
    def project_file_path(self) -> Path:
        """Path to the project configuration file."""
        return self._project_file_path
    
    @property
    def project_data(self) -> dict:
        """Raw project data dictionary."""
        return self._project_data
    
    @property
    def working_path(self) -> Path:
        """Absolute path to the project working directory."""
        return self._working_path
    
    @property
    def repo_top(self) -> Path:
        """REPO_TOP environment variable path."""
        return self._repo_top
    
    # Methods for getting file lists
    def get_file_list_for_tool(self, tool_name: str, verbose: bool = False) -> List[dict]:
        """
        Get list of source files for a specific tool (vivado or verilator).
        
        Args:
            tool_name: Tool name ('vivado' or 'verilator')
            verbose: If True, print file information
            
        Returns:
            List of file dictionaries with resolved paths
        """
        all_source_files = self.sources.get("files", []).copy()
        tool_source_files = []
        file_order = 1
        
        for file_dict in all_source_files:
            # Support both old format (direct keys) and new format (hdlforge_properties)
            hdlforge_props = file_dict.get("hdlforge_properties", {})
            if hdlforge_props:
                # New format: properties in hdlforge_properties
                tool_enabled = hdlforge_props.get(tool_name, False)
                relative_to_project_path = hdlforge_props.get("relative_to_project_path", False)
            else:
                # Old format: properties directly in file_dict
                tool_enabled = file_dict.get(tool_name, False)
                relative_to_project_path = file_dict.get("relative_to_project_path", False)
            
            if tool_enabled:
                
                # Handle both old format (file as list) and new format (file as string)
                file_list = file_dict.get("file", [])
                if not isinstance(file_list, list):
                    file_list = [file_list]
                
                for file_path_str in file_list:
                    if relative_to_project_path:
                        file_path = self._working_path / Path(file_path_str)
                    else:
                        file_path = Path(os.path.expandvars(file_path_str))
                    
                    if verbose:
                        print(f"[i] source file #{file_order}: {str(file_path)} for tool: {tool_name}")
                    
                    # Create a copy of the file dict with resolved path
                    _file_dict = file_dict.copy()
                    _file_dict["file"] = str(file_path.resolve())
                    tool_source_files.append(_file_dict)
                    file_order += 1
        
        return tool_source_files
    
    def get_vivado_sources(self, verbose: bool = False) -> List[dict]:
        """Get source files for Vivado."""
        return self.get_file_list_for_tool("vivado", verbose)
    
    def get_verilator_sources(self, verbose: bool = False) -> List[dict]:
        """Get source files for Verilator."""
        return self.get_file_list_for_tool("verilator", verbose)
    
    def get_sim_target(self, target_name: str) -> Optional[dict]:
        """
        Get a specific Verilator simulation target by name.
        
        Args:
            target_name: Name of the simulation target
            
        Returns:
            Target dictionary or None if not found
        """
        for target in self.verilator_sim_targets:
            if target.get("name") == target_name:
                return target
        return None
    
    def verify_repo_path(self) -> None:
        """
        Verify that the project path is under REPO_TOP.
        
        Exits with error if validation fails.
        """
        if not str(self._working_path.resolve()).startswith(str(self._repo_top.resolve())):
            print(f"[!x!]  PROJECT_FILES path '{self._working_path}' is not under REPO_TOP '{self._repo_top}'")
            print(f"Please run: update_repo_path")
            exit(1)
    
    def save_project_data(self) -> None:
        """
        Save the current project data back to the JSON file.
        
        This updates the JSON file with any changes made to _project_data.
        """
        if not self._project_file_path.exists():
            print(f"❌ Project file not found: {self._project_file_path}")
            exit(1)
        
        file_ext = self._project_file_path.suffix.lower()
        
        if file_ext == '.json':
            JSONFileHandler.write_json_file(self._project_file_path, self._project_data, merge_records=True)
            print(f"✅ Updated project file: {self._project_file_path.name}")
        else:
            print(f"❌ Saving is only supported for JSON files. Current file: {file_ext}")
            exit(1)
    
    def update_vivado_runs_flow(self, runs_flow: Dict[str, Any]) -> None:
        """
        Update the vivado_settings.runs_flow in the project data.
        
        Args:
            runs_flow: Dictionary containing the updated runs_flow configuration
        """
        if "vivado_settings" not in self._project_data:
            self._project_data["vivado_settings"] = {}
        self._project_data["vivado_settings"]["runs_flow"] = runs_flow
        # Also update the cached value
        self.vivado_runs_flow = runs_flow

