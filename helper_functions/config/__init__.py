#!/usr/bin/env python3

"""
Config module for Fabrinetes - Single source of truth for configuration parsing.

This module provides functions to extract configuration information from TOML config files,
including image names, container names, tarball paths, and other configuration data.

All functions take a config_file path as input and return the relevant configuration data.
This ensures consistency across the entire codebase.
"""

from .name_generator import (
    get_image_name,
    get_container_name,
    get_run_name,
    get_tarball_path,
    get_tarball_directory,
    get_tarball_filename,
    get_tarball_name_from_image_name,
    get_config_info
)

__all__ = [
    'get_image_name',
    'get_container_name',
    'get_run_name',
    'get_tarball_path',
    'get_tarball_directory',
    'get_tarball_filename',
    'get_tarball_name_from_image_name',
    'get_config_info'
]