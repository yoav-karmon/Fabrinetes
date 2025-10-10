#!/usr/bin/env python3

from dataclasses import asdict, dataclass
import toml
from invoke import task
import os
import re
import sys
import shutil
import subprocess
import argparse
import time
import json
import yaml
from dataclasses import dataclass, asdict
import os
import toml
from tabulate import tabulate
import pathlib 
import logging
import datetime

# Import all tasks from modular structure
from invoke_tasks import gen_image, commit, run, exec, shell, clean_image, kill, pkg, list, help, test

def export_image(ctx, repo_name, tag):
    """Export Docker image to tar.gz file"""
    import subprocess
    
    # Create images directory if it doesn't exist
    images_dir = f"containers/{repo_name}/images"
    os.makedirs(images_dir, exist_ok=True)
    
    # Export image
    tar_filename = f"{repo_name}-{tag}.tar.gz"
    tar_path = f"{images_dir}/{tar_filename}"
    
    print(f"Exporting {repo_name}:{tag} to {tar_path}...")
    
    try:
        # Use subprocess to handle the pipe properly
        result = subprocess.run(
            f"docker save {repo_name}:{tag} | gzip > {tar_path}",
            shell=True, check=True, capture_output=True, text=True
        )
        print(f"Successfully exported image to {tar_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error exporting image: {e}")
        print(f"stderr: {e.stderr}")

def import_image(ctx, tar_path):
    """Import Docker image from tar.gz file"""
    if not os.path.exists(tar_path):
        print(f"Error: File {tar_path} does not exist")
        return False
    
    print(f"Importing image from {tar_path}...")
    
    try:
        result = subprocess.run(
            f"gunzip -c {tar_path} | docker load",
            shell=True, check=True, capture_output=True, text=True
        )
        print(f"Successfully imported image from {tar_path}")
        print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error importing image: {e}")
        print(f"stderr: {e.stderr}")
        return False

def show_command_help(command_name, command_data):
    """Show command-specific help with pretty table"""
    from tabulate import tabulate
    import subprocess
    
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
        print("")

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

