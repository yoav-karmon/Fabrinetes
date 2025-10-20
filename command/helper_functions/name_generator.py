#!/usr/bin/env python3

"""
Name generator module for Fabrinetes containers.
Provides a single function that returns all container naming and configuration information.
"""

from command.helper_functions.config.name_generator import get_container_info, ContainerInfo

# Export the main function and dataclass for easy access
__all__ = ['get_container_info', 'ContainerInfo']