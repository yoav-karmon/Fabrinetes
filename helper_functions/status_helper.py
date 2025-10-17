#!/usr/bin/env python3

"""
Status helper module for Fabrinetes - Comprehensive container status information.

This module provides functions to collect and display comprehensive status information
about containers, images, tarballs, and file system components.
"""

import os
import docker
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from .status_utils import format_file_size, translate_docker_error

@dataclass
class StatusInfo:
    """Dataclass containing status information for a single component"""
    name: str
    toml_key: Optional[str] = None  # TOML key path for this item
    exists: bool = False
    status: str = ""  # "exists", "not found", "running", "stopped", etc.
    size: Optional[str] = None
    modified: Optional[str] = None
    details: Optional[str] = None

@dataclass
class StatusCollector:
    """Single source of truth for status collection - consolidates all status logic"""
    container_info: Any  # ContainerInfo type
    docker_client: Optional[docker.DockerClient] = field(default=None, init=False)
    
    def __post_init__(self):
        """Initialize cached resources"""
        try:
            self.docker_client = docker.from_env()
        except Exception:
            self.docker_client = None
    
    def collect_file_status(self, file_path: str, name: str, toml_key: str = None) -> StatusInfo:
        """Get status information for a file"""
        if not file_path:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not specified")
        
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            size = format_file_size(stat.st_size)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            return StatusInfo(
                name=name,
                toml_key=toml_key,
                exists=True,
                status="exists",
                size=size,
                modified=modified
            )
        else:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not found")
    
    def collect_directory_status(self, dir_path: str, name: str, toml_key: str = None) -> StatusInfo:
        """Get status information for a directory"""
        if not dir_path:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not specified")
        
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            # Check if writable
            writable = os.access(dir_path, os.W_OK)
            status = "exists, writable" if writable else "exists, read-only"
            return StatusInfo(name=name, toml_key=toml_key, exists=True, status=status)
        else:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not found")
    
    def collect_docker_image_status(self, image_name: str, name: str, toml_key: str = None) -> StatusInfo:
        """Get status information for a Docker image"""
        if not image_name:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not specified")
        
        if not self.docker_client:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="Docker daemon not running - start Docker service")
        
        try:
            image = self.docker_client.images.get(image_name)
            size = format_file_size(image.attrs['Size'])
            created = datetime.fromisoformat(image.attrs['Created'].replace('Z', '+00:00'))
            created_str = created.strftime("%Y-%m-%d %H:%M:%S")
            return StatusInfo(
                name=name,
                toml_key=toml_key,
                exists=True,
                status="exists",
                size=size,
                modified=created_str
            )
        except docker.errors.ImageNotFound:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not found")
        except Exception as e:
            friendly_error = translate_docker_error(e)
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status=friendly_error)
    
    def collect_docker_container_status(self, container_name: str, name: str, toml_key: str = None) -> StatusInfo:
        """Get status information for a Docker container"""
        if not container_name:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not specified")
        
        if not self.docker_client:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="Docker daemon not running - start Docker service")
        
        try:
            container = self.docker_client.containers.get(container_name)
            status = container.status
            created = datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00'))
            created_str = created.strftime("%Y-%m-%d %H:%M:%S")
            return StatusInfo(
                name=name,
                toml_key=toml_key,
                exists=True,
                status=status,
                modified=created_str
            )
        except docker.errors.NotFound:
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status="not found")
        except Exception as e:
            friendly_error = translate_docker_error(e)
            return StatusInfo(name=name, toml_key=toml_key, exists=False, status=friendly_error)
    
    def collect_comprehensive_status(self) -> 'ContainerStatus':
        """Collect comprehensive status information for all container components - single source of truth"""
        
        # Config file status
        config_file = self.collect_file_status(self.container_info.config_file_resolved, "Config File", "config")
        
        # Image status
        base_image = self.collect_docker_image_status(self.container_info.base_image_docker, "Base Image", "config.base_image")
        main_image = self.collect_docker_image_status(self.container_info.image_docker, "Main Image", "config.image")
        
        # Tarball status
        base_tarball = self.collect_file_status(self.container_info.base_image_tarball_resolved, "Base Tarball", "config.base_image.tarball_path")
        main_tarball = self.collect_file_status(self.container_info.image_tarball_resolved, "Main Tarball", "config.image.tarball_path")
        
        # Container status
        container = self.collect_docker_container_status(self.container_info.run_name, "Container", "config.container.name")
        
        # Directory status (these are derived, not directly in TOML)
        working_directory = self.collect_directory_status(self.container_info.working_directory, "Working Directory")
        
        return ContainerStatus(
            config_file=config_file,
            base_image=base_image,
            main_image=main_image,
            base_tarball=base_tarball,
            main_tarball=main_tarball,
            container=container,
            working_directory=working_directory
        )

@dataclass
class ContainerStatus:
    """Comprehensive container status information"""
    # Config status
    config_file: StatusInfo
    
    # Image status
    base_image: StatusInfo
    main_image: StatusInfo
    
    # Tarball status
    base_tarball: StatusInfo
    main_tarball: StatusInfo
    
    # Container status
    container: StatusInfo
    
    # Directory status
    working_directory: StatusInfo

def collect_comprehensive_status(container_info) -> ContainerStatus:
    """Collect comprehensive status information for all container components"""
    collector = StatusCollector(container_info)
    return collector.collect_comprehensive_status()

def format_status_output(status: ContainerStatus) -> str:
    """Format comprehensive status information for display"""
    output = []
    
    # Config Status
    output.append("Config Status:")
    config = status.config_file
    status_icon = "✅" if config.exists else "❌"
    label = f"{config.name} ({config.toml_key})" if config.toml_key else config.name
    output.append(f"  {label}: {status_icon} ({config.status})")
    if config.size:
        output.append(f"    Size: {config.size}")
    if config.modified:
        output.append(f"    Modified: {config.modified}")
    output.append("")
    
    # Image Status
    output.append("Image Status:")
    for image in [status.base_image, status.main_image]:
        status_icon = "✅" if image.exists else "❌"
        label = f"{image.name} ({image.toml_key})" if image.toml_key else image.name
        output.append(f"  {label}: {status_icon} ({image.status})")
        if image.size:
            output.append(f"    Size: {image.size}")
        if image.modified:
            output.append(f"    Created: {image.modified}")
    output.append("")
    
    # Tarball Status
    output.append("Tarball Status:")
    for tarball in [status.base_tarball, status.main_tarball]:
        status_icon = "✅" if tarball.exists else "❌"
        label = f"{tarball.name} ({tarball.toml_key})" if tarball.toml_key else tarball.name
        output.append(f"  {label}: {status_icon} ({tarball.status})")
        if tarball.size:
            output.append(f"    Size: {tarball.size}")
        if tarball.modified:
            output.append(f"    Modified: {tarball.modified}")
    output.append("")
    
    # Container Status
    output.append("Container Status:")
    container = status.container
    status_icon = "✅" if container.exists else "❌"
    label = f"{container.name} ({container.toml_key})" if container.toml_key else container.name
    output.append(f"  {label}: {status_icon} ({container.status})")
    if container.modified:
        output.append(f"    Created: {container.modified}")
    output.append("")
    
    # Directory Status
    output.append("Directory Status:")
    directory = status.working_directory
    status_icon = "✅" if directory.exists else "❌"
    label = f"{directory.name} ({directory.toml_key})" if directory.toml_key else directory.name
    output.append(f"  {label}: {status_icon} ({directory.status})")
    output.append("")
    
    return "\n".join(output)
