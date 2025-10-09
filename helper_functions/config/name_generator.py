#!/usr/bin/env python3

import os
import toml

def _get_image_name_from_config(config_file: str) -> str:
    config = toml.load(config_file)
    container_config = config['config']
    image_name = container_config['image_name']
    
    if ':' not in image_name:
        raise ValueError(f"Image name must contain ':' separator: {image_name}")
    
    return image_name

def get_image_name(config_file: str) -> dict:
    image_name = _get_image_name_from_config(config_file)
    name, tag = image_name.split(':', 1)
    return {
        'name': name,
        'tag': tag,
        'full': f"{name}.{tag}",
        'docker': f"{name}:{tag}"
    }

def get_container_name(config_file: str) -> str:
    return get_image_name(config_file)['name']

def get_run_name(config_file: str) -> str:
    return f"{get_image_name(config_file)['full']}.run"

def get_tarball_path(config_file: str) -> str:
    image_info = get_image_name(config_file)
    return f"containers/{image_info['name']}/images/{image_info['full']}.tar.gz"

def get_tarball_directory(config_file: str) -> str:
    return f"containers/{get_container_name(config_file)}/images"

def get_tarball_filename(config_file: str) -> str:
    return f"{get_image_name(config_file)['full']}.tar.gz"

def get_tarball_name_from_image_name(image_name: str) -> str:
    if ':' not in image_name:
        raise ValueError(f"Image name must contain ':' separator: {image_name}")
    
    name, tag = image_name.split(':', 1)
    return f"{name}.{tag}.tar.gz"

def get_config_info(config_file: str) -> dict:
    config = toml.load(config_file)
    container_config = config['config']
    image_info = get_image_name(config_file)
    
    return {
        'config_file': config_file,
        'image_name': image_info['full'],
        'image_name_without_tag': image_info['name'],
        'image_tag': image_info['tag'],
        'container_name': get_container_name(config_file),
        'run_name': get_run_name(config_file),
        'tarball_path': get_tarball_path(config_file),
        'tarball_directory': get_tarball_directory(config_file),
        'base_image': container_config['base_image'],
        'image_name_config': container_config['image_name'],
        'mounts': container_config['mounts'],
        'environment': container_config.get('environment', {}),
        'network': container_config.get('network', 'host'),
        'command': container_config.get('command', 'bash'),
        'init_env': container_config['init_env']
    }