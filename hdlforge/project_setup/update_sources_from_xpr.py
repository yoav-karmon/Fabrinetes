#!/usr/bin/env python3
"""
Update HDLForge project sources from Vivado .xpr file
Extracts files and properties from XPR and updates the JSON structure
"""

import sys
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any
from json_file_handler import JSONFileHandler


def resolve_vivado_path(path_str: str, xpr_file: Path) -> str:
    """
    Resolve Vivado path variables like $PPRDIR, $PSRCDIR, etc.
    Based on the .xpr file location
    
    $PPRDIR = directory containing the .xpr file
    """
    xpr_path = Path(xpr_file).resolve()
    xpr_dir = xpr_path.parent
    
    # The xpr is typically at: project_dir/_vivado/project_name/project_name.xpr
    # $PPRDIR in Vivado XML refers to the directory containing the .xpr file
    # So $PPRDIR = _vivado/project_name
    pprdir = xpr_dir
    
    if path_str.startswith('$PPRDIR'):
        # Remove $PPRDIR and resolve relative to pprdir (xpr_dir)
        # $PPRDIR in XML = directory containing .xpr file
        rel_path = path_str.replace('$PPRDIR', '')
        rel_path = rel_path.lstrip('/')
        # Resolve from pprdir (xpr_dir)
        resolved = (pprdir / rel_path).resolve()
        return str(resolved)
    elif path_str.startswith('$PSRCDIR'):
        # Sources directory
        rel_path = path_str.replace('$PSRCDIR', '')
        rel_path = rel_path.lstrip('/')
        # Sources are typically in _vivado/project_name/project_name.srcs
        sources_dir = xpr_dir / f"{xpr_dir.name}.srcs"
        resolved = (sources_dir / rel_path).resolve()
        return str(resolved)
    else:
        # Try to resolve as-is
        if os.path.isabs(path_str):
            return path_str
        else:
            # Try relative to xpr directory
            resolved = (xpr_dir / path_str).resolve()
            if resolved.exists():
                return str(resolved)
            # Return the resolved path anyway (might not exist yet)
            return str(resolved)


def extract_file_properties(file_elem, xpr_file: Path) -> Dict[str, Any]:
    """Extract all properties from a File element"""
    properties = {}
    
    # Get the Path attribute
    path_attr = file_elem.get('Path', '')
    if path_attr:
        resolved_path = resolve_vivado_path(path_attr, xpr_file)
        properties['NAME'] = resolved_path
        properties['PATH'] = resolved_path
    
    # Get FileInfo attributes
    file_info = file_elem.find('FileInfo')
    if file_info is not None:
        for attr in file_info.findall('Attr'):
            attr_name = attr.get('Name', '')
            attr_val = attr.get('Val', '')
            
            if attr_name:
                # Handle multiple attributes with same name (like UsedIn)
                if attr_name in properties:
                    # Convert to list if not already
                    if not isinstance(properties[attr_name], list):
                        properties[attr_name] = [properties[attr_name]]
                    properties[attr_name].append(attr_val)
                else:
                    properties[attr_name] = attr_val
    
    # Get any other attributes directly on File element
    for attr_name, attr_val in file_elem.attrib.items():
        if attr_name != 'Path' and attr_name not in properties:
            properties[attr_name.upper()] = attr_val
    
    return properties


