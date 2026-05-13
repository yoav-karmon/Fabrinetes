#!/usr/bin/env python
"""
Project File - Single source of truth for HDLForge project data

This module provides a ProjectFile class that loads and provides access
to project configuration from JSON or TOML files.
"""

import os
import json
import tomllib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from project_detector import detect_project_file, handle_project_detection_errors, get_project_files
from json_file_handler import JSONFileHandler


class ProjectFile:
    """
    Loads and provides access to HDLForge project configuration.
    
    This class serves as a single source of truth for all project information,
    ensuring consistent access to project settings, source files, and tool configurations.
    """
    
    def __init__(self, project_file: Optional[Union[str, Path]] = None):
        """
        Initialize the ProjectFile.
        
        Args:
            project_file: Optional project file path. If None, auto-detects from current directory.
        """
        # Load basic project data
        self._project_file_path = self._get_project_file_path(project_file)
        self._project_data = self._load_project_data()
        self._repo_top = Path(os.environ.get("REPO_TOP", ""))

        # Extract settings
        self.settings = self._project_data.get("settings", {})
        if "project_path" in self.settings:
            print(
                "[!x!] settings.project_path is no longer supported.\n"
                "[i] The working root is always the directory containing this project file.\n"
                "[i] Remove project_path from your *.hdlforge.json / *.hdlforge.toml and use paths relative to that directory."
            )
            exit(1)

        # Working directory: directory of the project file (single source of truth)
        self._working_path = self._project_file_path.parent.resolve()
        # Tool configurations - each tool has its own section
        vivado_section = self._project_data.get("vivado", {})
        verilator_section = self._project_data.get("verilator", {})
        
        self.vivado_config = vivado_section.get("config", {})
        self.vivado_external_config = vivado_section.get("external_config", {})
        self.verilator_config = verilator_section.get("config", {})
        self.verilator_external_config = verilator_section.get("external_config", {})
        # Sources are now under verilator.config.sources (flat array format)
        self.sources = self.verilator_config.get("sources", [])
        
        # Project settings
        self.project_name = self.settings.get("project_name", "").strip()
        # Exposed for callers that expect a project root string; equals working_path.
        self.project_path = str(self._working_path)

        # Vivado config - project identity must be explicit when Vivado is used
        vivado_build_dir_str = self.vivado_config.get("build_dir", "_vivado")
        self.vivado_build_dir = self._working_path / vivado_build_dir_str
        self.vivado_project_name = self.vivado_config.get("project_name", "").strip()
        # Note: part, top_module, set_var, runs_flow are now only in TCL file, not JSON
        self.vivado_lint_ignore_error_codes = self.vivado_config.get("lint_ignore_error_codes", [])
        self.vivado_lint_ignore_warning_codes = self.vivado_config.get("lint_ignore_warning_codes", [])
        
        # Vivado paths - get from external_config.filename
        project_tcl_filename = self.vivado_external_config.get("filename", "")
        self.vivado_project_tcl_edit_json = self.vivado_external_config.get("project_tcl_edit_json", "")
        if project_tcl_filename:
            self.vivado_project_tcl = self._working_path / project_tcl_filename
        elif self.vivado_project_name:
            self.vivado_project_tcl = self._working_path / f"{self.vivado_project_name}.tcl"
        else:
            self.vivado_project_tcl = None
        
        if self.vivado_project_name:
            self.vivado_project_xpr_path = self.vivado_build_dir / self.vivado_project_name / f"{self.vivado_project_name}.xpr"
            self.vivado_project_xpr_relative = f"{self.vivado_project_name}/{self.vivado_project_name}.xpr"
            self.vivado_output_tcl_path = self.vivado_build_dir / f"{self.vivado_project_name}.tcl"
        else:
            self.vivado_project_xpr_path = None
            self.vivado_project_xpr_relative = None
            self.vivado_output_tcl_path = None
        
        # Verilator config
        verilator_build_dir_str = self.verilator_config.get("build_dir", "_verilator")
        self.verilator_build_dir = self._working_path / verilator_build_dir_str
        self.verilator_sim_targets = self.verilator_config.get("sim_targets", [])
        self.verilator_includes_paths = self.verilator_config.get("includes_paths", [])
    
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
                p = Path(project_file)
                if p.is_absolute():
                    project_file_path = p
                else:
                    original_cwd = Path(
                        os.environ.get("HDLFORGE_ORIG_DIR", str(ROOT_FOLDER))
                    )
                    cand_root = (ROOT_FOLDER / project_file).resolve()
                    cand_orig = (original_cwd / project_file).resolve()
                    if cand_root.exists():
                        project_file_path = cand_root
                    elif cand_orig.exists():
                        project_file_path = cand_orig
                    else:
                        project_file_path = cand_root
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
            return project_file_path.resolve()
    
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
        Get list of source files for a specific tool.
        Sources are now a flat array in verilator.config.sources.
        Paths are resolved relative to the JSON file location (not project path).
        
        Args:
            tool_name: Tool name ('vivado' or 'verilator') - currently only 'verilator' is supported
            verbose: If True, print file information
            
        Returns:
            List of file dictionaries with resolved paths
        """
        # Sources are now a flat array in verilator_settings.sources
        # Support both old format (sources.files array) and new format (sources array)
        if isinstance(self.sources, dict) and "files" in self.sources:
            # Old format: sources.files array
            source_list = self.sources.get("files", [])
            # Extract file paths from old format
            all_file_paths = []
            for file_entry in source_list:
                if isinstance(file_entry, dict):
                    file_path = file_entry.get("file", "")
                    if isinstance(file_path, list):
                        all_file_paths.extend(file_path)
                    else:
                        all_file_paths.append(file_path)
                else:
                    all_file_paths.append(file_entry)
        elif isinstance(self.sources, list):
            # New format: flat array of file paths
            all_file_paths = self.sources
        else:
            all_file_paths = []
        
        tool_source_files = []
        file_order = 1
        
        # JSON file directory - paths are relative to this
        json_file_dir = self._project_file_path.parent
        
        for file_path_str in all_file_paths:
            # Resolve environment variables first
            expanded_path = os.path.expandvars(file_path_str)
            
            # Resolve path relative to JSON file location
            file_path = Path(expanded_path)
            if not file_path.is_absolute():
                # Relative path - resolve relative to JSON file directory
                file_path = (json_file_dir / file_path).resolve()
            else:
                # Absolute path - just resolve it
                file_path = file_path.resolve()
            
            if verbose:
                print(f"[i] source file #{file_order}: {str(file_path)} for tool: {tool_name}")
            
            # Create file dict with resolved path
            file_dict = {
                "file": str(file_path)
            }
            tool_source_files.append(file_dict)
            file_order += 1
        
        return tool_source_files
    
    def get_vivado_sources(self, verbose: bool = False) -> List[dict]:
        """
        Get source files for Vivado.
        Note: Vivado sources are now managed in the TCL file, not in JSON.
        This method returns an empty list.
        """
        # Vivado sources come from TCL file, not JSON
        return []
    
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

    def require_vivado_project_name(self) -> None:
        """Fail fast unless vivado.config.project_name is explicitly configured."""
        if self.vivado_project_name:
            return

        print(
            "[!x!] vivado.config.project_name is required for Vivado operations.\n"
            f"[i] Project file: {self._project_file_path}\n"
            "[i] HDLForge no longer falls back to settings.project_name, the project folder name, or the JSON filename."
        )
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
    
