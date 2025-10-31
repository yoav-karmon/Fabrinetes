#!/usr/bin/env python3

import os
import sys
import json
import toml
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from functools import lru_cache

# Constants
DEFAULT_X11_MOUNTS = [
    "/tmp/.X11-unix:/tmp/.X11-unix",
    "$HOME/.Xauthority:$HOME/.Xauthority:ro"
]

# Common error handling functions
def _handle_config_error(error_msg: str, config_file: str) -> None:
    """Common error handling for config operations"""
    print(f"Error: {error_msg}: {config_file}")
    sys.exit(1)

def _validate_config_section(config_data: dict, section_name: str, config_file: str) -> None:
    """Validate required config section exists"""
    if section_name not in config_data:
        _handle_config_error(f"Missing '[config.{section_name}]' section", config_file)

def _load_config_file(config_file: str) -> dict:
    """Load and parse config file (JSON or TOML) with error handling"""
    try:
        file_ext = os.path.splitext(config_file)[1].lower()
        with open(config_file, 'r') as f:
            if file_ext == '.json':
                return json.load(f)
            elif file_ext == '.toml':
                return toml.load(f)
            else:
                _handle_config_error(f"Unsupported config file format: {file_ext}. Supported formats: .json, .toml", config_file)
    except FileNotFoundError:
        _handle_config_error("Config file not found", config_file)
    except json.JSONDecodeError as e:
        _handle_config_error(f"Failed to parse JSON config file: {e}", config_file)
    except Exception as e:
        _handle_config_error(f"Failed to parse config file: {e}", config_file)

def _load_toml_file(config_file: str) -> dict:
    """Legacy function - use _load_config_file() instead"""
    return _load_config_file(config_file)

@dataclass
class ImageConfig:
    """Image configuration section"""
    name: str
    tag: str
    dockerfile_path: str = "Dockerfile"
    package_list_path: str = "packages.txt"

@dataclass
class ContainerConfig:
    """Container configuration section"""
    name: str

@dataclass
class X11Config:
    """X11 configuration section"""
    enable: bool = True
    mounts: List[str] = field(default_factory=lambda: DEFAULT_X11_MOUNTS)

@dataclass
class ConfigSection:
    """Main config section"""
    mounts: List[str] = field(default_factory=list)
    X11: Optional[X11Config] = None

@dataclass
class CommandDefinition:
    """Definition for a single command"""
    name: str
    description: str
    function: Callable
    requires_config: bool = True
    testable: bool = True

@dataclass
class CommandConfig:
    """Centralized command configuration - single source of truth for all commands"""
    
    @classmethod
    @lru_cache(maxsize=1)
    def get_all_commands(cls) -> Dict[str, CommandDefinition]:
        """Get all available commands - single source of truth"""
        from command.build.build import build
        from command.run.run import run
        from command.test.test import test
        from command.exec.exec import exec_cmd
        
        return {
            'build': CommandDefinition(
                name='build',
                description='Build image from Dockerfile',
                function=build,
                requires_config=True,
                testable=True
            ),
            'run': CommandDefinition(
                name='run',
                description='Generate Docker run command',
                function=run,
                requires_config=True,
                testable=True
            ),
            'status': CommandDefinition(
                name='status',
                description='Show config file status',
                function=cls._status_command,
                requires_config=True,
                testable=True
            ),
            'help': CommandDefinition(
                name='help',
                description='Show this help message',
                function=cls._help_command,
                requires_config=False,
                testable=False
            ),
            'test': CommandDefinition(
                name='test',
                description='Run all commands in test mode',
                function=test,
                requires_config=True,
                testable=False
            ),
            'exec': CommandDefinition(
                name='exec',
                description='Generate Docker exec command for running container',
                function=exec_cmd,
                requires_config=True,
                testable=True
            )
        }
    
    @classmethod
    def get_command_names(cls) -> List[str]:
        """Get list of command names for argument parser"""
        return list(cls.get_all_commands().keys())
    
    @classmethod
    def get_testable_commands(cls) -> List[str]:
        """Get list of testable command names"""
        commands = cls.get_all_commands()
        return [name for name, cmd in commands.items() if cmd.testable]
    
    @classmethod
    def get_command_description(cls, name: str) -> str:
        """Get description for a specific command"""
        commands = cls.get_all_commands()
        cmd_def = commands.get(name)
        return cmd_def.description if cmd_def else 'Unknown command'
    
    @classmethod
    def _status_command(cls, args, container_info):
        """Internal status command implementation"""
        try:
            from command.helper_functions.status_helper import collect_comprehensive_status, format_status_output
            container_info = ContainerInfo.get_container_info(container_info.config_file_resolved)
            status = collect_comprehensive_status(container_info)
            print(format_status_output(status))
        except FileNotFoundError as e:
            print(f"Config file not found: {e}")
        except Exception as e:
            print(f"Error checking status: {e}")
    
    @classmethod
    def _help_command(cls, args, container_info):
        """Internal help command implementation"""
        from command.help.help import show_global_help
        show_global_help()

