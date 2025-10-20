#!/usr/bin/env python3

"""
Config module for Fabrinetes - Single source of truth for configuration parsing.

This module provides functions to extract configuration information from TOML config files,
including image names, container names, tarball paths, and other configuration data.

All functions take a config_file path as input and return the relevant configuration data.
This ensures consistency across the entire codebase.
"""

from .name_generator import get_container_info, ContainerInfo

__all__ = [
    'get_container_info',
    'ContainerInfo'
]