def extract_files_from_xpr(xpr_file: Path, fileset_name: str = 'sources_1') -> List[Dict[str, Any]]:
    """
    Extract all files and their properties from a Vivado .xpr file
    
    Args:
        xpr_file: Path to .xpr file
        fileset_name: Name of the fileset to extract (default: 'sources_1')
    
    Returns:
        List of dicts, each containing 'path' and 'properties'
    """
    if not xpr_file.exists():
        raise FileNotFoundError(f"XPR file not found: {xpr_file}")
    
    # Parse XML
    try:
        tree = ET.parse(xpr_file)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse XML: {e}")
    
    files = []
    
    # Find FileSets element
    filesets = root.find('FileSets')
    if filesets is None:
        return files
    
    # Find the specific FileSet
    fileset = None
    for fs in filesets.findall('FileSet'):
        if fs.get('Name') == fileset_name:
            fileset = fs
            break
    
    if fileset is None:
        return files
    
    # Extract all File elements
    for file_elem in fileset.findall('File'):
        properties = extract_file_properties(file_elem, xpr_file)
        
        # Get the resolved path
        file_path = properties.get('NAME') or properties.get('PATH', '')
        if not file_path:
            # Fallback to Path attribute
            path_attr = file_elem.get('Path', '')
            file_path = resolve_vivado_path(path_attr, xpr_file)
        
        # Normalize path
        if file_path:
            file_path = str(Path(file_path).resolve())
        
        # Build file entry
        file_entry = {
            'path': file_path
        }
        
        # Add properties (exclude path/name from properties dict to avoid duplication)
        props_dict = {k: v for k, v in properties.items() if k not in ['NAME', 'PATH']}
        if props_dict:
            file_entry['properties'] = props_dict
        
        files.append(file_entry)
    
    return files


def _compare_properties(old_props: Dict[str, Any], new_props: Dict[str, Any], file_path: str) -> List[str]:
    """
    Compare old and new properties and return list of differences.
    
    Args:
        old_props: Existing properties from JSON
        new_props: New properties from XPR
        file_path: File path for logging
    
    Returns:
        List of difference messages
    """
    differences = []
    
    # Normalize properties for comparison (handle list vs string for UsedIn)
    def normalize_value(val):
        if isinstance(val, list):
            return sorted(val) if all(isinstance(x, str) for x in val) else val
        return val
    
    # Check all keys in both old and new
    all_keys = set(old_props.keys()) | set(new_props.keys())
    
    for key in all_keys:
        old_val = old_props.get(key)
        new_val = new_props.get(key)
        
        # Normalize for comparison
        old_normalized = normalize_value(old_val)
        new_normalized = normalize_value(new_val)
        
        if old_val is None:
            differences.append(f"  [+] Added property '{key}': {new_val}")
        elif new_val is None:
            differences.append(f"  [-] Removed property '{key}': {old_val}")
        elif old_normalized != new_normalized:
            differences.append(f"  [~] Changed property '{key}': {old_val} → {new_val}")
    
    return differences


