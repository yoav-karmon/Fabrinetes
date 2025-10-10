#!/usr/bin/env python3

import os
import toml
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class ContainerInfo:
    """Dataclass containing all container naming and configuration information"""
    # Image information
    image_name: str
    image_tag: str
    image_full: str
    image_docker: str
    image_tarball: str
    
    # Base image information
    base_image_name: str
    base_image_tag: str
    base_image_full: str
    base_image_docker: str
    base_image_tarball: str
    
    # Container information
    container_name: str
    run_name: str
    
    # Paths
    tarball_path: str
    tarball_directory: str
    
    # Configuration
    config_file: str
    mounts: List[str]
    x11_path: str

def get_container_info(config_file: str) -> ContainerInfo:
    """
    Single function that returns all container naming and configuration information.
    
    Args:
        config_file: Path to the TOML configuration file
        
    Returns:
        ContainerInfo dataclass with all naming and configuration data
    """
    config = toml.load(config_file)
    container_config = config['config']
    
    # Image information
    image_name = container_config['image']['name']
    image_tag = container_config['image']['tag']
    image_full = f"{image_name}-{image_tag}"
    image_docker = f"{image_name}:{image_tag}"
    image_tarball = container_config['image']['tarball_name']
    
    # Base image information
    base_image_name = container_config['base_image']['name']
    base_image_tag = container_config['base_image']['tag']
    base_image_full = f"{base_image_name}-{base_image_tag}"
    base_image_docker = f"{base_image_name}:{base_image_tag}"
    base_image_tarball = container_config['base_image']['tarball_name']
    
    # Container information
    container_name = container_config['container']['name']
    run_name = f"{image_full}.run"
    
    # Paths
    tarball_directory = f"containers/{image_name}"
    tarball_path = f"{tarball_directory}/{image_tarball}"
    
    return ContainerInfo(
        # Image
        image_name=image_name,
        image_tag=image_tag,
        image_full=image_full,
        image_docker=image_docker,
        image_tarball=image_tarball,
        
        # Base image
        base_image_name=base_image_name,
        base_image_tag=base_image_tag,
        base_image_full=base_image_full,
        base_image_docker=base_image_docker,
        base_image_tarball=base_image_tarball,
        
        # Container
        container_name=container_name,
        run_name=run_name,
        
        # Paths
        tarball_path=tarball_path,
        tarball_directory=tarball_directory,
        
        # Configuration
        config_file=config_file,
        mounts=container_config['mounts'],
        x11_path=container_config['X11_path']
    )