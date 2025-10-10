#!/usr/bin/env python3

import os
import glob
import subprocess
from invoke import task

def get_running_containers():
    """Get list of running container names"""
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

def show_command_help(command_name, command_data):
    """Show command-specific help with clean line-by-line format"""
    print(f"\n{command_name.upper()} Command Help")
    print("=" * 50)
    print(f"Syntax: {command_data['syntax']}")
    print(f"Description: {command_data['description']}")
    print()
    
    if 'arguments' in command_data:
        print("Arguments:")
        print("-" * 30)
        
        # Get running containers for commands that need container names
        running_containers = get_running_containers()
        
        for i, arg in enumerate(command_data['arguments'], 1):
            print(f"\n{i}. {arg[0]}")
            print(f"   Description: {arg[1]}")
            print(f"   Required: {arg[2]}")
            
            # Handle container names dynamically
            if len(arg) >= 4 and 'container-name' in arg[0] and 'From Docker Containers table above' in arg[3]:
                if running_containers:
                    print(f"   Allowed Values: {', '.join(running_containers)}")
                else:
                    print(f"   Allowed Values: No running containers found")
            else:
                print(f"   Allowed Values: {arg[3]}")
        
        print()
    
    if 'examples' in command_data:
        print("Examples:")
        print("-" * 20)
        for i, example in enumerate(command_data['examples'], 1):
            print(f"\n{i}. {example}")
        print()

# Individual help functions for each task
def show_run_help():
    """Show help for run command"""
    command_data = {
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
    }
    show_command_help('run', command_data)

def show_exec_help():
    """Show help for exec command"""
    command_data = {
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
    }
    show_command_help('exec', command_data)

def show_shell_help():
    """Show help for shell command"""
    command_data = {
        'syntax': './fabrinetes shell --container-name <container-name>',
        'description': 'Open an interactive shell in a running container',
        'arguments': [
            ['--container-name', 'Name of the running container', 'Yes', 'From Docker Containers table above']
        ],
        'examples': [
            './fabrinetes shell --container-name fabrinetes-dev-testing-20251008-141316'
        ]
    }
    show_command_help('shell', command_data)

def show_gen_image_help():
    """Show help for gen-image command"""
    command_data = {
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
    }
    show_command_help('gen-image', command_data)

def show_commit_help():
    """Show help for commit command"""
    command_data = {
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
    }
    show_command_help('commit', command_data)

def show_clean_image_help():
    """Show help for clean-image command"""
    command_data = {
        'syntax': './fabrinetes clean-image <base-image>',
        'description': 'Clean up all containers and images for a specific base image',
        'arguments': [
            ['base-image', 'Base image name to clean (e.g., fabrinetes-skeleton:latest)', 'Yes', 'fabrinetes-skeleton:latest, fabrinetes-dev-testing:latest, etc.']
        ],
        'examples': [
            './fabrinetes clean-image fabrinetes-skeleton:latest',
            './fabrinetes clean-image fabrinetes-dev-testing:latest'
        ]
    }
    show_command_help('clean-image', command_data)

def show_kill_help():
    """Show help for kill command"""
    command_data = {
        'syntax': './fabrinetes kill <container-name>',
        'description': 'Stop and remove a specific container (not the image)',
        'arguments': [
            ['container-name', 'Name of the container to kill', 'Yes', 'From Docker Containers table above']
        ],
        'examples': [
            './fabrinetes kill fabrinetes-dev-testing.fabrinetes-skeleton.latest.run',
            './fabrinetes kill fabrinetes-skeleton.latest.run'
        ]
    }
    show_command_help('kill', command_data)

def show_pkg_help():
    """Show help for pkg command"""
    command_data = {
        'syntax': './fabrinetes pkg --container-name <container-name>',
        'description': 'Package management: generate package file with versions and download .deb files from containers',
        'arguments': [
            ['--container-name', 'Name of the running container to manage', 'Yes', 'From Docker Containers table above']
        ],
        'examples': [
            './fabrinetes pkg --container-name fabrinetes-dev-testing-20251008-154737'
        ]
    }
    show_command_help('pkg', command_data)

