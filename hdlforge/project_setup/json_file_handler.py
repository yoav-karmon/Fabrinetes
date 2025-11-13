#!/usr/bin/env python3
"""
Centralized JSON File Handler for HDLForge Project Files
Handles merging records with identical properties and flat formatting
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict


class JSONFileHandler:
    """
    Centralized handler for reading, writing, and processing HDLForge JSON project files.
    Handles merging records with identical properties and flat formatting.
    """
    
    @staticmethod
    def merge_file_records(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge file records that have identical hdlforge_properties and vivado_properties.
        
        Args:
            files: List of file records
            
        Returns:
            Merged list of file records
        """
        # Group files by their properties
        groups = defaultdict(list)
        
        for file_entry in files:
            # Create a key from the properties
            hdlforge_props = file_entry.get('hdlforge_properties', {})
            vivado_props = file_entry.get('vivado_properties', {})
            
            # Normalize UsedIn arrays to sorted lists for consistent comparison
            if 'UsedIn' in vivado_props and isinstance(vivado_props['UsedIn'], list):
                vivado_props = vivado_props.copy()  # Don't modify original
                vivado_props['UsedIn'] = sorted(vivado_props['UsedIn'])
            
            # Convert to JSON strings for comparison (sorted keys for consistency)
            hdlforge_key = json.dumps(hdlforge_props, sort_keys=True)
            vivado_key = json.dumps(vivado_props, sort_keys=True)
            key = (hdlforge_key, vivado_key)
            
            # Add file path to the group
            file_path = file_entry.get('file', '')
            groups[key].append(file_path)
        
        # Create merged records
        merged_files = []
        for (hdlforge_key, vivado_key), file_paths in groups.items():
            # Parse the properties back
            hdlforge_props = json.loads(hdlforge_key)
            vivado_props = json.loads(vivado_key)
            
            # Ensure UsedIn is normalized (sorted) in output
            if 'UsedIn' in vivado_props and isinstance(vivado_props['UsedIn'], list):
                vivado_props['UsedIn'] = sorted(vivado_props['UsedIn'])
            
            # Create merged record
            merged_record = {
                'file': file_paths if len(file_paths) > 1 else file_paths[0]
            }
            
            # Only add properties if they're not empty
            if hdlforge_props:
                merged_record['hdlforge_properties'] = hdlforge_props
            if vivado_props:
                merged_record['vivado_properties'] = vivado_props
            
            merged_files.append(merged_record)
        
        return merged_files
    
    @staticmethod
    def _format_json_value(value: Any, indent: int, level: int, compact_properties: bool = True) -> str:
        """
        Recursively format a JSON value with special handling for property dictionaries.
        
        Args:
            value: Value to format
            indent: Indentation spaces per level
            level: Current indentation level
            compact_properties: If True, format hdlforge_properties and vivado_properties as single lines
            
        Returns:
            Formatted string
        """
        indent_str = ' ' * (indent * level)
        next_indent = ' ' * (indent * (level + 1))
        
        if isinstance(value, dict):
            lines = []
            items = list(value.items())
            # Filter out empty properties if compact_properties is enabled
            filtered_items = []
            for key, val in items:
                if compact_properties and key in ['hdlforge_properties', 'vivado_properties'] and not val:
                    continue  # Skip empty properties
                filtered_items.append((key, val))
            
            for i, (key, val) in enumerate(filtered_items):
                key_str = json.dumps(key, ensure_ascii=False)
                
                # Check if this is a property dictionary that should be compact
                if compact_properties and key in ['hdlforge_properties', 'vivado_properties']:
                    # Format as compact single line (we know it's not empty from filter above)
                    compact = json.dumps(val, separators=(',', ':'))
                    lines.append(f'{indent_str}{key_str}: {compact}')
                elif isinstance(val, dict):
                    lines.append(f'{indent_str}{key_str}: {{')
                    lines.append(JSONFileHandler._format_json_value(val, indent, level + 1, compact_properties))
                    lines.append(f'{indent_str}}}')
                elif isinstance(val, list):
                    lines.append(f'{indent_str}{key_str}: [')
                    for j, item in enumerate(val):
                        item_str = JSONFileHandler._format_json_value(item, indent, level + 1, compact_properties)
                        if isinstance(item, dict):
                            lines.append(f'{next_indent}{{')
                            lines.append(item_str)
                            lines.append(f'{next_indent}}}')
                        else:
                            lines.append(f'{next_indent}{item_str}')
                        if j < len(val) - 1:
                            lines[-1] += ','
                    lines.append(f'{indent_str}]')
                else:
                    val_str = json.dumps(val, ensure_ascii=False)
                    lines.append(f'{indent_str}{key_str}: {val_str}')
                
                # Add comma if not the last item
                if i < len(filtered_items) - 1:
                    lines[-1] += ','
            
            return '\n'.join(lines)
        elif isinstance(value, list):
            lines = []
            for i, item in enumerate(value):
                item_str = JSONFileHandler._format_json_value(item, indent, level + 1, compact_properties)
                if isinstance(item, dict):
                    lines.append(f'{indent_str}{{')
                    lines.append(item_str)
                    lines.append(f'{indent_str}}}')
                else:
                    lines.append(f'{indent_str}{item_str}')
                if i < len(value) - 1:
                    lines[-1] += ','
            return '\n'.join(lines)
        else:
            return json.dumps(value, ensure_ascii=False)
    
    @staticmethod
    def read_json_file(file_path: Path) -> Dict[str, Any]:
        """
        Read and parse JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def write_json_file(file_path: Path, data: Dict[str, Any], merge_records: bool = True) -> None:
        """
        Write JSON file with merged records and compact property formatting.
        
        Args:
            file_path: Path to JSON file
            data: Data to write
            merge_records: If True, merge file records with identical properties
        """
        # Create a copy to avoid modifying original
        data_copy = json.loads(json.dumps(data))
        
        # Merge file records if requested
        if merge_records and 'sources' in data_copy and 'files' in data_copy['sources']:
            data_copy['sources']['files'] = JSONFileHandler.merge_file_records(data_copy['sources']['files'])
        
        # Format the entire JSON structure
        formatted = JSONFileHandler._format_json_value(data_copy, indent=2, level=0, compact_properties=True)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write(formatted)
            f.write('\n}\n')
