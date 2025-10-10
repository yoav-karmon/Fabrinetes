#!/usr/bin/env python3

import os
import re
import time
from invoke import task
from helper_functions.name_generator import get_container_info
from helper_functions.image_management import save_image_to_tarball

@task
def commit(ctx, container_name=None, tag=None, message=None, help=False):
    """Commit running container to new image"""
    from invoke_tasks.help.help import show_commit_help
    
    # Check for help flag or missing required arguments
    if help or not container_name:
        show_commit_help()
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
            container_info = get_container_info(config_path)
            if container_info.run_name == container_name:
                config_file = config_path
                break
        except Exception:
            continue
    
    if not config_file:
        print(f"Error: Could not find config file for container '{container_name}'")
        return
    
    # Get image name from config
    container_info = get_container_info(config_file)
    commit_image_name = container_info.image_full
    
    print(f"Committing container '{container_name}' to base image '{commit_image_name}'...")
    
    try:
        commit_cmd = f"docker commit -m '{message}' {container_name} {commit_image_name}"
        ctx.run(commit_cmd, hide=True)
        print(f"✅ Successfully committed container to {commit_image_name}")
        
        # Save image to tarball for restoration
        if save_image_to_tarball(ctx, commit_image_name, config_file):
            print(f"✅ Image saved for future restoration")
        
        # Export the image to base_images folder
        tarball_path = container_info.tarball_path
        tarball_directory = container_info.tarball_directory
        
        # Create directory if it doesn't exist
        os.makedirs(tarball_directory, exist_ok=True)
        
        # Save image to tarball
        save_cmd = f"docker save {commit_image_name} | gzip > {tarball_path}"
        ctx.run(save_cmd, hide=True)
        print(f"✅ Image exported to {tarball_path}")
        
    except Exception as e:
        print(f"❌ Failed to commit container: {e}")
