#!/usr/bin/env python3

import os
import sys

# Check imports first
try:
    import toml
    import docker
    print("🔧 Fabrinetes ready!")
except ImportError as e:
    print(f"❌ Missing package: {e}")
    print("\n👋 Exiting gracefully")
    sys.exit(1)

# Import ContainerInfo
from helper_functions.config.name_generator import ContainerInfo

def main():
    """Main function - command dispatcher"""
    parser = ContainerInfo.create_parser()
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    container_info = ContainerInfo.from_args(args)
    
    # Dispatch commands with try-catch
    if args.cmd == "build":
        try:
            from invoke_tasks.build.build import build
            build(args, container_info)
        except ImportError as e:
            print(f"❌ Failed to import build module: {e}")
            sys.exit(1)
    
    elif args.cmd == "run":
        try:
            from invoke_tasks.run.run import run
            run(args, container_info)
        except ImportError as e:
            print(f"❌ Failed to import run module: {e}")
            sys.exit(1)
    
    elif args.cmd == "commit":
        try:
            from invoke_tasks.commit.commit import commit
            commit(args, container_info)
        except ImportError as e:
            print(f"❌ Failed to import commit module: {e}")
            sys.exit(1)
    
    elif args.cmd == "restore":
        try:
            from invoke_tasks.restore.restore import restore
            restore(args, container_info)
        except ImportError as e:
            print(f"❌ Failed to import restore module: {e}")
            sys.exit(1)
    
    elif args.cmd == "status":
        try:
            container_info = ContainerInfo.get_container_info(container_info.config_file_resolved)
            print(f"Config: {os.path.basename(container_info.config_file_resolved)}")
            print(f"Image: {container_info.image_docker}")
            print(f"Container: {container_info.run_name}")
        except Exception as e:
            print(f"❌ Error checking status: {e}")
    
    elif args.cmd is None and args.config_file:
        print("Running all commands in sequence...")
        
        print("=== RUN ===")
        try:
            from invoke_tasks.run.run import run
            run(args, container_info)
        except ImportError as e:
            print(f"❌ Failed to import run module: {e}")
            sys.exit(1)
        
        print("=== COMMIT ===")
        try:
            from invoke_tasks.commit.commit import commit
            commit(args, container_info)
        except ImportError as e:
            print(f"❌ Failed to import commit module: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()