@dataclass
class ContainerInfo:
    """Dataclass containing all container naming and configuration information"""
    # Image information
    image_name: str
    image_tag: str
    image_full: str
    image_docker: str
    image_dockerfile: str
    image_dockerfile_resolved: str
    image_package_list: str
    image_package_list_resolved: str
    
    # Container information
    container_name: str
    run_name: str
    
    # Working directory and config paths
    working_directory: str
    config_file: str
    config_file_resolved: str
    
    # Configuration objects
    image_config: ImageConfig
    container_config: ContainerConfig
    config_section: ConfigSection
    
    # Convenience properties for backward compatibility
    @property
    def mounts(self) -> List[str]:
        return self.config_section.mounts
    
    @property
    def x11_enabled(self) -> bool:
        return self.config_section.X11.enable if self.config_section.X11 else True
    
    @property
    def x11_mounts(self) -> List[str]:
        if not self.config_section.X11:
            # No X11 section - return defaults
            return DEFAULT_X11_MOUNTS
        
        if not self.config_section.X11.enable:
            # X11 disabled - return empty list
            return []
        
        # X11 enabled - return configured mounts
        return self.config_section.X11.mounts
    
    def resolve(self, path: str, check_exists: bool = True) -> str:
        """
        Resolve a path relative to the config directory.
        
        Args:
            path: Path to resolve (can be relative or absolute)
            check_exists: If True, returns None if path doesn't exist. If False, returns resolved path regardless.
            
        Returns:
            Resolved absolute path if it exists (or if check_exists=False), None otherwise
        """
        try:
            # If path is already absolute, use it as is
            if os.path.isabs(path):
                resolved_path = path
            else:
                # Resolve relative to config directory
                resolved_path = os.path.join(self.working_directory, path)
            
            # Check if the resolved path exists (only if requested)
            if check_exists and not os.path.exists(resolved_path):
                return None
            
            return resolved_path
        except Exception:
            return None
    
    @classmethod
    def create_parser(cls) -> argparse.ArgumentParser:
        """Create and configure the argument parser"""
        # Get command names and descriptions from centralized config
        command_names = CommandConfig.get_command_names()
        command_descriptions = []
        
        for name in command_names:
            desc = CommandConfig.get_command_description(name)
            command_descriptions.append(f"  {name:<12} - {desc}")
        
        parser = argparse.ArgumentParser(
            description="Fabrinetes - Docker Container Management Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=f"""
Examples:
  %(prog)s --cmd run --config-file containers.toml
  %(prog)s --cmd exec --config-file containers.toml
  %(prog)s --cmd exec --config-file containers.toml --exec-cmd "hdlforge test"
  %(prog)s --cmd build --config-file containers.toml
  %(prog)s --cmd status --config-file containers.toml
  %(prog)s --cmd test --config-file containers.toml

Available Commands:
{chr(10).join(command_descriptions)}
            """
        )
        
        # Main command structure - use centralized command names
        parser.add_argument('--cmd', 
                           choices=command_names,
                           help='Command to execute')
        parser.add_argument('--config-file', 
                           help='Path to config.json or config.toml file')
        parser.add_argument('--show-help', 
                           action='store_true',
                           help='Show help for the specific command')
        
        # Run command arguments
        parser.add_argument('--rm', 
                           action='store_true',
                           help='Remove container after exit')
        # parser.add_argument('--x11', 
        #                    action='store_true',
        #                    help='Enable X11 forwarding')  # Removed - now config-driven
        parser.add_argument('--usb', 
                           action='store_true',
                           help='Enable USB device access')
        parser.add_argument('--host-net', 
                           action='store_true',
                           help='Enable host networking (required for NIC access)')
        parser.add_argument('--ask', 
                           action='store_true',
                           help='Ask before executing commands')
        parser.add_argument('--verbose', 
                           action='store_true',
                           help='Enable verbose output')
        parser.add_argument('--shm-size', 
                           help='Set shared memory size (e.g., 2g). Default: 2g for FPGA development')
        
        # Restore command arguments
        # Commit command arguments
        parser.add_argument('--tag', 
                           help='Tag for the committed image')
        parser.add_argument('--message', 
                           help='Commit message')
        
        # Exec command arguments
        parser.add_argument('--exec-cmd', 
                           nargs='*',
                           help='Command to execute inside the container')
        
        # Push command arguments
        parser.add_argument('--github-username', 
                           help='GitHub username for container registry')
        parser.add_argument('--registry', 
                           help='Container registry URL (default: ghcr.io)')
        
        return parser
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'ContainerInfo':
        """Create ContainerInfo from parsed arguments"""
        if not args.config_file:
            print("Error: --config-file is required")
            print("Usage: ./fabrinetes --cmd <command> --config-file <config.json|config.toml>")
            print("")
            print("Example config file locations:")
            print("  containers/my-project/config.json")
            print("  containers/my-project/config.toml")
            print("  /path/to/your/config.json")
            sys.exit(1)
        
        return cls.get_container_info(args.config_file)
    
    @classmethod
    @lru_cache(maxsize=128)
    def get_container_info(cls, config_file: str) -> 'ContainerInfo':
        """
        Load container configuration from TOML file and create ContainerInfo dataclass.
        Uses dataclass parsing instead of raw dictionary access.
        """
        # Resolve config file path
        config_file_absolute = os.path.abspath(config_file)
        working_directory = os.path.dirname(config_file_absolute)
        
        # Load config file (JSON or TOML)
        config_data_dict = _load_config_file(config_file_absolute)
        
        # Validate required sections exist
        if 'config' not in config_data_dict:
            _handle_config_error("Missing '[config]' section", config_file_absolute)
        
        config_data = config_data_dict['config']
        
        # Parse configuration sections using dataclasses
        try:
            # Parse image config
            _validate_config_section(config_data, 'image', config_file_absolute)
            image_config = ImageConfig(**config_data['image'])
            
            # Parse container config
            _validate_config_section(config_data, 'container', config_file_absolute)
            container_config = ContainerConfig(**config_data['container'])
            
            # Parse main config section
            config_section_data = {k: v for k, v in config_data.items() 
                                 if k not in ['image', 'container']}
            
            # Handle X11 section if present
            if 'X11' in config_section_data:
                config_section_data['X11'] = X11Config(**config_section_data['X11'])
            
            config_section = ConfigSection(**config_section_data)
            
        except TypeError as e:
            _handle_config_error(f"Invalid configuration: {e}", config_file_absolute)
        
        # Create ContainerInfo with parsed dataclasses
        container_info = cls(
            # Image information
            image_name=image_config.name,
            image_tag=image_config.tag,
            image_full=f"{image_config.name}-{image_config.tag}",
            image_docker=f"{image_config.name}:{image_config.tag}",
            image_dockerfile=image_config.dockerfile_path,
            image_dockerfile_resolved=None,  # Will be set below
            image_package_list=image_config.package_list_path,
            image_package_list_resolved=None,  # Will be set below
            
            # Container information
            container_name=container_config.name,
            run_name=f"{container_config.name}.run",
            
            # Working directory and config paths
            working_directory=working_directory,
            config_file=config_file,
            config_file_resolved=config_file_absolute,
            
            # Configuration objects
            image_config=image_config,
            container_config=container_config,
            config_section=config_section
        )
        
        # Use resolve method to get dockerfile path
        image_dockerfile_resolved = container_info.resolve(image_config.dockerfile_path, check_exists=False)
        image_package_list_resolved = container_info.resolve(image_config.package_list_path)
        
        # Update the resolved paths
        container_info.image_dockerfile_resolved = image_dockerfile_resolved
        container_info.image_package_list_resolved = image_package_list_resolved
        
        return container_info

# Legacy function for backward compatibility
def get_container_info(config_file: str) -> ContainerInfo:
    """Legacy function - use ContainerInfo.get_container_info() instead"""
    return ContainerInfo.get_container_info(config_file)