#!/usr/bin/env python3

import os
import sys

# Check imports first
try:
    import toml
    import docker
except ImportError as e:
    print(f"❌ Missing package: {e}")
    print("\n👋 Exiting gracefully")
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
        print("❌ No command specified or invalid command")
        parser.print_usage()
        return
    
    # Handle commands that don't require config file
    if not cmd_def.requires_config:
        cmd_def.function(args, None)
        return
    
    # Handle commands that require config file
    try:
        container_info = ContainerInfo.from_args(args)
        
        # Special handling for status command
        if args.cmd == "status":
            container_info = ContainerInfo.get_container_info(container_info.config_file_resolved)
        
        # Execute the command
        cmd_def.function(args, container_info)
        
    except FileNotFoundError as e:
        print(f"❌ Config file not found: {e}")
    except Exception as e:
        print(f"❌ Error executing {args.cmd}: {e}")

if __name__ == "__main__":
    main()