#!/usr/bin/env python3
"""
Display and formatting utilities for HDLForge
"""

import inspect
from pathlib import Path
from typing import List
from tabulate import tabulate


def print_task_args(local_vars: dict, REPO_TOP: str, allowed_values: dict[str, List[str]] = {}):
    """Print task arguments in a formatted table"""
    # Get the calling function name automatically
    caller_name = inspect.stack()[1].function  
    
    # Remove Invoke context (c), internal variables (_path, _full), and empty project argument
    # Also exclude internal metadata variables like ALLOWED_STEPS, TOOL_NAME, SCRIPT_DIR
    # Exclude callable objects (functions, methods, etc.)
    excluded_keys = {"c", "project", "ALLOWED_STEPS", "TOOL_NAME", "SCRIPT_DIR", "capture_environment_variables", "print_task_args"}
    args = {k: v for k, v in local_vars.items() 
            if k not in excluded_keys 
            and not k.endswith("_path") 
            and not k.endswith("_full")
            and not callable(v)}
    max_key_len = max(len(k) for k in args.keys()) if args else 0
    border = "=" * (max_key_len + 30)
    
    print(border)
    print(f"[i] Task: {caller_name}")
    print(border)
    print("file executed: ", Path(__file__).resolve())
    table=[["key","value","allowed"]]
    
    # Sort keys alphabetically
    sorted_keys = sorted(args.keys())
    
    # Maximum width for value column to keep table readable
    MAX_VALUE_WIDTH = 40
    MAX_ALLOWED_WIDTH = 35
    
    def truncate_value(val: str, max_width: int = MAX_VALUE_WIDTH) -> str:
        """Truncate long values with ellipsis"""
        if len(val) <= max_width:
            return val
        return val[:max_width-3] + "..."
    
    def truncate_allowed(val: str, max_width: int = MAX_ALLOWED_WIDTH) -> str:
        """Truncate allowed values more aggressively"""
        if len(val) <= max_width:
            return val
        return val[:max_width-3] + "..."
    
    for key in sorted_keys:
        try:
            value = args[key]
            # Special handling for project_file - show just the project file name
            if key == "project_file" and hasattr(value, 'project_file_path'):
                display_value = value.project_file_path.name
                table.append([key.ljust(max_key_len), display_value, ""])
                continue
            
            if( key in allowed_values):
                # Format value for display, truncate if needed
                display_value = str(value) if value is not None else ""
                if isinstance(value, list):
                    display_value = f"[{', '.join(map(str, value))}]"
                display_value = truncate_value(display_value)
                # For step parameter, show API flag names instead of internal step names
                if key == "step" and isinstance(value, list):
                    # Map internal step names to API flag names
                    step_to_flag = {
                        "list_runs": "--list_runs",
                        "reset_run": "--reset_run <run_name>",
                        "syn": "--syn <run_name>",
                        "impl": "--impl <run_name>",
                        "bit": "--bit <run_name>",
                        "lint": "--lint",
                        "all": "--all <run_name>",
                        "generate_prj_with_external_tcl": "--generate_prj_with_external_tcl",
                        "write_tcl": "--write_tcl",
                        "file_remove": "--file_remove --file_path <path>",
                        "file_add": "--file_add --file_path <path>"
                    }
                    flag_names = [step_to_flag.get(s, s) for s in value]
                    display_value = f"[{', '.join(flag_names)}]"
                    display_value = truncate_value(display_value)
                allowed_str = ', '.join(allowed_values[key])
                allowed_str = truncate_allowed(allowed_str)
                table.append([key.ljust(max_key_len), display_value, allowed_str])
            elif(not isinstance(value, dict) and not isinstance(value, list)):
                # Convert Path objects to strings
                if isinstance(value, Path):
                    value = str(value)
                # Skip if value can't be converted to string
                try:
                    str_value = str(value)
                    if REPO_TOP+"/" in str_value:
                        str_value = str_value.replace(REPO_TOP+"/", "$REPO_TOP/")
                    str_value = truncate_value(str_value)
                    table.append([key.ljust(max_key_len), str_value, ""])
                except:
                    # Skip variables that can't be converted to string
                    pass
            elif(isinstance(value, list)):
                # Format list nicely
                list_str = f"[{', '.join(map(str, value))}]"
                list_str = truncate_value(list_str)
                table.append([key.ljust(max_key_len), list_str, ""])
            elif(isinstance(value,dict)):
                # Format dict nicely, especially for dicts containing lists
                formatted_parts = []
                for k, v in value.items():
                    if isinstance(v, list):
                        formatted_parts.append(f"{k}: [{', '.join(map(str, v))}]")
                    else:
                        formatted_parts.append(f"{k}: {v}")
                print_str = ", ".join(formatted_parts)
                print_str = truncate_value(print_str)
                table.append([key.ljust(max_key_len), print_str, ""])
        except Exception as e:
            # Skip problematic variables silently
            continue
    print(tabulate(table, headers="firstrow", tablefmt="grid", colalign=("left", "left", "left")))
        
    print(border)
    print("")
    

