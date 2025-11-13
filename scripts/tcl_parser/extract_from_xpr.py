#!/usr/bin/env python3
"""
Extract file list and properties from Vivado .xpr project file (XML format)
Much faster than TCL parsing or Vivado batch mode
"""

import sys
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def resolve_vivado_path(path_str, xpr_file):
    """
    Resolve Vivado path variables like $PPRDIR, $PSRCDIR, etc.
    Based on the .xpr file location
    
    $PPRDIR = project directory (parent of _vivado)
    """
    xpr_path = Path(xpr_file).resolve()
    xpr_dir = xpr_path.parent
    
    # The xpr is typically at: project_dir/_vivado/project_name/project_name.xpr
    # $PPRDIR in Vivado XML refers to the directory containing the .xpr file
    # So $PPRDIR = _vivado/project_name
    # But for resolving paths, we want the actual project root (parent of _vivado)
    # Go up: xpr_dir -> _vivado/project_name -> _vivado -> project_dir
    project_root = xpr_dir.parent.parent
    # $PPRDIR in the XML actually refers to xpr_dir, not project_root
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
            # Try relative to project root first (most common)
            resolved = (project_root / path_str).resolve()
            if resolved.exists():
                return str(resolved)
            # Try relative to xpr directory
            resolved = (xpr_dir / path_str).resolve()
            if resolved.exists():
                return str(resolved)
            # Return the resolved path anyway (might not exist yet)
            return str((project_root / path_str).resolve())


def extract_file_properties(file_elem, xpr_file):
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


def extract_files_from_xpr(xpr_file, fileset_name='sources_1'):
    """
    Extract all files and their properties from a Vivado .xpr file
    
    Args:
        xpr_file: Path to .xpr file
        fileset_name: Name of the fileset to extract (default: 'sources_1')
    
    Returns:
        List of dicts, each containing 'path' and 'properties'
    """
    xpr_path = Path(xpr_file)
    if not xpr_path.exists():
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
        print("Warning: No FileSets element found", file=sys.stderr)
        return files
    
    # Find the specific FileSet
    fileset = None
    for fs in filesets.findall('FileSet'):
        if fs.get('Name') == fileset_name:
            fileset = fs
            break
    
    if fileset is None:
        print(f"Warning: FileSet '{fileset_name}' not found", file=sys.stderr)
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


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: extract_from_xpr.py <project.xpr> [fileset_name] [--json]", file=sys.stderr)
        sys.exit(1)
    
    xpr_file = sys.argv[1]
    fileset_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'sources_1'
    json_output = '--json' in sys.argv or '-j' in sys.argv
    
    try:
        files = extract_files_from_xpr(xpr_file, fileset_name)
        
        if json_output:
            output = {
                'files': files
            }
            print(json.dumps(output, indent=2))
        else:
            # Simple list output
            for file_entry in files:
                print(file_entry['path'])
                if 'properties' in file_entry:
                    for prop_name, prop_val in file_entry['properties'].items():
                        print(f"  {prop_name}: {prop_val}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

