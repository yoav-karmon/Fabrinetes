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
from invoke_tasks import build, restore, commit, run, exec, shell, clean, pkg, list, help

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
        print("")

# Command-specific help data
COMMAND_HELP = {
    'run': {
        'syntax': './fabrinetes run --file <config-file> --name <repository-name> [--rm] [--x11] [--usb] [--ask] [--verbose]',
        'description': 'Run a Docker container with the specified configuration',
        'arguments': [
            ['--file', 'Path to the configuration file', 'Yes', 'containers/<path>/config/fabrinetes.config'],
            ['--name', 'Repository name from config', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full'],
            ['--rm', 'Automatically remove container when it exits', 'No', 'optional flag'],
            ['--x11', 'Enable X11 GUI support', 'No', 'optional flag'],
            ['--usb', 'Enable USB device access', 'No', 'optional flag'],
            ['--ask', 'Ask for confirmation before running', 'No', 'optional flag'],
            ['--verbose', 'Show detailed output', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes run --file containers/fabrinetes-dev-testing/config/fabrinetes.config --name fabrinetes-dev-testing',
            './fabrinetes run --file containers/fabrinetes-dev-testing/config/fabrinetes.config --name fabrinetes-dev-testing --rm --x11'
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
    'build': {
        'syntax': './fabrinetes build <repository-name> [--dry-run] [--export] [--skeleton]',
        'description': 'Build Docker image for the specified repository from skeleton by default',
        'arguments': [
            ['repository-name', 'Name of the repository to build', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full, skeleton'],
            ['--dry-run', 'Show what would be built without actually building', 'No', 'optional flag'],
            ['--export', 'Export built image to tar.gz file', 'No', 'optional flag'],
            ['--skeleton', 'Rebuild skeleton container (use with repository-name=skeleton)', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes build fabrinetes-dev-testing',
            './fabrinetes build skeleton --skeleton',
            './fabrinetes build fabrinetes-dev --dry-run',
            './fabrinetes build fabrinetes-dev-testing --export'
        ]
    },
    'restore': {
        'syntax': './fabrinetes restore <repository-name> [--tar-file <path>]',
        'description': 'Restore Docker image from tar.gz file instead of building',
        'arguments': [
            ['repository-name', 'Name of the repository to restore', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full'],
            ['--tar-file', 'Path to specific tar.gz file (optional)', 'No', 'path to .tar.gz file']
        ],
        'examples': [
            './fabrinetes restore fabrinetes-dev-testing',
            './fabrinetes restore fabrinetes-dev --tar-file containers/fabrinetes-dev/images/fabrinetes-dev-latest.tar.gz'
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
    'clean': {
        'syntax': './fabrinetes clean --file <config-file> [--name <repository-name>]',
        'description': 'Clean up containers and images for a specific configuration',
        'arguments': [
            ['--file', 'Path to the configuration file', 'Yes', 'containers/<path>/config/fabrinetes.config'],
            ['--name', 'Name of repository to clean (optional, cleans all if not specified)', 'No', 'repository name from config']
        ],
        'examples': [
            './fabrinetes clean --file containers/fabrinetes-dev-testing/config/fabrinetes.config',
            './fabrinetes clean --file containers/fabrinetes-dev-testing/config/fabrinetes.config --name fabrinetes-dev-testing'
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
    }
}
