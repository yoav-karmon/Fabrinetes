#!/usr/bin/env python3

import os
import glob
from invoke import task
from tabulate import tabulate

def show_command_help(command_name, command_data):
    """Show command-specific help with pretty table"""
    print(f"\n{command_name.upper()} Command Help")
    print("=" * 50)
    print(f"Syntax: {command_data['syntax']}")
    print(f"Description: {command_data['description']}")
    print()
    
    if 'arguments' in command_data:
        print("Arguments:")
        headers = ["Argument", "Description", "Required", "Allowed Values"]
        
        # Get running containers for commands that need container names
        running_containers = get_running_containers()
        
        # Modify arguments to show actual running containers
        modified_arguments = []
        for arg in command_data['arguments']:
            if len(arg) >= 4 and 'container-name' in arg[0] and 'From Docker Containers table above' in arg[3]:
                if running_containers:
                    arg[3] = ', '.join(running_containers)
                else:
                    arg[3] = 'No running containers found'
            modified_arguments.append(arg)
        
        print(tabulate(modified_arguments, headers=headers, tablefmt="grid"))
        print()
    
    if 'examples' in command_data:
        print("Examples:")
        for example in command_data['examples']:
            print(f"  {example}")

def get_running_containers():
    """Get list of running container names"""
    import subprocess
    try:
        result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], 
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            containers = [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
            return containers
        else:
            return []
    except Exception:
        return []

@task
def help(ctx):
    """Show help with pretty table of available repositories"""
    print("Fabrinetes - Docker Container Management Tool")
    print("=" * 60)
    
    # Find all config files
    config_files = glob.glob("containers/*/config.toml")
    
    if config_files:
        print("Available Repositories:")
        print("+------------------------+------------------------------------------------------------+")
        print("| Repository Name        | Config File                                                |")
        print("+------------------------+------------------------------------------------------------+")
        
        for config_file in sorted(config_files):
            # Extract repository name from path
            parts = config_file.split('/')
            if len(parts) >= 2:
                repo_name = parts[1]  # containers/REPO_NAME/config.toml
            else:
                repo_name = "unknown"
            
            print(f"| {repo_name:<22} | {config_file:<58} |")
        print("+------------------------+------------------------------------------------------------+")
        print("")
    else:
        print("No configuration files found in containers/*/config.toml")
        print("")
        print("To get started, create a config file in containers/<name>/config.toml")
        print("Example structure:")
        print("  containers/my-container/config.toml")
        print("")
    
    print("Options:")
    
    # Get running containers for dynamic display
    running_containers = get_running_containers()
    container_values = ', '.join(running_containers) if running_containers else 'No running containers found'
    
    options_data = [
        ["./fabrinetes gen-image", "[config-file] [--dry-run] [--base-image]", "Generate Docker image from config file", "config-file: containers/<path>/config.toml"],
        ["./fabrinetes run", "[config-file] [--rm] [--x11] [--usb] [--ask] [--verbose]", "Run container with specified config", "config-file: containers/<path>/config.toml"],
        ["./fabrinetes list", "", "List Docker images and containers", "None"],
        ["./fabrinetes exec", "--container-name [container-name] --command '[command]' [--interactive]", "Execute command in running container", f"container-name: {container_values}"],
        ["./fabrinetes shell", "--container-name [container-name]", "Open interactive shell in container", f"container-name: {container_values}"],
        ["./fabrinetes commit", "--container-name [name] [--tag <tag>] [--message <message>]", "Commit running container to new image", f"container-name: {container_values}"],
        ["./fabrinetes clean-image", "[image-name]", "Clean up containers and images", "image-name: from Docker Images table"],
        ["./fabrinetes kill", "[container-name]", "Stop and remove container", f"container-name: {container_values}"],
        ["./fabrinetes pkg", "--container-name [container-name]", "Package management: generate package file with versions and download .deb files", f"container-name: {container_values}"]
    ]
    headers = ["Command", "Arguments", "Description", "Allowed Values"]
    print(tabulate(options_data, headers=headers, tablefmt="grid"))
    
    print("\nExamples:")
    examples_data = [
        ["./fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml", "Generate container from config"],
        ["./fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml --base-image", "Generate base image from Dockerfile"],
        ["./fabrinetes run containers/fabrinetes-dev-testing/config.toml", "Run container with config"],
        ["./fabrinetes exec --container-name fabrinetes-dev-testing.latest.run --command 'ls -la'", "Execute command in container"],
        ["./fabrinetes shell --container-name fabrinetes-dev-testing.latest.run", "Open shell in container"],
        ["./fabrinetes pkg --container-name fabrinetes-dev-testing.latest.run", "Manage packages in container"]
    ]
    headers = ["Command", "Description"]
    print(tabulate(examples_data, headers=headers, tablefmt="grid"))