def print_boxed(message: str, border_char: str = "=", padding: int = 2):
    """Print a message in a box with borders"""
    lines = message.split("\n")
    max_len = max(len(line) for line in lines)
    border = border_char * (max_len + padding * 2 + 2)
    
    print(border)
    for line in lines:
        print(f"{border_char}{' ' * padding}{line.ljust(max_len)}{' ' * padding}{border_char}")
    print(border)
    # Get the calling function name automatically
    caller_name = inspect.stack()[1].function  
    
    # Remove Invoke context (c), internal variables (_path, _full), and empty project argument
    # Also exclude internal metadata variables like ALLOWED_STEPS, TOOL_NAME, SCRIPT_DIR
    # Exclude callable objects (functions, methods, etc.)
    # Exclude run_name and file_path as they are derived from flag values, not direct parameters
    excluded_keys = {"c", "project", "ALLOWED_STEPS", "TOOL_NAME", "SCRIPT_DIR", "capture_environment_variables", "print_task_args", "run_name", "file_path"}
    args = {k: v for k, v in local_vars.items() 
            if k not in excluded_keys 
            and not k.endswith("_path") 
            and not k.endswith("_full")
            and not callable(v)}
    max_key_len = max(len(k) for k in args.keys()) if args else 0
    border = "=" * (max_key_len + 30)
    
    print(border)
    print(f"[i] Task: {caller_name}")
    print(border)
    print("file executed: ", Path(__file__).resolve())
    table=[["key","value","allowed"]]
    
    # Sort keys alphabetically
    sorted_keys = sorted(args.keys())
    
    # Maximum width for value column to keep table readable
    MAX_VALUE_WIDTH = 80
    
    def truncate_value(val: str, max_width: int = MAX_VALUE_WIDTH) -> str:
        """Truncate long values with ellipsis"""
        if len(val) <= max_width:
            return val
        return val[:max_width-3] + "..."
    
    for key in sorted_keys:
        try:
            value = args[key]
            # Special handling for project_file - show just the project file name
            if key == "project_file" and hasattr(value, 'project_file_path'):
                display_value = value.project_file_path.name
                table.append([key.ljust(max_key_len), display_value, ""])
                continue
            
            if( key in allowed_values):
                # Format value for display, truncate if needed
                display_value = str(value) if value is not None else ""
                if isinstance(value, list):
                    display_value = f"[{', '.join(map(str, value))}]"
                display_value = truncate_value(display_value)
                table.append([key.ljust(max_key_len), display_value, f"(allowed: {', '.join(allowed_values[key])})"])
            elif(not isinstance(value, dict) and not isinstance(value, list)):
                # Convert Path objects to strings
                if isinstance(value, Path):
                    value = str(value)
                # Skip if value can't be converted to string
                try:
                    str_value = str(value)
                    if REPO_TOP+"/" in str_value:
                        str_value = str_value.replace(REPO_TOP+"/", "$REPO_TOP/")
                    str_value = truncate_value(str_value)
                    table.append([key.ljust(max_key_len), str_value, ""])
                except:
                    # Skip variables that can't be converted to string
                    pass
            elif(isinstance(value, list)):
                # Format list nicely
                list_str = f"[{', '.join(map(str, value))}]"
                list_str = truncate_value(list_str)
                table.append([key.ljust(max_key_len), list_str, ""])
            elif(isinstance(value,dict)):
                # Format dict nicely, especially for dicts containing lists
                formatted_parts = []
                for k, v in value.items():
                    if isinstance(v, list):
                        formatted_parts.append(f"{k}: [{', '.join(map(str, v))}]")
                    else:
                        formatted_parts.append(f"{k}: {v}")
                print_str = ", ".join(formatted_parts)
                print_str = truncate_value(print_str)
                table.append([key.ljust(max_key_len), print_str, ""])
        except Exception as e:
            # Skip problematic variables silently
            continue
    print(tabulate(table, headers="firstrow", tablefmt="fancy_grid",colalign=("left", "left", "center")))
        
    print(border)
    print("")
    

def print_boxed(message: str, border_char: str = "=", padding: int = 2):
    """Print a message in a box with borders"""
    lines = message.split("\n")
    max_len = max(len(line) for line in lines)
    border = border_char * (max_len + padding * 2 + 2)
    
    print(border)
    for line in lines:
        print(f"{border_char}{' ' * padding}{line.ljust(max_len)}{' ' * padding}{border_char}")
    print(border)

