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
        print(tabulate(command_data['arguments'], headers=headers, tablefmt="grid"))
        print()
    
    if 'examples' in command_data:
        print("Examples:")
        for example in command_data['examples']:
            print(f"  {example}")

@task
def help(ctx):
    """Show help with pretty table of available repositories"""
    print("Fabrinetes - Docker Container Management Tool")
    print("=" * 60)
    
    # Find all config files
    config_files = glob.glob("containers/*/config/*.config")
    
    if not config_files:
        print("No configuration files found in containers/*/config/")
        return
    
    print("Available Repositories:")
    print("+------------------------+------------------------------------------------------------+")
    print("| Repository Name        | Config File                                                |")
    print("+------------------------+------------------------------------------------------------+")
    
    for config_file in sorted(config_files):
        # Extract repository name from path
        parts = config_file.split('/')
        if len(parts) >= 3:
            repo_name = parts[1]  # containers/REPO_NAME/config/file.config
        else:
            repo_name = "unknown"
        
        print(f"| {repo_name:<22} | {config_file:<58} |")
    print("+------------------------+------------------------------------------------------------+")
    print("")
    print("Options:")
    options_data = [
        ["./fabrinetes build", "[repository-name] [--dry-run] [--export] [--skeleton]", "Build Docker image from skeleton by default", "fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full, skeleton"],
        ["./fabrinetes restore", "[repository-name] [--tar-file <path>]", "Restore Docker image from tar.gz file", "fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full"],
        ["./fabrinetes list", "", "List Docker images and containers", "None"],
        ["./fabrinetes run", "--file [config-file] --name [repository-name] [--rm] [--x11] [--usb] [--ask] [--verbose]", "Run container with specified config", "config-file: path to .config, repository-name: from table above, flags: optional"],
        ["./fabrinetes exec", "--container-name [container-name] --command '[command]' [--interactive]", "Execute command in running container", "container-name: from Docker Containers table, command: any shell command"],
        ["./fabrinetes shell", "--container-name [container-name]", "Open interactive shell in container", "container-name: from Docker Containers table"],
        ["./fabrinetes commit", "--container-name [name] [--tag <tag>] [--message <message>]", "Commit running container to new image", "container-name: from Docker Containers table, tag: optional"],
        ["./fabrinetes clean", "--file [config-file] [--name [repository-name]]", "Clean up containers and images", "config-file: path to .config, repository-name: optional"],
        ["./fabrinetes pkg", "[container-name]", "Package management: generate package file with versions and download .deb files", "container-name: from Docker Containers table"]
    ]
    headers = ["Command", "Arguments", "Description", "Allowed Values"]
    print(tabulate(options_data, headers=headers, tablefmt="grid"))
    
    print("\nExamples:")
    examples_data = [
        ["./fabrinetes build fabrinetes-dev-testing", "Build container from skeleton"],
        ["./fabrinetes build skeleton --skeleton", "Rebuild skeleton container"],
        ["./fabrinetes run --file containers/fabrinetes-dev-testing/config.toml", "Run container with config"],
        ["./fabrinetes exec --container-name fabrinetes-dev-testing-20251008-141316 --command 'ls -la'", "Execute command in container"],
        ["./fabrinetes shell --container-name fabrinetes-dev-testing-20251008-141316", "Open shell in container"],
        ["./fabrinetes pkg --container-name fabrinetes-dev-testing-20251008-141316", "Manage packages in container"]
    ]
    headers = ["Command", "Description"]
    print(tabulate(examples_data, headers=headers, tablefmt="grid"))
