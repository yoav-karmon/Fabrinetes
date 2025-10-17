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

# Import ContainerInfo
from helper_functions.config.name_generator import ContainerInfo

# Import command modules
from command.build.build import build
from command.run.run import run
from command.commit.commit import commit
from command.restore.restore import restore
from command.clean_images.clean_images import clean_images

# Import status helper
from helper_functions.status_helper import collect_comprehensive_status, format_status_output

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
    
    # Handle status command early - needs special error handling
    if args.cmd == "status":
        try:
            container_info = ContainerInfo.from_args(args)
            container_info = ContainerInfo.get_container_info(container_info.config_file_resolved)
            status = collect_comprehensive_status(container_info)
            print(format_status_output(status))
        except FileNotFoundError as e:
            print(f"❌ Config file not found: {e}")
        except Exception as e:
            print(f"❌ Error checking status: {e}")
        return
    
    container_info = ContainerInfo.from_args(args)
    
    # Dispatch commands
    if args.cmd == "build":
        build(args, container_info)
    
    elif args.cmd == "run":
        run(args, container_info)
    
    elif args.cmd == "commit":
        commit(args, container_info)
    
    elif args.cmd == "restore":
        restore(args, container_info)
    
    elif args.cmd == "clean-images":
        clean_images(args, container_info)
    
    elif args.cmd is None and args.config_file:
        print("Running all commands in sequence...")
        
        print("=== RUN ===")
        run(args, container_info)
        
        print("=== COMMIT ===")
        commit(args, container_info)

if __name__ == "__main__":
    main()