#!/usr/bin/env python3

import os
import sys
import toml
import argparse
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

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
    base_image_dockerfile: str
    base_image_dockerfile_resolved: str
    
    # Container information
    container_name: str
    run_name: str
    
    # Paths (original from config)
    tarball_path: str
    tarball_directory: str
    
    # Paths (resolved absolute)
    tarball_path_resolved: str
    tarball_directory_resolved: str
    
    # Working directory and config paths
    working_directory: str
    config_file: str
    config_file_resolved: str
    config_directory: str
    
    # Configuration
    mounts: List[str]
    x11_path: str
    
    def resolve(self, path: str) -> str:
        """
        Resolve a path relative to the config directory.
        Returns None if the path cannot be resolved or doesn't exist.
        
        Args:
            path: Path to resolve (can be relative or absolute)
            
        Returns:
            Resolved absolute path if it exists, None otherwise
        """
        try:
            # If path is already absolute, use it as is
            if os.path.isabs(path):
                resolved_path = path
            else:
                # Resolve relative to config directory
                resolved_path = os.path.join(self.config_directory, path)
            
            # Check if the resolved path exists
            if os.path.exists(resolved_path):
                return resolved_path
            else:
                return None
        except Exception:
            return None
    
    @classmethod
    def create_parser(cls) -> argparse.ArgumentParser:
        """Create and configure the argument parser"""
        parser = argparse.ArgumentParser(
            description="Fabrinetes - Docker Container Management Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --cmd run --config-file containers.toml
  %(prog)s --cmd build --config-file containers.toml --buildbase
  %(prog)s --cmd status --config-file containers.toml
  %(prog)s --cmd restore --config-file containers.toml --base-image
  %(prog)s --cmd commit --config-file containers.toml

Available Commands:
  build    - Build base image from Dockerfile
  run      - Generate Docker run command
  commit   - Generate Docker commit command
  restore  - Generate Docker restore command
  status   - Show config file status
            """
        )
        
        # Main command structure
        parser.add_argument('--cmd', 
                           choices=['build', 'run', 'commit', 'restore', 'status'],
                           help='Command to execute')
        parser.add_argument('--config-file', 
                           help='Path to config.toml file')
        
        # Build command arguments
        parser.add_argument('--buildbase', 
                           action='store_true',
                           help='Build base image from Dockerfile (required for build command)')
        
        # Run command arguments
        parser.add_argument('--rm', 
                           action='store_true',
                           help='Remove container after exit')
        parser.add_argument('--x11', 
                           action='store_true',
                           help='Enable X11 forwarding')
        parser.add_argument('--no-x11', 
                           action='store_true',
                           help='Disable X11 forwarding')
        parser.add_argument('--usb', 
                           action='store_true',
                           help='Enable USB device access')
        parser.add_argument('--ask', 
                           action='store_true',
                           help='Ask before executing commands')
        parser.add_argument('--verbose', 
                           action='store_true',
                           help='Enable verbose output')
        
        # Restore command arguments
        parser.add_argument('--base-image', 
                           action='store_true',
                           help='Restore base image from tarball')
        parser.add_argument('--image', 
                           action='store_true',
                           help='Restore main image from tarball')
        
        # Commit command arguments
        parser.add_argument('--tag', 
                           help='Tag for the committed image')
        parser.add_argument('--message', 
                           help='Commit message')
        
        return parser
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'ContainerInfo':
        """Create ContainerInfo from parsed arguments"""
        if not args.config_file:
            print("❌ Error: --config-file is required")
            print("Usage: ./fabrinetes --cmd <command> --config-file <config.toml>")
            print("")
            print("Example config file locations:")
            print("  containers/my-project/config.toml")
            print("  /path/to/your/config.toml")
            sys.exit(1)
        
        return cls.get_container_info(args.config_file)
    
    @classmethod
    def get_container_info(cls, config_file: str) -> 'ContainerInfo':
        """
        Single function that returns all container naming and configuration information.
        This is the SINGLE SOURCE OF TRUTH for all config data and working directory information.
        
        Args:
            config_file: Path to the TOML configuration file
            
        Returns:
            ContainerInfo dataclass with all naming, configuration data, and resolved paths
        """
        # Resolve config file to absolute path
        config_file_absolute = os.path.abspath(config_file)
        
        # Get working directory (where the script was invoked from)
        working_directory = os.getcwd()
        
        # Get config directory
        config_directory = os.path.dirname(config_file_absolute)
        
        # Load config
        config = toml.load(config_file_absolute)
        container_config = config['config']
        
        # Image information
        image_name = container_config['image']['name']
        image_tag = container_config['image']['tag']
        image_full = f"{image_name}-{image_tag}"
        image_docker = f"{image_full}:{image_tag}"
        image_tarball = container_config['image']['tarball_name']
        
        # Base image information
        base_image_name = container_config['base_image']['name']
        base_image_tag = container_config['base_image']['tag']
        base_image_full = f"{base_image_name}-{base_image_tag}"
        base_image_docker = f"{base_image_full}:{base_image_tag}"
        base_image_tarball = container_config['base_image']['tarball_name']
        base_image_dockerfile = container_config['base_image'].get('dockerfile', 'Dockerfile')
        
        # Container information
        container_name = container_config['container']['name']
        run_name = f"{image_full}.run"
        
        # Paths (original from config)
        tarball_directory = f"containers/{image_name}"
        tarball_path = f"{tarball_directory}/{image_tarball}"
        
        # Resolved absolute paths
        tarball_directory_resolved = os.path.join(config_directory, tarball_directory)
        tarball_path_resolved = os.path.join(config_directory, tarball_path)
        
        # Create temporary ContainerInfo to use resolve method
        temp_info = cls(
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
            base_image_dockerfile=base_image_dockerfile,
            base_image_dockerfile_resolved=None,  # Will be set below
            
            # Container
            container_name=container_name,
            run_name=run_name,
            
            # Paths (original from config)
            tarball_path=tarball_path,
            tarball_directory=tarball_directory,
            
            # Paths (resolved absolute)
            tarball_path_resolved=tarball_path_resolved,
            tarball_directory_resolved=tarball_directory_resolved,
            
            # Working directory and config paths
            working_directory=working_directory,
            config_file=config_file,
            config_file_resolved=config_file_absolute,
            config_directory=config_directory,
            
            # Configuration
            mounts=container_config['mounts'],
            x11_path=container_config['X11_path']
        )
        
        # Use resolve method to get dockerfile path
        base_image_dockerfile_resolved = temp_info.resolve(base_image_dockerfile)
        
        # Update the dockerfile resolved path
        temp_info.base_image_dockerfile_resolved = base_image_dockerfile_resolved
        
        return temp_info

# Legacy function for backward compatibility
def get_container_info(config_file: str) -> ContainerInfo:
    """Legacy function - use ContainerInfo.get_container_info() instead"""
    return ContainerInfo.get_container_info(config_file)