def show_test_help():
    """Show help for test command"""
    command_data = {
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
    show_command_help('test', command_data)

def show_list_help():
    """Show help for list command"""
    command_data = {
        'syntax': './fabrinetes list',
        'description': 'List Docker images and containers in a pretty table format',
        'arguments': [],
        'examples': [
            './fabrinetes list'
        ]
    }
    show_command_help('list', command_data)

def show_build_help():
    """Show help for build command (deprecated)"""
    command_data = {
        'syntax': './fabrinetes build <repository-name> [--skeleton] [--restore-only]',
        'description': 'Legacy build command - DEPRECATED, use gen-image instead',
        'arguments': [
            ['repository-name', 'Name of the repository/container to build', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, etc.'],
            ['--skeleton', 'Build skeleton base image', 'No', 'optional flag'],
            ['--restore-only', 'Only restore from tarball, don\'t build', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes build fabrinetes-dev-testing --skeleton',
            './fabrinetes build fabrinetes-dev-testing --restore-only'
        ]
    }
    show_command_help('build', command_data)

# Global help function for no arguments
def show_global_help():
    """Show global help when no arguments are provided"""
    print("Fabrinetes - Docker Container Management Tool")
    print("=" * 60)
    
    # Find all config files
    config_files = glob.glob("containers/*/config.toml")
    
    if config_files:
        print("\nAvailable Repositories:")
        print("-" * 40)
        
        for i, config_file in enumerate(sorted(config_files), 1):
            # Extract repository name from path
            parts = config_file.split('/')
            if len(parts) >= 2:
                repo_name = parts[1]  # containers/REPO_NAME/config.toml
            else:
                repo_name = "unknown"
            
            print(f"\n{i}. Repository: {repo_name}")
            print(f"   Config File: {config_file}")
        print()
    else:
        print("\nNo configuration files found in containers/*/config.toml")
        print("\nTo get started, create a config file in containers/<name>/config.toml")
        print("Example structure:")
        print("  containers/my-container/config.toml")
        print("")
    
    print("\nAvailable Commands:")
    print("-" * 30)
    
    # Get running containers for dynamic display
    running_containers = get_running_containers()
    container_values = ', '.join(running_containers) if running_containers else 'No running containers found'
    
    commands = [
        {
            'command': './fabrinetes gen-image',
            'args': '[config-file] [--dry-run] [--base-image]',
            'description': 'Generate Docker image from config file',
            'allowed_values': 'config-file: containers/<path>/config.toml'
        },
        {
            'command': './fabrinetes run',
            'args': '[config-file] [--rm] [--x11] [--usb] [--ask] [--verbose]',
            'description': 'Run container with specified config',
            'allowed_values': 'config-file: containers/<path>/config.toml'
        },
        {
            'command': './fabrinetes list',
            'args': '',
            'description': 'List Docker images and containers',
            'allowed_values': 'None'
        },
        {
            'command': './fabrinetes exec',
            'args': '--container-name [container-name] --command \'[command]\' [--interactive]',
            'description': 'Execute command in running container',
            'allowed_values': f'container-name: {container_values}'
        },
        {
            'command': './fabrinetes shell',
            'args': '--container-name [container-name]',
            'description': 'Open interactive shell in container',
            'allowed_values': f'container-name: {container_values}'
        },
        {
            'command': './fabrinetes commit',
            'args': '--container-name [name] [--tag <tag>] [--message <message>]',
            'description': 'Commit running container to new image',
            'allowed_values': f'container-name: {container_values}'
        },
        {
            'command': './fabrinetes clean-image',
            'args': '[image-name]',
            'description': 'Clean up containers and images',
            'allowed_values': 'image-name: from Docker Images table'
        },
        {
            'command': './fabrinetes kill',
            'args': '[container-name]',
            'description': 'Stop and remove container',
            'allowed_values': f'container-name: {container_values}'
        },
        {
            'command': './fabrinetes pkg',
            'args': '--container-name [container-name]',
            'description': 'Package management: generate package file with versions and download .deb files',
            'allowed_values': f'container-name: {container_values}'
        }
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"\n{i}. Command: {cmd['command']}")
        print(f"   Arguments: {cmd['args']}")
        print(f"   Description: {cmd['description']}")
        print(f"   Allowed Values: {cmd['allowed_values']}")
    
    print("\n\nExamples:")
    print("-" * 20)
    
    examples = [
        './fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml',
        './fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml --base-image',
        './fabrinetes run containers/fabrinetes-dev-testing/config.toml',
        './fabrinetes exec --container-name fabrinetes-dev-testing.latest.run --command \'ls -la\'',
        './fabrinetes shell --container-name fabrinetes-dev-testing.latest.run',
        './fabrinetes pkg --container-name fabrinetes-dev-testing.latest.run'
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example}")

@task
def help(ctx):
    """Show global help with pretty table of available repositories"""
    show_global_help()