def update_sources_from_xpr(project_loader, xpr_file: Path, working_path: Path) -> bool:
    """
    Update project sources from XPR file.
    Converts each file to its own JSON record with vivado/verilator flags.
    Logs property differences between JSON and XPR.
    
    Args:
        project_loader: ProjectLoader instance
        xpr_file: Path to .xpr file
        working_path: Project working directory (for relative paths)
    
    Returns:
        True if sources were updated, False otherwise
    """
    try:
        # Get existing files from JSON for comparison
        existing_files = {}
        if 'sources' in project_loader._project_data and 'files' in project_loader._project_data['sources']:
            for file_entry in project_loader._project_data['sources']['files']:
                file_path = file_entry.get('file', '')
                # Handle both string and list formats
                if isinstance(file_path, list):
                    for fp in file_path:
                        # Resolve path relative to working_path
                        try:
                            if Path(fp).is_absolute():
                                abs_fp = Path(fp).resolve()
                            else:
                                abs_fp = (working_path / fp).resolve()
                            existing_files[str(abs_fp)] = {
                                'hdlforge_properties': file_entry.get('hdlforge_properties', {}),
                                'vivado_properties': file_entry.get('vivado_properties', {})
                            }
                        except Exception:
                            # Skip if path can't be resolved
                            pass
                else:
                    # Resolve path relative to working_path
                    try:
                        if Path(file_path).is_absolute():
                            abs_fp = Path(file_path).resolve()
                        else:
                            abs_fp = (working_path / file_path).resolve()
                        existing_files[str(abs_fp)] = {
                            'hdlforge_properties': file_entry.get('hdlforge_properties', {}),
                            'vivado_properties': file_entry.get('vivado_properties', {})
                        }
                    except Exception:
                        # Skip if path can't be resolved
                        pass
        
        # Extract files from XPR
        xpr_files = extract_files_from_xpr(xpr_file, 'sources_1')
        
        if not xpr_files:
            print("[!] No files found in XPR file")
            return False
        
        # Convert to new structure: each file is its own record
        new_files = []
        property_changes_found = False
        
        for xpr_file_entry in xpr_files:
            abs_path = Path(xpr_file_entry['path'])
            props = xpr_file_entry.get('properties', {})
            
            # Make path relative to project
            try:
                rel_path = abs_path.relative_to(working_path)
            except ValueError:
                # Path is not under working_path, use absolute
                rel_path = abs_path
            
            # Determine file type and tool flags
            file_ext = abs_path.suffix.lower()
            is_verilog = file_ext in ['.sv', '.v']
            is_vhdl = file_ext in ['.vhd', '.vhdl']
            is_xdc = file_ext == '.xdc'
            is_ip = file_ext in ['.xci', '.xcix']
            
            # Default: All files in XPR are for Vivado
            vivado = True
            
            # Verilator: Only RTL files (Verilog/VHDL) that are used in simulation
            verilator = False
            if is_verilog or is_vhdl:
                # Check UsedIn property to determine if it's for simulation
                used_in = props.get('UsedIn', [])
                if isinstance(used_in, str):
                    used_in = [used_in]
                
                # If file is marked for simulation, include in Verilator
                if 'simulation' in used_in:
                    verilator = True
            
            # Create file record
            file_record = {
                'file': str(rel_path)
            }
            
            # Add HDLForge properties (compact, single line format)
            file_record['hdlforge_properties'] = {
                'vivado': vivado,
                'verilator': verilator,
                'relative_to_project_path': True
            }
            
            # Add Vivado properties if any (excluding internal ones)
            vivado_props = {}
            for key, value in props.items():
                # Skip internal/read-only properties
                if not key.startswith('IS_') and not key.startswith('CLASS_'):
                    # Normalize UsedIn array to sorted list for consistent merging
                    if key == 'USEDIN' and isinstance(value, list):
                        vivado_props[key] = sorted(value)
                    else:
                        vivado_props[key] = value
            
            if vivado_props:
                file_record['vivado_properties'] = vivado_props
            
            # Compare with existing properties
            abs_path_str = str(abs_path.resolve())
            if abs_path_str in existing_files:
                existing = existing_files[abs_path_str]
                existing_hdlforge = existing.get('hdlforge_properties', {})
                existing_vivado = existing.get('vivado_properties', {})
                new_hdlforge = file_record.get('hdlforge_properties', {})
                new_vivado = file_record.get('vivado_properties', {})
                
                # Check HDLForge properties
                hdlforge_diffs = _compare_properties(existing_hdlforge, new_hdlforge, str(rel_path))
                # Check Vivado properties
                vivado_diffs = _compare_properties(existing_vivado, new_vivado, str(rel_path))
                
                if hdlforge_diffs or vivado_diffs:
                    property_changes_found = True
                    print(f"[~] Property changes detected for: {rel_path}")
                    if hdlforge_diffs:
                        print("  HDLForge properties:")
                        for diff in hdlforge_diffs:
                            print(diff)
                    if vivado_diffs:
                        print("  Vivado properties:")
                        for diff in vivado_diffs:
                            print(diff)
            
            new_files.append(file_record)
        
        # Merge files with identical properties
        merged_files = JSONFileHandler.merge_file_records(new_files)
        
        # Update project data
        if 'sources' not in project_loader._project_data:
            project_loader._project_data['sources'] = {}
        
        project_loader._project_data['sources']['files'] = merged_files
        project_loader.sources = project_loader._project_data['sources']
        
        # Always return True to trigger save (merging may have changed structure even if no property changes)
        return True
        
    except Exception as e:
        print(f"[!x!] Error updating sources from XPR: {e}")
        import traceback
        traceback.print_exc()
        return None

