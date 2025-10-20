#!/usr/bin/env python3

import os
import sys
import toml
import argparse
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable

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
    
    # Configuration
    mounts: List[str]
    x11_path: str
    
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
                           help='Path to config.toml file')
        parser.add_argument('--show-help', 
                           action='store_true',
                           help='Show help for the specific command')
        
        # Run command arguments
        parser.add_argument('--rm', 
                           action='store_true',
                           help='Remove container after exit')
        parser.add_argument('--x11', 
                           action='store_true',
                           help='Enable X11 forwarding')
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
        
        # Get working directory (where the config file is located)
        working_directory = os.path.dirname(config_file_absolute)
        
        # Get tarball directory (where the script was invoked from - where tarballs are stored)
        tarball_directory_base = os.getcwd()
        
        # Load config with error handling
        try:
            config = toml.load(config_file_absolute)
        except FileNotFoundError:
            print(f"Error: Config file not found: {config_file_absolute}")
            print("Please check the file path and try again.")
            sys.exit(1)
        except PermissionError:
            print(f"Error: Permission denied reading config file: {config_file_absolute}")
            print("Please check file permissions and try again.")
            sys.exit(1)
        except toml.TomlDecodeError as e:
            print(f"Error: TOML file corruption or syntax error in: {config_file_absolute}")
            print(f"Parse error: {e}")
            print("Please check the TOML syntax and try again.")
            print("Common issues:")
            print("  - Missing quotes around strings")
            print("  - Invalid table syntax")
            print("  - Unclosed brackets or quotes")
            print("  - Invalid characters")
            sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to load config file: {config_file_absolute}")
            print(f"Unexpected error: {e}")
            print("Please check the file and try again.")
            sys.exit(1)
        
        # Validate config structure
        if 'config' not in config:
            print(f"Error: Missing '[config]' section in: {config_file_absolute}")
            print("The config file must contain a '[config]' section.")
            sys.exit(1)
        
        container_config = config['config']
        
        # Validate required sections
        if 'image' not in container_config:
            print(f"Error: Missing '[config.image]' section in: {config_file_absolute}")
            print("The config file must contain a '[config.image]' section.")
            sys.exit(1)
        
        if 'container' not in container_config:
            print(f"Error: Missing '[config.container]' section in: {config_file_absolute}")
            print("The config file must contain a '[config.container]' section.")
            sys.exit(1)
        
        # Validate required image fields
        image_section = container_config['image']
        required_image_fields = ['name', 'tag']
        for field in required_image_fields:
            if field not in image_section:
                print(f"Error: Missing required field '[config.image.{field}]' in: {config_file_absolute}")
                print(f"The config file must contain '{field}' in the '[config.image]' section.")
                sys.exit(1)
        
        # Validate required container fields
        container_section = container_config['container']
        required_container_fields = ['name']
        for field in required_container_fields:
            if field not in container_section:
                print(f"Error: Missing required field '[config.container.{field}]' in: {config_file_absolute}")
                print(f"The config file must contain '{field}' in the '[config.container]' section.")
                sys.exit(1)
        
        # Image information
        image_name = image_section['name']
        image_tag = image_section['tag']
        image_full = f"{image_name}-{image_tag}"
        image_docker = f"{image_name}:{image_tag}"
        image_dockerfile = image_section.get('dockerfile_path', 'Dockerfile')
        image_package_list = image_section.get('package_list_path', 'packages.txt')
        
        # Container information
        container_name = container_section['name']
        run_name = f"{container_name}.run"
        
        # Validate optional sections and set defaults
        mounts = container_config.get('mounts', [])
        x11_path = container_config.get('X11_path', '/tmp/.X11-unix:/tmp/.X11-unix')
        
        # Create temporary ContainerInfo to use resolve methods
        temp_info = cls(
            # Image
            image_name=image_name,
            image_tag=image_tag,
            image_full=image_full,
            image_docker=image_docker,
            image_dockerfile=image_dockerfile,
            image_dockerfile_resolved=None,  # Will be set below
            image_package_list=image_package_list,
            image_package_list_resolved=None,  # Will be set below
            
            # Container
            container_name=container_name,
            run_name=run_name,
            
            # Working directory and config paths
            working_directory=working_directory,
            config_file=config_file,
            config_file_resolved=config_file_absolute,
            
            # Configuration
            mounts=mounts,
            x11_path=x11_path
        )
        
        # Use resolve method to get dockerfile path (don't check existence for build files)
        image_dockerfile_resolved = temp_info.resolve(image_dockerfile, check_exists=False)
        
        # Use resolve method to get package list path
        image_package_list_resolved = temp_info.resolve(image_package_list)
        
        # Update the resolved paths
        temp_info.image_dockerfile_resolved = image_dockerfile_resolved
        temp_info.image_package_list_resolved = image_package_list_resolved
        
        return temp_info

# Legacy function for backward compatibility
def get_container_info(config_file: str) -> ContainerInfo:
    """Legacy function - use ContainerInfo.get_container_info() instead"""
    return ContainerInfo.get_container_info(config_file)