#!/usr/bin/env python3

import os
import glob
import subprocess
from invoke import task
from helper_functions.name_generator import get_container_info

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

def check_image_exists(image_name):
    """Check if Docker image exists"""
    try:
        result = subprocess.run(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'], 
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            images = [img.strip() for img in result.stdout.strip().split('\n') if img.strip()]
            return image_name in images
        return False
    except Exception:
        return False

def check_tarball_exists(tarball_path):
    """Check if tarball file exists"""
    return os.path.exists(tarball_path)

def check_container_status(container_name):
    """Check container status: running, stopped, or none"""
    try:
        # Check if container is running
        result = subprocess.run(['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'], 
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return "running"
        
        # Check if container exists but is stopped
        result = subprocess.run(['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}'], 
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return "stopped"
        
        return "none"
    except Exception:
        return "none"

def get_config_status(config_file):
    """Get comprehensive status for a config file"""
    try:
        container_info = get_container_info(config_file)
        
        # Check base image status
        base_image_exists = check_image_exists(container_info.base_image_docker)
        base_tarball_exists = check_tarball_exists(container_info.tarball_directory + "/" + container_info.base_image_tarball)
        
        # Check main image status
        main_image_exists = check_image_exists(container_info.image_docker)
        main_tarball_exists = check_tarball_exists(container_info.tarball_path)
        
        # Check container status
        container_status = check_container_status(container_info.run_name)
        
        return {
            'base_image': {
                'exists': base_image_exists,
                'tarball_exists': base_tarball_exists
            },
            'main_image': {
                'exists': main_image_exists,
                'tarball_exists': main_tarball_exists
            },
            'container': {
                'status': container_status
            }
        }
    except Exception as e:
        return {
            'error': str(e),
            'base_image': {'exists': False, 'tarball_exists': False},
            'main_image': {'exists': False, 'tarball_exists': False},
            'container': {'status': 'none'}
        }

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
        'syntax': './fabrinetes run --config-file <config-file> [--rm] [--x11] [--usb] [--ask] [--verbose]',
        'description': 'Run a Docker container with the specified configuration (container name auto-generated from config path)',
        'arguments': [
            ['--config-file', 'Path to the configuration file (REQUIRED)', 'Yes', 'containers/<path>/config.toml'],
            ['--rm', 'Automatically remove container when it exits', 'No', 'optional flag'],
            ['--x11', 'Enable X11 GUI support', 'No', 'optional flag'],
            ['--usb', 'Enable USB device access', 'No', 'optional flag'],
            ['--ask', 'Ask for confirmation before running', 'No', 'optional flag'],
            ['--verbose', 'Show detailed output', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes run --config-file containers/fabrinetes-dev-testing/config.toml',
            './fabrinetes run --config-file containers/fabrinetes-dev-testing/config.toml --rm --x11'
        ]
    }
    show_command_help('run', command_data)


def show_build_help():
    """Show help for build command"""
    command_data = {
        'syntax': './fabrinetes build --config-file <config-file> --buildbase',
        'description': 'Generate Docker build command for base image only',
        'arguments': [
            ['--config-file', 'Path to config.toml file (REQUIRED)', 'Yes', 'containers/<path>/config.toml'],
            ['--buildbase', 'Build base image from Dockerfile (REQUIRED)', 'Yes', 'required flag'],
        ],
        'examples': [
            './fabrinetes build --config-file containers/fabrinetes-dev-testing/config.toml --buildbase',
        ],
        'note': 'The build command is now dedicated to building base images only. For main images, use the future \'install\' command (not implemented yet).'
    }
    show_command_help('build', command_data)

def show_commit_help():
    """Show help for commit command"""
    command_data = {
        'syntax': './fabrinetes commit --config-file <config-file> [--tag <tag>] [--message <message>]',
        'description': 'Generate Docker commit command to stdout without executing it',
        'arguments': [
            ['--config-file', 'Path to config.toml file (REQUIRED)', 'Yes', 'containers/<path>/config.toml'],
            ['--tag', 'Tag for the new image (default: from config)', 'No', 'any tag name'],
            ['--message', 'Commit message (optional)', 'No', 'any message']
        ],
        'examples': [
            './fabrinetes commit --config-file containers/fabrinetes-dev-testing/config.toml',
            './fabrinetes commit --config-file containers/fabrinetes-dev-testing/config.toml --tag v1.0 --message "Added new features"'
        ]
    }
    show_command_help('commit', command_data)


def show_clean_help():
    """Show help for clean command"""
    command_data = {
        'syntax': './fabrinetes clean --config-file <config-file> [options]',
        'description': 'Comprehensive clean command for base images, containers, and images',
        'arguments': [
            ['--config-file', 'Path to config.toml file (REQUIRED)', 'Yes', 'containers/<path>/config.toml'],
            ['--base-image', 'Clean base image (remove from Docker and tarball)', 'No', 'optional flag'],
            ['--image', 'Clean main image (remove from Docker and tarball)', 'No', 'optional flag'],
            ['--container', 'Clean container (kill and remove)', 'No', 'optional flag'],
            ['--all', 'Clean everything (base image, image, container)', 'No', 'optional flag'],
            ['--dangling', 'Remove dangling images', 'No', 'optional flag'],
        ],
        'examples': [
            './fabrinetes clean --config-file containers/fabrinetes-dev-testing/config.toml --all',
            './fabrinetes clean --config-file containers/fabrinetes-dev-testing/config.toml --base-image --image',
            './fabrinetes clean --config-file containers/fabrinetes-dev-testing/config.toml --container --dangling',
            './fabrinetes clean --config-file containers/fabrinetes-dev-testing/config.toml --base-image',
            './fabrinetes clean --config-file containers/fabrinetes-dev-testing/config.toml --image --container'
        ]
    }
    show_command_help('clean', command_data)

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
        'syntax': './fabrinetes pkg --container-name <container-name> [--recover|--install]',
        'description': 'Package recovery and installation: extract packages from containers or install from pkg-cache',
        'arguments': [
            ['--container-name', 'Name of the running container to manage', 'Yes', 'From Docker Containers table above'],
            ['--container-id', 'Alternative: Container ID for targeting', 'No', 'Container ID like ffb2b6947fb9'],
            ['--recover', 'Extract packages from container and create pkg-cache', 'No', 'Recovery mode'],
            ['--install', 'Install packages from pkg-cache to container', 'No', 'Installation mode'],
            ['--pkg-cache', 'Path to pkg-cache directory for installation', 'No', 'e.g., containers/ffb2b6947fb9/pkg-cache'],
            ['--offline', 'Use offline mode (install from local .deb files)', 'No', 'Requires --install'],
            ['--online', 'Use online mode (use apt-get install)', 'No', 'Requires --install'],
            ['--package', 'Specific package to install (optional)', 'No', 'If not provided, install all packages']
        ],
        'examples': [
            '# Recovery mode',
            './fabrinetes pkg --container-name fabrinetes-fpga-dev-1 --recover',
            './fabrinetes pkg --container-id ffb2b6947fb9 --recover',
            '',
            '# Offline installation (all packages)',
            './fabrinetes pkg --container-name fabrinetes-dev-testing-latest.run --install --pkg-cache containers/ffb2b6947fb9/pkg-cache --offline',
            '',
            '# Online installation (all packages)',
            './fabrinetes pkg --container-name fabrinetes-dev-testing-latest.run --install --pkg-cache containers/ffb2b6947fb9/pkg-cache --online',
            '',
            '# Install specific package offline',
            './fabrinetes pkg --container-name fabrinetes-dev-testing-latest.run --install --pkg-cache containers/ffb2b6947fb9/pkg-cache --offline --package git',
            '',
            '# Install specific package online',
            './fabrinetes pkg --container-name fabrinetes-dev-testing-latest.run --install --pkg-cache containers/ffb2b6947fb9/pkg-cache --online --package python3-pip'
        ]
    }
    show_command_help('pkg', command_data)

def show_test_help():
    """Show help for test command"""
    command_data = {
        'syntax': './fabrinetes test --command <command> [--test-number <number>]',
        'description': 'Test commands using comprehensive test vectors with fabrinetes-dev-testing container',
        'arguments': [
            ['--command', 'Test command to run', 'Yes', 'run, build, clean, kill, commit, pkg, all'],
            ['--test-number', 'Run specific test by number (1-based)', 'No', '1, 2, 3, etc.']
        ],
        'examples': [
            './fabrinetes test --command run',
            './fabrinetes test --command run --test-number 5',
            './fabrinetes test --command build', 
            './fabrinetes test --command clean',
            './fabrinetes test --command kill',
            './fabrinetes test --command commit',
            './fabrinetes test --command pkg',
            './fabrinetes test --command all'
        ]
    }
    show_command_help('test', command_data)

def show_restore_help():
    """Show help for restore command"""
    command_data = {
        'syntax': './fabrinetes restore --config-file <config-file> [--base-image|--image]',
        'description': 'Generate Docker load command to restore images from tar.gz files',
        'arguments': [
            '--config-file <config-file> (REQUIRED) - Path to config file',
            '--base-image - Restore base image from tar.gz',
            '--image - Restore main image from tar.gz'
        ],
        'examples': [
            './fabrinetes restore --config-file containers/my-container/config.toml --base-image',
            './fabrinetes restore --config-file containers/my-container/config.toml --image'
        ]
    }
    show_command_help('restore', command_data)

def show_exec_help():
    """Show help for exec command"""
    command_data = {
        'syntax': './fabrinetes exec --config-file <config-file> [--exec-cmd <command>]',
        'description': 'Generate Docker exec command for running container with proper user context',
        'arguments': [
            '--config-file <config-file> (REQUIRED) - Path to config file',
            '--exec-cmd <command> (OPTIONAL) - Command to execute inside container'
        ],
        'examples': [
            './fabrinetes exec --config-file containers/my-container/config.toml | bash',
            './fabrinetes exec --config-file containers/my-container/config.toml --exec-cmd "hdlforge test" | bash',
            './fabrinetes exec --config-file containers/my-container/config.toml --exec-cmd "cd /home/user/repo && ls -la" | bash'
        ]
    }
    show_command_help('exec', command_data)


# Global help function for no arguments
def show_config_status(config_file):
    """Show status for a specific config file"""
    print("Config File Status")
    print("=" * 60)
    print(f"Config File: {config_file}")
    print()
    
    try:
        # Get status for the specific config file
        status = get_config_status(config_file)
        
        if 'error' in status:
            print(f"❌ Error loading config file: {status['error']}")
            return
        
        # Display status information
        print("Status:")
        print("-" * 20)
        
        # Base image status
        base_status = "✅" if status['base_image']['exists'] else "❌"
        base_tarball_status = "✅" if status['base_image']['tarball_exists'] else "❌"
        print(f"Base Image:    {base_status} Docker  {base_tarball_status} Tarball")
        
        # Main image status
        main_status = "✅" if status['main_image']['exists'] else "❌"
        main_tarball_status = "✅" if status['main_image']['tarball_exists'] else "❌"
        print(f"Main Image:    {main_status} Docker  {main_tarball_status} Tarball")
        
        # Container status
        container_status = status['container']['status']
        if container_status == "running":
            print(f"Container:     🟢 Running")
        elif container_status == "stopped":
            print(f"Container:     🟡 Stopped")
        else:
            print(f"Container:     🔴 None")
        
        print()
        
        # Show available commands for this config
        print("Available Commands for this Config:")
        print("-" * 40)
        print("1. ./fabrinetes run --config-file " + config_file)
        print("2. ./fabrinetes build --config-file " + config_file + " [--base-image]")
        print("3. ./fabrinetes restore --config-file " + config_file + " [--base-image|--image]")
        print()
        
    except Exception as e:
        print(f"❌ Error processing config file: {e}")

def show_global_help():
    """Show global help when no arguments are provided"""
    print("Fabrinetes - Docker Container Management Tool")
    print("=" * 60)
    
    print("\nAvailable Commands:")
    print("-" * 30)
    
    # Get running containers for dynamic display
    running_containers = get_running_containers()
    container_values = ', '.join(running_containers) if running_containers else 'No running containers found'
    
    commands = [
        {
            'command': './fabrinetes build',
            'args': '--config-file <config-file> [--base-image]',
            'description': 'Generate Docker image from config file',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes run',
            'args': '--config-file <config-file> [--rm] [--x11] [--usb] [--ask] [--verbose]',
            'description': 'Run container with specified config',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes exec',
            'args': '--config-file <config-file> [--exec-cmd <command>]',
            'description': 'Execute commands in running container with proper user context',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes commit',
            'args': '--config-file <config-file> [--tag <tag>] [--message <message>]',
            'description': 'Generate Docker commit command to stdout without executing it',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes kill',
            'args': '--config-file <config-file> [container-name]',
            'description': 'Stop and remove container',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes pkg',
            'args': '--config-file <config-file> --container-name [container-name]',
            'description': 'Package management: generate package file with versions and download .deb files',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes restore',
            'args': '--config-file <config-file> [--base-image|--image]',
            'description': 'Restore Docker image from tarball',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes status',
            'args': '--config-file <config-file>',
            'description': 'Show config file status and available commands',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        }
    ]
    
    for i, cmd in enumerate(commands, 1):
        print(f"\n{i}. Command: {cmd['command']}")
        print(f"   Arguments: {cmd['args']}")
        print(f"   Description: {cmd['description']}")
        print(f"   Allowed Values: {cmd['allowed_values']}")
    
    print("\n\nExamples:")
    print("-" * 20)
    
    # Compressed examples using templates
    example_templates = [
        "./fabrinetes --config-file <config> [--cmd <command>]",
        "./fabrinetes build --config-file <config> --buildbase",
        "./fabrinetes run --config-file <config> [--rm|--x11|--usb|--ask|--verbose]",
        "./fabrinetes exec --config-file <config> [--exec-cmd <command>]",
        "./fabrinetes commit --config-file <config> [--tag <tag>] [--message <message>]",
        "./fabrinetes restore --config-file <config> [--base-image|--image]",
        "./fabrinetes status --config-file <config>",
        "./fabrinetes pkg --config-file <config> --container-name <name>"
    ]
    
    for i, template in enumerate(example_templates, 1):
        print(f"{i}. {template}")
    
    # Note: All commands now require --config-file parameter
    print("\n\nNote:")
    print("-" * 20)
    print("All commands now require --config-file parameter.")
    print("Use --config-file to specify which config file to use.")
    print("")
    print("Example config file locations:")
    print("  containers/my-project/config.toml")
    print("  /path/to/your/config.toml")

@task
def help(ctx, config_file=None):
    """Show global help with pretty table of available repositories or status for specific config file"""
    if config_file:
        show_config_status(config_file)
    else:
        show_global_help()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--config-file" and len(sys.argv) > 2:
        config_file = sys.argv[2]
        show_config_status(config_file)
    else:
        show_global_help()