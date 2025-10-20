#!/usr/bin/env python3

import os
import sys

# Check imports first
try:
    import toml
    import docker
except ImportError as e:
    print(f"Missing package: {e}")
    print("\nExiting gracefully")
    sys.exit(1)

# Import ContainerInfo and CommandConfig
from helper_functions.config.name_generator import ContainerInfo, CommandConfig

def main():
    """Main function - command dispatcher"""
    parser = ContainerInfo.create_parser()
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_usage()
        return
    
    # Handle help command early - doesn't need config file
    if args.cmd == "help":
        parser.print_help()
        return
    
    # Get command definition from centralized config
    all_commands = CommandConfig.get_all_commands()
    cmd_def = all_commands.get(args.cmd)
    
    if cmd_def is None:
        print("No command specified or invalid command")
        parser.print_usage()
        return
    
    # Handle commands that don't require config file
    if not cmd_def.requires_config:
        cmd_def.function(args, None)
        return
    
    # Check for help flag before requiring config file
    if args.show_help:
        cmd_def.function(args, None)
        return
    
    # For commands that require config file, just call the command function
    # The ContainerInfo dataclass will handle all processing and error detection internally
    container_info = ContainerInfo.from_args(args)
    cmd_def.function(args, container_info)

if __name__ == "__main__":
    main()