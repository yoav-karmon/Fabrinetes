#!/usr/bin/env python3

import os
import datetime
import pathlib
import toml
from invoke import task
from .helpers import setup_x11_support, resolve_mounts, printlocals
from helper_functions.config.name_generator import get_image_name, get_run_name
from helper_functions.image_management import ensure_image_available, convert_to_docker_format

@task
def run(ctx, file=None, rm=False, verbose=False, x11=True, usb=False, ask=True):
    """Run a Docker container with the specified configuration"""
    from tasks import show_command_help, COMMAND_HELP
    
    # Check for missing required arguments
    if not file:
        show_command_help('run', COMMAND_HELP['run'])
        return
    
    # Load configuration
    try:
        config = toml.load(file)
    except Exception as e:
        print(f"Error loading config file {file}: {e}")
        return
    
    # Find the container configuration
    container_config = None
    if 'config' in config:
        container_config = config['config']
    
    if not container_config:
        print(f"Error: No [config] section found in config file")
        return
    
    # Stage 1: Find the image name needed to run
    image_info = get_image_name(file)
    image_name = image_info['full']
    print(f"Stage 1: Image needed: {image_name}")
    
    # Stage 2: Check if image exists, try to restore if not
    print(f"Stage 2: Checking image availability...")
    if not ensure_image_available(ctx, image_name):
        import sys
        sys.exit(1)  # Exit with error code when image is not available
    
    # Stage 3: Check if container is running, run if not
    print(f"Stage 3: Checking container status...")
    
    # Generate container name
    container_name = get_run_name(file)
    if not container_name:
        return
    command = container_config.get('command', 'bash')
    mounts = container_config.get('mounts', [])
    environment = container_config.get('environment', {})
    X11_path = container_config.get('X11_path', None)
    
    # Check if container is already running
    existing_container = ctx.run(f"docker ps -q -f name=^{container_name}$", hide=True, warn=True)
    if existing_container.stdout.strip():
        print(f"Error: Container '{container_name}' is already running")
        print(f"Use './fabrinetes exec --container-name {container_name} --command bash' to access it")
        return
    
    # Check if container exists but is stopped
    stopped_container = ctx.run(f"docker ps -aq -f name=^{container_name}$", hide=True, warn=True)
    if stopped_container.stdout.strip():
        print(f"Container '{container_name}' exists but is stopped. Starting it...")
        ctx.run(f"docker start {container_name}", hide=True)
        print(f"✅ Container '{container_name}' started successfully")
        return
    
    # Build docker command
    cmd_parts = ["docker", "run", "-dit"]
    
    if rm:
        cmd_parts.append("--rm")
    
    # Set up X11 support using helper function
    cmd_parts = setup_x11_support(x11, X11_path, cmd_parts)
    
    if usb:
        cmd_parts.append("-v /dev/bus/usb:/dev/bus/usb")
    
    # Add environment variables
    for key, value in environment.items():
        cmd_parts.append(f"-e {key}={value}")
    
    # Resolve and add mounts
    relative_path = pathlib.Path(file).parent
    resolved_mounts = resolve_mounts(mounts, relative_path)
    
    for host_path, container_path in resolved_mounts:
        cmd_parts.append(f"-v {host_path}:{container_path}")
    
    # Add init_env mount if specified
    if 'init_env' in container_config:
        init_env_mount = container_config['init_env']
        if ':' in init_env_mount:
            host_path, container_path = init_env_mount.split(':', 1)
            # Expand environment variables in host path
            host_path = os.path.expandvars(host_path)
            # Convert to absolute path if relative
            if not os.path.isabs(host_path):
                host_path = str(relative_path / host_path)
            # Ensure the path is absolute
            host_path = os.path.abspath(host_path)
            cmd_parts.append(f"-v {host_path}:{container_path}")
    
    # Add container name and image
    cmd_parts.extend(["--name", container_name, convert_to_docker_format(image_name)])
    
    # Add command
    cmd_parts.append(command)
    
    # Print configuration if verbose
    if verbose:
        printlocals(locals(), verbose=True)
    
    # Ask for confirmation if requested
    if ask:
        print(f"About to run container '{container_name}' with image '{image_name}'")
        print(f"Command: {' '.join(cmd_parts)}")
        response = input("Continue? (y/N): ")
        if response.lower() != 'y':
            print("Aborted")
            return
    
    # Run the container
    print(f"Starting container: {container_name}")
    ctx.run(" ".join(cmd_parts), pty=True)
    
    print(f"✅ Container '{container_name}' started successfully")
    print(f"📁 Config file: {file}")
    print(f"🔗 Mounts: {len(resolved_mounts)} configured")
    print(f"💡 To exec into container: ./fabrinetes exec --container-name {container_name} --command 'bash'")
    print(f"💡 To open shell: ./fabrinetes shell --container-name {container_name}")
