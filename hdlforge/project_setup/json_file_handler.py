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
        Merge file records that have identical properties.
        Supports both old nested format (hdlforge_properties) and new flat format.
        
        Args:
            files: List of file records
            
        Returns:
            Merged list of file records
        """
        # Group files by their properties
        groups = defaultdict(list)
        
        for file_entry in files:
            # Normalize properties - extract from nested or flat format
            if 'hdlforge_properties' in file_entry:
                # Old format: nested in hdlforge_properties
                props = file_entry.get('hdlforge_properties', {}).copy()
            else:
                # New format: flat structure - extract properties (exclude 'file')
                props = {k: v for k, v in file_entry.items() if k != 'file'}
            
            # Convert to JSON strings for comparison (sorted keys for consistency)
            props_key = json.dumps(props, sort_keys=True)
            
            # Add file path to the group
            file_path = file_entry.get('file', '')
            groups[props_key].append(file_path)
        
        # Create merged records
        merged_files = []
        for props_key, file_paths in groups.items():
            # Parse the properties back
            props = json.loads(props_key)
            
            # Create merged record
            merged_record = {
                'file': file_paths if len(file_paths) > 1 else file_paths[0]
            }
            
            # Add properties in new flat format
            if props:
                merged_record.update(props)
            
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
                # Note: hdlforge_properties is deprecated, but we still handle it for backward compatibility
                if compact_properties and key == 'hdlforge_properties' and not val:
                    continue  # Skip empty properties
                filtered_items.append((key, val))
            
            for i, (key, val) in enumerate(filtered_items):
                key_str = json.dumps(key, ensure_ascii=False)
                
                # Check if this is a property dictionary that should be compact
                # Note: hdlforge_properties is deprecated, but we still handle it for backward compatibility
                if compact_properties and key == 'hdlforge_properties':
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
        # Sources are now a flat array under verilator.config.sources
        verilator_section = data_copy.get('verilator', {})
        verilator_config = verilator_section.get('config', {})
        verilator_sources = verilator_config.get('sources', [])
        
        # Support both old format (dict with 'files') and new format (flat array)
        if isinstance(verilator_sources, dict) and 'files' in verilator_sources:
            # Old format: convert to new format
            old_files = verilator_sources.get('files', [])
            # Extract file paths from old format
            file_paths = []
            for file_entry in old_files:
                if isinstance(file_entry, dict):
                    file_path = file_entry.get('file', '')
                    if isinstance(file_path, list):
                        file_paths.extend(file_path)
                    else:
                        file_paths.append(file_path)
                else:
                    file_paths.append(file_entry)
            verilator_sources = file_paths
        
        # Ensure sources is a list
        if not isinstance(verilator_sources, list):
            verilator_sources = []
        
        # Ensure the structure is properly nested
        if 'verilator' not in data_copy:
            data_copy['verilator'] = {}
        if 'config' not in data_copy['verilator']:
            data_copy['verilator']['config'] = {}
        data_copy['verilator']['config']['sources'] = verilator_sources
        
        # Format the entire JSON structure
        formatted = JSONFileHandler._format_json_value(data_copy, indent=2, level=0, compact_properties=True)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write(formatted)
            f.write('\n}\n')
        # Group files by their properties
        groups = defaultdict(list)
        
        for file_entry in files:
            # Normalize properties - extract from nested or flat format
            if 'hdlforge_properties' in file_entry:
                # Old format: nested in hdlforge_properties
                props = file_entry.get('hdlforge_properties', {}).copy()
            else:
                # New format: flat structure - extract properties (exclude 'file')
                props = {k: v for k, v in file_entry.items() if k != 'file'}
            
            # Convert to JSON strings for comparison (sorted keys for consistency)
            props_key = json.dumps(props, sort_keys=True)
            
            # Add file path to the group
            file_path = file_entry.get('file', '')
            groups[props_key].append(file_path)
        
        # Create merged records
        merged_files = []
        for props_key, file_paths in groups.items():
            # Parse the properties back
            props = json.loads(props_key)
            
            # Create merged record
            merged_record = {
                'file': file_paths if len(file_paths) > 1 else file_paths[0]
            }
            
            # Add properties in new flat format
            if props:
                merged_record.update(props)
            
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
                # Note: hdlforge_properties is deprecated, but we still handle it for backward compatibility
                if compact_properties and key == 'hdlforge_properties' and not val:
                    continue  # Skip empty properties
                filtered_items.append((key, val))
            
            for i, (key, val) in enumerate(filtered_items):
                key_str = json.dumps(key, ensure_ascii=False)
                
                # Check if this is a property dictionary that should be compact
                # Note: hdlforge_properties is deprecated, but we still handle it for backward compatibility
                if compact_properties and key == 'hdlforge_properties':
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
        # Sources are now a flat array under verilator.config.sources
        verilator_section = data_copy.get('verilator', {})
        verilator_config = verilator_section.get('config', {})
        verilator_sources = verilator_config.get('sources', [])
        
        # Support both old format (dict with 'files') and new format (flat array)
        if isinstance(verilator_sources, dict) and 'files' in verilator_sources:
            # Old format: convert to new format
            old_files = verilator_sources.get('files', [])
            # Extract file paths from old format
            file_paths = []
            for file_entry in old_files:
                if isinstance(file_entry, dict):
                    file_path = file_entry.get('file', '')
                    if isinstance(file_path, list):
                        file_paths.extend(file_path)
                    else:
                        file_paths.append(file_path)
                else:
                    file_paths.append(file_entry)
            verilator_sources = file_paths
        
        # Ensure sources is a list
        if not isinstance(verilator_sources, list):
            verilator_sources = []
        
        # Ensure the structure is properly nested
        if 'verilator' not in data_copy:
            data_copy['verilator'] = {}
        if 'config' not in data_copy['verilator']:
            data_copy['verilator']['config'] = {}
        data_copy['verilator']['config']['sources'] = verilator_sources
        
        # Format the entire JSON structure
        formatted = JSONFileHandler._format_json_value(data_copy, indent=2, level=0, compact_properties=True)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write(formatted)
            f.write('\n}\n')
