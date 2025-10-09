#!/usr/bin/env python3

# Import from the new config module for single source of truth
from helper_functions.config.name_generator import (
    get_image_name,
    get_container_name,
    get_run_name,
    get_tarball_path,
    get_tarball_directory,
    get_config_info
)

# Legacy functions for backward compatibility
def generate_image_name_from_base_image(base_image: str) -> str:
    """
    Generate the exact image name from base_image.
    Returns the base_image as-is (e.g., "fabrinetes-skeleton:latest")
    """
    return base_image

def extract_image_info_from_base_image(base_image: str) -> tuple[str, str]:
    """
    Extract image name and tag from base_image.
    Returns (image_name, tag)
    """
    if ':' in base_image:
        image_name, tag = base_image.split(':', 1)
    else:
        image_name = base_image
        tag = "latest"
    return image_name, tag

def generate_run_name_from_config(config_file):
    """Generate run name from config file using base_image"""
    return get_run_name(config_file)

def generate_run_name_from_base_image(base_image, tag="latest"):
    """Generate run name directly from base image and tag"""
    # Extract image name (remove tag if present)
    if ':' in base_image:
        image_name = base_image.split(':')[0]
    else:
        image_name = base_image
        
    # Generate run name: <image>.<tag>.run
    run_name = f"{image_name}.{tag}.run"
    return run_name

def extract_image_info_from_run_name(run_name):
    """Extract image name and tag from run name"""
    if not run_name.endswith('.run'):
        return None, None
        
    # Remove .run suffix
    name_without_run = run_name[:-4]
    
    # Split by last dot to separate image and tag
    parts = name_without_run.rsplit('.', 1)
    if len(parts) == 2:
        image_name, tag = parts
        return image_name, tag
    else:
        return name_without_run, "latest"