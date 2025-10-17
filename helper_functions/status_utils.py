#!/usr/bin/env python3

"""
Status utilities module for Fabrinetes - Utility functions for status operations.

This module provides utility functions used by the status helper module,
including file size formatting and Docker error translation.
"""

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def translate_docker_error(error: Exception) -> str:
    """Translate Docker API errors into user-friendly messages"""
    error_str = str(error).lower()
    
    # Docker daemon not running
    if "connection aborted" in error_str or "no such file or directory" in error_str:
        return "Docker daemon not running - start Docker service"
    
    # Permission denied
    if "permission denied" in error_str or "access denied" in error_str:
        return "Permission denied - add user to docker group"
    
    # Network connectivity issues
    if "connection refused" in error_str or "network" in error_str:
        return "Network error - check Docker connectivity"
    
    # API version issues
    if "api version" in error_str or "version" in error_str:
        return "Docker API version mismatch - update Docker"
    
    # Resource constraints
    if "no space" in error_str or "disk space" in error_str:
        return "Resource error - check available disk space"
    
    if "memory" in error_str or "oom" in error_str:
        return "Resource error - check available memory"
    
    # Image/container specific errors
    if "image not found" in error_str or "no such image" in error_str:
        return "Image not found - build or pull image first"
    
    if "container not found" in error_str or "no such container" in error_str:
        return "Container not found - run container first"
    
    # Generic fallback
    return f"Docker error - {str(error)}"