# Command-specific help data
COMMAND_HELP = {
    'run': {
        'syntax': './fabrinetes run --file <config-file> [--rm] [--x11] [--usb] [--ask] [--verbose]',
        'description': 'Run a Docker container with the specified configuration (container name auto-generated from config path)',
        'arguments': [
            ['--file', 'Path to the configuration file', 'Yes', 'containers/<path>/config.toml'],
            ['--rm', 'Automatically remove container when it exits', 'No', 'optional flag'],
            ['--x11', 'Enable X11 GUI support', 'No', 'optional flag'],
            ['--usb', 'Enable USB device access', 'No', 'optional flag'],
            ['--ask', 'Ask for confirmation before running', 'No', 'optional flag'],
            ['--verbose', 'Show detailed output', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes run --file containers/fabrinetes-dev-testing/config.toml',
            './fabrinetes run --file containers/fabrinetes-dev-testing/config.toml --rm --x11'
        ]
    },
    'exec': {
        'syntax': './fabrinetes exec --container-name <container-name> --command \'<command>\' [--interactive]',
        'description': 'Execute a command in a running container',
        'arguments': [
            ['--container-name', 'Name of the running container', 'Yes', 'From Docker Containers table above'],
            ['--command', 'Command to execute (must be quoted)', 'Yes', 'Any shell command'],
            ['--interactive', 'Run command in interactive mode', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes exec --container-name fabrinetes-dev-testing-20251008-141316 --command \'ls -la\'',
            './fabrinetes exec --container-name fabrinetes-dev-testing-20251008-141316 --command \'python --version\' --interactive'
        ]
    },
    'shell': {
        'syntax': './fabrinetes shell --container-name <container-name>',
        'description': 'Open an interactive shell in a running container',
        'arguments': [
            ['--container-name', 'Name of the running container', 'Yes', 'From Docker Containers table above']
        ],
        'examples': [
            './fabrinetes shell --container-name fabrinetes-dev-testing-20251008-141316'
        ]
    },
    'gen-image': {
        'syntax': './fabrinetes gen-image <config-file> [--dry-run] [--base-image]',
        'description': 'Generate Docker image from config file - restore if tarball exists, otherwise build from base image',
        'arguments': [
            ['config-file', 'Path to config.toml file', 'Yes', 'containers/<path>/config.toml'],
            ['--dry-run', 'Show what would be generated without actually generating', 'No', 'optional flag'],
            ['--base-image', 'Build base image from Dockerfile instead of creating new image', 'No', 'optional flag'],
        ],
        'examples': [
            './fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml',
            './fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml --dry-run',
            './fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml --base-image'
        ]
    },
    'commit': {
        'syntax': './fabrinetes commit --container-name <name> [--tag <tag>] [--message <message>]',
        'description': 'Commit running container to new image',
        'arguments': [
            ['--container-name', 'Name of the running container', 'Yes', 'From Docker Containers table above'],
            ['--tag', 'Tag for the new image (default: latest)', 'No', 'any tag name'],
            ['--message', 'Commit message (optional)', 'No', 'any message']
        ],
        'examples': [
            './fabrinetes commit --container-name fabrinetes-dev-testing-20251008-141316',
            './fabrinetes commit --container-name fabrinetes-dev-testing-20251008-141316 --tag v1.0 --message "Added new features"'
        ]
    },
    'clean-image': {
        'syntax': './fabrinetes clean-image <base-image>',
        'description': 'Clean up all containers and images for a specific base image',
        'arguments': [
            ['base-image', 'Base image name to clean (e.g., fabrinetes-skeleton:latest)', 'Yes', 'fabrinetes-skeleton:latest, fabrinetes-dev-testing:latest, etc.']
        ],
        'examples': [
            './fabrinetes clean-image fabrinetes-skeleton:latest',
            './fabrinetes clean-image fabrinetes-dev-testing:latest'
        ]
    },
    'kill': {
        'syntax': './fabrinetes kill <container-name>',
        'description': 'Stop and remove a specific container (not the image)',
        'arguments': [
            ['container-name', 'Name of the container to kill', 'Yes', 'From Docker Containers table above']
        ],
        'examples': [
            './fabrinetes kill fabrinetes-dev-testing.fabrinetes-skeleton.latest.run',
            './fabrinetes kill fabrinetes-skeleton.latest.run'
        ]
    },
    'pkg': {
        'syntax': './fabrinetes pkg --container-name <container-name>',
        'description': 'Package management: generate package file with versions and download .deb files from containers',
        'arguments': [
            ['--container-name', 'Name of the running container to manage', 'Yes', 'fabrinetes-dev-testing-20251008-163531\nfabrinetes-dev-testing-20251008-163423\nfabrinetes-dev-testing-20251008-154737\nfabrinetes-dev-testing-20251008-153929\nfabrinetes-fpga-dev-1']
        ],
        'examples': [
            './fabrinetes pkg --container-name fabrinetes-dev-testing-20251008-154737'
        ]
    },
    'test': {
        'syntax': './fabrinetes test --command <command> [--test-number <number>]',
        'description': 'Test commands using comprehensive test vectors with fabrinetes-dev-testing container',
        'arguments': [
            ['--command', 'Test command to run', 'Yes', 'run, gen-image, clean-image, kill, commit, exec, shell, pkg, all'],
            ['--test-number', 'Run specific test by number (1-based)', 'No', '1, 2, 3, etc.']
        ],
        'examples': [
            './fabrinetes test --command run',
            './fabrinetes test --command run --test-number 5',
            './fabrinetes test --command gen-image', 
            './fabrinetes test --command clean-image',
            './fabrinetes test --command kill',
            './fabrinetes test --command commit',
            './fabrinetes test --command exec',
            './fabrinetes test --command shell',
            './fabrinetes test --command pkg',
            './fabrinetes test --command all'
        ]
    }
}
