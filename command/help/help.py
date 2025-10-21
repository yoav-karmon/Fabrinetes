#!/usr/bin/env python3

import os
import glob
import subprocess
from invoke import task
from command.helper_functions.name_generator import get_container_info

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
        
        # Check main image status
        main_image_exists = check_image_exists(container_info.image_docker)
        
        # Check container status
        container_status = check_container_status(container_info.run_name)
        
        return {
            'main_image': {
                'exists': main_image_exists
            },
            'container': {
                'status': container_status
            }
        }
    except Exception as e:
        return {
            'error': str(e),
            'main_image': {'exists': False},
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
        'syntax': './fabrinetes run --config-file <config-file> [--rm] [--usb] [--ask] [--verbose]',
        'description': 'Run a Docker container with the specified configuration (container name auto-generated from config path)',
        'arguments': [
            ['--config-file', 'Path to the configuration file (REQUIRED)', 'Yes', 'containers/<path>/config.toml'],
            ['--rm', 'Automatically remove container when it exits', 'No', 'optional flag'],
            ['--usb', 'Enable USB device access', 'No', 'optional flag'],
            ['--ask', 'Ask for confirmation before running', 'No', 'optional flag'],
            ['--verbose', 'Show detailed output', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes run --config-file containers/fabrinetes-dev-testing/config.toml',
            './fabrinetes run --config-file containers/fabrinetes-dev-testing/config.toml --rm'
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

def show_test_help():
    """Show help for test command"""
    command_data = {
        'syntax': './fabrinetes test --command <command> [--test-number <number>]',
        'description': 'Test commands using comprehensive test vectors with fabrinetes-dev-testing container',
        'arguments': [
            ['--command', 'Test command to run', 'Yes', 'run, build, clean, all'],
            ['--test-number', 'Run specific test by number (1-based)', 'No', '1, 2, 3, etc.']
        ],
        'examples': [
            './fabrinetes test --command run',
            './fabrinetes test --command run --test-number 5',
            './fabrinetes test --command build', 
            './fabrinetes test --command clean',
            './fabrinetes test --command all'
        ]
    }
    show_command_help('test', command_data)

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

def show_push_help():
    """Show help for push command"""
    command_data = {
        'syntax': './fabrinetes push --config-file <config-file> --github-username <username> [--registry <registry>]',
        'description': 'Generate Docker push commands for GitHub Container Registry (GHCR)',
        'arguments': [
            ['--config-file', 'Path to config.toml file (REQUIRED)', 'Yes', 'containers/<path>/config.toml'],
            ['--github-username', 'GitHub username for GHCR (REQUIRED)', 'Yes', 'your GitHub username'],
            ['--registry', 'Container registry URL (optional)', 'No', 'ghcr.io (default) or custom registry']
        ],
        'examples': [
            './fabrinetes push --config-file containers/fabrinetes-dev-testing/config.toml --github-username myuser | bash',
            './fabrinetes push --config-file containers/fabrinetes-dev-testing/config.toml --github-username myuser --registry ghcr.io | bash',
            './fabrinetes push --config-file containers/my-container/config.toml --github-username myuser --registry myregistry.com | bash'
        ]
    }
    show_command_help('push', command_data)


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
            print(f"Error loading config file: {status['error']}")
            return
        
        # Display status information
        print("Status:")
        print("-" * 20)
        
        # Main image status
        main_status = "OK" if status['main_image']['exists'] else "MISSING"
        print(f"Main Image:    {main_status} Docker")
        
        # Container status
        container_status = status['container']['status']
        if container_status == "running":
            print(f"Container:     Running")
        elif container_status == "stopped":
            print(f"Container:     Stopped")
        else:
            print(f"Container:     None")
        
        print()
        
        # Show available commands for this config
        print("Available Commands for this Config:")
        print("-" * 40)
        print("1. ./fabrinetes run --config-file " + config_file)
        print("2. ./fabrinetes build --config-file " + config_file + " [--base-image]")
        print("3. ./fabrinetes restore --config-file " + config_file + " [--base-image|--image]")
        print()
        
    except Exception as e:
        print(f"Error processing config file: {e}")

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
            'args': '--config-file <config-file>',
            'description': 'Build image from Dockerfile',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes run',
            'args': '--config-file <config-file> [--rm] [--usb] [--ask] [--verbose]',
            'description': 'Generate Docker run command',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes exec',
            'args': '--config-file <config-file> [--exec-cmd <command>]',
            'description': 'Generate Docker exec command for running container',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes status',
            'args': '--config-file <config-file>',
            'description': 'Show config file status',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes test',
            'args': '--config-file <config-file>',
            'description': 'Run all commands in test mode',
            'allowed_values': 'config-file: containers/<path>/config.toml (REQUIRED)'
        },
        {
            'command': './fabrinetes help',
            'args': '',
            'description': 'Show this help message',
            'allowed_values': 'No arguments required'
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
        "./fabrinetes build --config-file <config>",
        "./fabrinetes run --config-file <config> [--rm|--usb|--ask|--verbose]",
        "./fabrinetes exec --config-file <config> [--exec-cmd <command>]",
        "./fabrinetes status --config-file <config>",
        "./fabrinetes test --config-file <config>"
    ]
    
    for i, template in enumerate(example_templates, 1):
        print(f"{i}. {template}")
    
    # Docker Syntax Reference
    print("\n\nDocker Syntax Reference:")
    print("-" * 30)
    print("Common Docker commands that can be used directly:")
    print("")
    print("1. Docker Commit:")
    print("   docker commit -m \"<message>\" <container_name> <image_name:tag>")
    print("   Example: docker commit -m \"Added new features\" fabrinetes-local-run.run ykarmon/fabrinetes:v1.1")
    print("")
    print("2. Docker Run:")
    print("   docker run -d --name <container_name> <image_name:tag> <command>")
    print("   Example: docker run -d --name my-container ubuntu:latest sleep infinity")
    print("")
    print("3. Docker Exec:")
    print("   docker exec -it <container_name> <command>")
    print("   Example: docker exec -it my-container bash")
    print("")
    print("4. Docker Build:")
    print("   docker build -t <image_name:tag> -f <dockerfile> <context>")
    print("   Example: docker build -t my-image:latest -f Dockerfile .")
    print("")
    
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