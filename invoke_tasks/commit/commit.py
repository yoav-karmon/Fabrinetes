#!/usr/bin/env python3

import os
import re
import time
from invoke import task
from helper_functions.config.name_generator import get_image_name, get_run_name, get_tarball_path, get_tarball_directory
from helper_functions.name_generator import extract_image_info_from_base_image
from helper_functions.image_management import save_image_to_tarball

@task
def commit(ctx, container_name=None, tag=None, message=None):
    """Commit running container to new image"""
    from tasks import show_command_help, COMMAND_HELP
    
    # Check for missing required arguments
    if not container_name:
        show_command_help('commit', COMMAND_HELP['commit'])
        return
    
    # Check if container is running
    try:
        result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
        if not result.stdout.strip():
            print(f"Error: Container '{container_name}' is not running")
            print("Available running containers:")
            ctx.run("docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}'", pty=True)
            return
    except Exception:
        print(f"Error: Could not check container status")
        return
    
    # Extract repository name from container name using name generator
    image_name, container_tag = extract_image_info_from_run_name(container_name)
    if image_name:
        repo_name = image_name
    else:
        # Fallback: use container name as-is
        repo_name = container_name
    
    # Generate tag if not provided
    if not tag:
        tag = container_tag if container_tag else "latest"
    
    # Generate commit message if not provided
    if not message:
        message = f"Committed {container_name} at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Find the config file for this container
    config_file = None
    import glob
    config_files = glob.glob("containers/*/config.toml")
    for config_path in config_files:
        try:
            if get_run_name(config_path) == container_name:
                config_file = config_path
                break
        except Exception:
            continue
    
    if not config_file:
        print(f"Error: Could not find config file for container '{container_name}'")
        return
    
    # Get image name from config
    image_info = get_image_name(config_file)
    commit_image_name = image_info['full']
    
    print(f"Committing container '{container_name}' to base image '{commit_image_name}'...")
    
    try:
        commit_cmd = f"docker commit -m '{message}' {container_name} {commit_image_name}"
        ctx.run(commit_cmd, hide=True)
        print(f"✅ Successfully committed container to {commit_image_name}")
        
        # Save image to tarball for restoration
        if save_image_to_tarball(ctx, commit_image_name, config_file):
            print(f"✅ Image saved for future restoration")
        
        # Export the image to base_images folder
        base_image_name, base_tag = extract_image_info_from_base_image(commit_image_name)
        tarball_path = get_tarball_path(config_file)
        tarball_directory = get_tarball_directory(config_file)
        
        # Create directory if it doesn't exist
        os.makedirs(tarball_directory, exist_ok=True)
        
        # Save image to tarball
        save_cmd = f"docker save {commit_image_name} | gzip > {tarball_path}"
        ctx.run(save_cmd, hide=True)
        print(f"✅ Image exported to {tarball_path}")
        
    except Exception as e:
        print(f"❌ Failed to commit container: {e}")
