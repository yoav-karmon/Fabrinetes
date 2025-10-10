#!/usr/bin/env python3

import os
import glob
from invoke import Context
from helper_functions.name_generator import get_container_info

def convert_to_docker_format(image_name: str) -> str:
    """Convert image name to Docker format (name:tag)"""
    # If it already has a colon, it's already in Docker format
    if ':' in image_name:
        return image_name
    
    # If it ends with '-latest', convert to ':latest'
    if image_name.endswith('-latest'):
        return f"{image_name}:latest"
    
    # If it has a dot and doesn't end with .tar.gz, convert dot to colon
    if '.' in image_name and not image_name.endswith('.tar.gz'):
        parts = image_name.rsplit('.', 1)
        if len(parts) == 2:
            return f"{parts[0]}:{parts[1]}"
    
    # Default: add :latest tag
    return f"{image_name}:latest"

def convert_from_docker_format(image_name: str) -> str:
    if ':' in image_name:
        return image_name.replace(':', '.')
    return image_name

def check_image_exists(ctx: Context, image_name: str) -> bool:
    docker_image_name = convert_to_docker_format(image_name)
    result = ctx.run(f"docker images {docker_image_name} --format '{{.Repository}}'", hide=True, warn=True)
    return bool(result.stdout.strip())

def find_image_tarball(image_name: str) -> str:
    # Convert image name to tarball format
    if ':' in image_name:
        name, tag = image_name.split(':', 1)
        tarball_filename = f"{name}-{tag}.tar.gz"
    else:
        tarball_filename = f"{image_name}-latest.tar.gz"
    
    # Look in containers/*/ directories
    containers_dir = "containers"
    if os.path.exists(containers_dir):
        pattern = f"{containers_dir}/**/{tarball_filename}"
        tarballs = glob.glob(pattern, recursive=True)
        if tarballs:
            return tarballs[0]
    
    return None

def restore_image_from_tarball(ctx: Context, image_name: str) -> bool:
    tarball_path = find_image_tarball(image_name)
    if not tarball_path:
        return False
    
    print(f"Found tarball: {tarball_path}")
    docker_image_name = convert_to_docker_format(image_name)
    print(f"Restoring image: {docker_image_name}")
    
    result = ctx.run(f"docker load -i {tarball_path}", hide=True)
    if result.ok:
        print(f"Successfully restored image: {docker_image_name}")
        return True
    else:
        print(f"Failed to restore image: {result.stderr}")
        return False

def ensure_image_available(ctx: Context, image_name: str) -> bool:
    if check_image_exists(ctx, image_name):
        docker_image_name = convert_to_docker_format(image_name)
        print(f"Image '{docker_image_name}' found locally")
        return True
    
    docker_image_name = convert_to_docker_format(image_name)
    print(f"Image '{docker_image_name}' not found locally, attempting to restore...")
    if restore_image_from_tarball(ctx, image_name):
        return True
    
    print(f"Image '{docker_image_name}' not available and restore failed")
    print(f"Please rebuild the image: ./fabrinetes gen-image <repository>")
    return False

def save_image_to_tarball(ctx: Context, image_name: str, config_file: str = None, tarball_image_name: str = None) -> bool:
    docker_image_name = convert_to_docker_format(image_name)
    
    if config_file:
        config_dir = os.path.dirname(config_file)
        tarball_directory = config_dir
        os.makedirs(tarball_directory, exist_ok=True)
        
        # Use custom tarball image name if provided, otherwise use the image name from config
        if tarball_image_name:
            tarball_name, tarball_tag = tarball_image_name.split(':', 1)
            tarball_filename = f"{tarball_name}-{tarball_tag}.tar.gz"
        else:
            # Get tarball filename from config
            container_info = get_container_info(config_file)
            tarball_filename = container_info.image_tarball
        
        tarball_path = os.path.join(tarball_directory, tarball_filename)
    else:
        if ':' in docker_image_name:
            image_base, tag = docker_image_name.split(':', 1)
        else:
            image_base, tag = docker_image_name, "latest"
        
        base_images_dir = f"base_images/{image_base}"
        os.makedirs(base_images_dir, exist_ok=True)
        
        tarball_filename = f"{image_base}-{tag}.tar.gz"
        tarball_path = os.path.join(base_images_dir, tarball_filename)
    
    print(f"Saving image '{docker_image_name}' to {tarball_path}")
    
    result = ctx.run(f"docker save {docker_image_name} | gzip > {tarball_path}", hide=True)
    if result.ok:
        print(f"Image saved successfully: {tarball_path}")
        return True
    else:
        print(f"Failed to save image: {result.stderr}")
        return False