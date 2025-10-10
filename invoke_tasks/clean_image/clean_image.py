#!/usr/bin/env python3

import os
import glob
from invoke import task

@task
def clean_image(ctx, image=None):
    """
    Clean up all containers and images for a specific base image
    
    Args:
        image: Base image name (e.g., "fabrinetes-skeleton:latest")
    """
    from tasks import show_command_help, COMMAND_HELP
    
    # Check for missing required arguments
    if not image:
        show_command_help('clean-image', COMMAND_HELP['clean-image'])
        return
    
    print(f"🧹 Cleaning all containers and images for base image: {image}")
    print("=" * 60)
    
    # Find all containers using this image
    print("🔍 Finding containers using this image...")
    result = ctx.run(f"docker ps -a --filter ancestor={image} --format '{{{{.Names}}}}'", hide=True)
    containers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    
    if containers:
        print(f"📦 Found {len(containers)} containers using image '{image}':")
        for container in containers:
            print(f"  - {container}")
        
        # Stop and remove all containers
        print("\n🛑 Stopping and removing containers...")
        for container in containers:
            print(f"  Stopping {container}...")
            ctx.run(f"docker stop {container}", hide=True, warn=True)
            print(f"  Removing {container}...")
            ctx.run(f"docker rm {container}", hide=True, warn=True)
        print("✅ All containers removed")
    else:
        print("✅ No containers found using this image")
    
    # Find and remove all images with this base image name
    print(f"\n🔍 Finding images based on '{image}'...")
    
    # Extract base image name (without tag)
    base_image_name = image.split(':')[0] if ':' in image else image
    
    # Find all images that start with the base image name
    result = ctx.run(f"docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}}' | grep '^{base_image_name}'", hide=True, warn=True)
    images = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    
    if images:
        print(f"📦 Found {len(images)} images based on '{base_image_name}':")
        for img in images:
            print(f"  - {img}")
        
        # Remove all images
        print("\n🗑️ Removing images...")
        for img in images:
            print(f"  Removing {img}...")
            ctx.run(f"docker rmi {img}", hide=True, warn=True)
        print("✅ All images removed")
    else:
        print("✅ No images found based on this name")
    
    # Clean up any dangling images
    print("\n🧽 Cleaning up dangling images...")
    ctx.run("docker image prune -f", hide=True, warn=True)
    
    print(f"\n✅ Cleanup completed for base image: {image}")

