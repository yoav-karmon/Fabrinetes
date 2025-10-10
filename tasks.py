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
from helper_functions.name_generator import get_container_info

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
    import subprocess
    
    print(f"Importing image from {tar_path}...")
    
    try:
        # Use subprocess to handle the pipe properly
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

@task(help={
    'config_file': 'Path to config.toml file',
    'base_image': 'Clean base image (remove from Docker and tarball)',
    'image': 'Clean main image (remove from Docker and tarball)',
    'container': 'Clean container (kill and remove)',
    'all': 'Clean everything (base image, image, container)',
    'dangling': 'Remove dangling images',
    'help': 'Show help information'
})
def clean(ctx, config_file=None, base_image=False, image=False, container=False, all=False, dangling=False, help=False):
    """Comprehensive clean command for base images, containers, and images"""
    
    # Check for help flag or missing required arguments
    if help:
        show_clean_help()
        return
    
    if not config_file:
        print("❌ Error: Config file is required")
        show_clean_help()
        return
    
    # Check if config file exists
    if not os.path.exists(config_file):
        print(f"❌ Error: Config file not found at {config_file}")
        return
    
    # Get container info using dataclass
    container_info = get_container_info(config_file)
    
    # If no specific targets specified, show help
    if not any([base_image, image, container, all, dangling]):
        print("❌ Error: No cleaning targets specified")
        show_clean_help()
        return
    
    print(f"🧹 Starting clean operation for: {container_info.image_name}")
    
    # Clean dangling images first (always do this)
    if dangling or all:
        clean_dangling_images(ctx)
    
    # Clean base image
    if base_image or all:
        clean_base_image(ctx, container_info)
    
    # Clean main image
    if image or all:
        clean_main_image(ctx, container_info)
    
    # Clean container
    if container or all:
        clean_container(ctx, container_info)
    
    print(f"✅ Clean operation completed for: {container_info.image_name}")

def clean_dangling_images(ctx):
    """Remove dangling Docker images"""
    print("🧹 Cleaning dangling images...")
    
    # Remove dangling images
    result = ctx.run("docker image prune -f", hide=True, warn=True)
    if result.ok:
        print("✅ Dangling images cleaned")
    else:
        print(f"⚠️ Warning: Failed to clean dangling images: {result.stderr}")

def clean_base_image(ctx, container_info):
    """Clean base image (remove from Docker and tarball)"""
    base_image_name = container_info.base_image_docker
    base_tarball_path = container_info.tarball_directory + "/" + container_info.base_image_tarball
    
    print(f"🧹 Cleaning base image: {base_image_name}")
    
    # Remove from Docker
    result = ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
    if result.ok:
        print(f"✅ Base image removed from Docker: {base_image_name}")
    else:
        print(f"⚠️ Warning: Base image not found in Docker: {base_image_name}")
    
    # Remove tarball
    if os.path.exists(base_tarball_path):
        os.remove(base_tarball_path)
        print(f"✅ Base image tarball removed: {base_tarball_path}")
    else:
        print(f"ℹ️ Base image tarball not found: {base_tarball_path}")

def clean_main_image(ctx, container_info):
    """Clean main image (remove from Docker and tarball)"""
    image_name = container_info.image_docker
    tarball_path = container_info.tarball_path
    
    print(f"🧹 Cleaning main image: {image_name}")
    
    # Remove from Docker
    result = ctx.run(f"docker rmi -f {image_name}", hide=True, warn=True)
    if result.ok:
        print(f"✅ Main image removed from Docker: {image_name}")
    else:
        print(f"⚠️ Warning: Main image not found in Docker: {image_name}")
    
    # Remove tarball
    if os.path.exists(tarball_path):
        os.remove(tarball_path)
        print(f"✅ Main image tarball removed: {tarball_path}")
    else:
        print(f"ℹ️ Main image tarball not found: {tarball_path}")

def clean_container(ctx, container_info):
    """Clean container (kill and remove)"""
    container_name = container_info.run_name
    
    print(f"🧹 Cleaning container: {container_name}")
    
    # Kill container if running
    result = ctx.run(f"docker kill {container_name}", hide=True, warn=True)
    if result.ok:
        print(f"✅ Container killed: {container_name}")
    else:
        print(f"ℹ️ Container not running: {container_name}")
    
    # Remove container
    result = ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
    if result.ok:
        print(f"✅ Container removed: {container_name}")
    else:
        print(f"ℹ️ Container not found: {container_name}")

def show_clean_help():
    """Show help for clean command"""
    print("""
CLEAN Command Help
==================================================
Syntax: ./fabrinetes clean <config-file> [options]
Description: Comprehensive clean command for base images, containers, and images

Arguments:
------------------------------

1. config-file
   Description: Path to config.toml file
   Required: Yes
   Allowed Values: containers/<path>/config.toml

2. --base-image
   Description: Clean base image (remove from Docker and tarball)
   Required: No

3. --image
   Description: Clean main image (remove from Docker and tarball)
   Required: No

4. --container
   Description: Clean container (kill and remove)
   Required: No

5. --all
   Description: Clean everything (base image, image, container)
   Required: No

6. --dangling
   Description: Remove dangling images
   Required: No

Examples:
--------------------

1. ./fabrinetes clean containers/fabrinetes-dev-testing/config.toml --all

2. ./fabrinetes clean containers/fabrinetes-dev-testing/config.toml --base-image --image

3. ./fabrinetes clean containers/fabrinetes-dev-testing/config.toml --container --dangling

4. ./fabrinetes clean containers/fabrinetes-dev-testing/config.toml --base-image

5. ./fabrinetes clean containers/fabrinetes-dev-testing/config.toml --image --container
""")