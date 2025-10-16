#!/usr/bin/env python3

import os
import sys
import subprocess
import pathlib
from helper_functions.config.name_generator import ContainerInfo

# Global variables
SCRIPT_PATH = os.path.abspath(__file__)
TASKS_DIR = os.path.dirname(SCRIPT_PATH)
LOG_DIR = os.path.join(TASKS_DIR, "logs")
ORIGINAL_WORKING_DIR = os.getcwd()

def setup_logging():
    """Setup logging directory and return logfile path"""
    os.makedirs(LOG_DIR, exist_ok=True)
    logfile = os.path.join(LOG_DIR, "fabrinetes.log")
    return logfile


def log_command(logfile, command):
    """Log executed command to logfile"""
    with open(logfile, 'a') as f:
        f.write(f"{command}\n")

def config_status(config_file):
    """Show config file status"""
    try:
        container_info = ContainerInfo.get_container_info(config_file)
        
        print("Fabrinetes - Config File Status")
        print("=" * 60)
        print(f"Config File: {os.path.basename(config_file)}")
        print()
        print("Status:")
        print("-" * 20)
        
        # Check base image
        base_image_exists = check_image_exists(container_info.base_image_docker)
        base_tarball_exists = container_info.resolve(os.path.join(container_info.tarball_directory, container_info.base_image_tarball)) is not None
        
        print(f"Base Image:    {'✅' if base_image_exists else '❌'} Docker  {'✅' if base_tarball_exists else '❌'} Tarball")
        
        # Check main image
        main_image_exists = check_image_exists(container_info.image_docker)
        main_tarball_exists = container_info.resolve(container_info.tarball_path) is not None
        
        print(f"Main Image:    {'✅' if main_image_exists else '❌'} Docker  {'✅' if main_tarball_exists else '❌'} Tarball")
        
        # Check container status
        container_status = check_container_status(container_info.run_name)
        if container_status == "running":
            print(f"Container:     🟢 Running")
        elif container_status == "stopped":
            print(f"Container:     🟡 Stopped")
        else:
            print(f"Container:     🔴 None")
        
        print()
        
    except Exception as e:
        print(f"❌ Error processing config file: {e}")

def check_image_exists(image_name):
    """Check if Docker image exists"""
    try:
        result = subprocess.run(f"docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}}'", 
                              shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            images = [img.strip() for img in result.stdout.strip().split('\n') if img.strip()]
            return image_name in images
        return False
    except Exception:
        return False

def check_container_status(container_name):
    """Check container status: running, stopped, or none"""
    try:
        # Check if container is running
        result = subprocess.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", 
                              shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return "running"
        
        # Check if container exists but is stopped
        result = subprocess.run(f"docker ps -a --filter name={container_name} --format '{{{{.Names}}}}'", 
                              shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return "stopped"
        
        return "none"
    except Exception:
        return "none"

def main():
    """Main function using argparse and command dispatcher"""
    # Parse arguments first
    parser = ContainerInfo.create_parser()
    args = parser.parse_args()
    
    # Handle special cases for help and no arguments after parsing
    if len(sys.argv) == 1:
        # No arguments - show help
        parser.print_help()
        return
    
    # Setup environment
    logfile = setup_logging()
    
    # Set environment variables
    os.environ['WORKDIR'] = ORIGINAL_WORKING_DIR
    
    # Create container info from config file (can be None)
    container_info = ContainerInfo.from_args(args)
    
    # Log the command
    cmd_str = " ".join(sys.argv[1:])
    log_command(logfile, f"python3 fabrinetes.py {cmd_str}")
    
    # Dispatch command directly
    if args.cmd == "build":
        from invoke_tasks.build.build import build
        build(args, container_info)
    
    if args.cmd == "run":
        from invoke_tasks.run.run import run
        run(args, container_info)
    
    if args.cmd == "commit":
        from invoke_tasks.commit.commit import commit
        commit(args, container_info)
    
    if args.cmd == "restore":
        from invoke_tasks.restore.restore import restore
        restore(args, container_info)
    
    if args.cmd == "status":
        config_status(container_info.config_file_resolved)

if __name__ == "__main__":
    main()
