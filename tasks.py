#!/usr/bin/env python3

from dataclasses import asdict, dataclass
import toml
from invoke import task
import os
import re
import sys
import shutil
import subprocess
import argparse
import time
import json
import yaml
from dataclasses import dataclass, asdict
import os
import toml
from tabulate import tabulate
import pathlib 
import logging
import datetime

# Import all tasks from modular structure
from invoke_tasks import gen_image, commit, run, exec, shell, clean_image, kill, pkg, list, help, test

def export_image(ctx, repo_name, tag):
    """Export Docker image to tar.gz file"""
    import subprocess
    
    # Create images directory if it doesn't exist
    images_dir = f"containers/{repo_name}/images"
    os.makedirs(images_dir, exist_ok=True)
    
    # Export image
    tar_filename = f"{repo_name}-{tag}.tar.gz"
    tar_path = f"{images_dir}/{tar_filename}"
    
    print(f"Exporting {repo_name}:{tag} to {tar_path}...")
    
    try:
        # Use subprocess to handle the pipe properly
        result = subprocess.run(
            f"docker save {repo_name}:{tag} | gzip > {tar_path}",
            shell=True, check=True, capture_output=True, text=True
        )
        print(f"Successfully exported image to {tar_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error exporting image: {e}")
        print(f"stderr: {e.stderr}")

def import_image(ctx, tar_path):
    """Import Docker image from tar.gz file"""
    import subprocess
    
    print(f"Importing image from {tar_path}...")
    
    try:
        # Use subprocess to handle the pipe properly
        result = subprocess.run(
            f"gunzip -c {tar_path} | docker load",
            shell=True, check=True, capture_output=True, text=True
        )
        print(f"Successfully imported image from {tar_path}")
        print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error importing image: {e}")
        print(f"stderr: {e.stderr}")
        return False