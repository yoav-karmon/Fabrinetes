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
from typing import List, Tuple


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def resolve_mounts(mounts: List[str], relative_path: pathlib.Path) -> List[Tuple[str, str]]:
    """
    Resolves a list of mount strings of the form 'host:container',
    expanding environment variables and resolving relative host paths
    against the provided relative_path.
    """
    resolved = []

    for entry in mounts:
        if ":" not in entry:
            raise ValueError(f"Invalid mount format (expected 'host:container'): {entry}")
        
        host_raw, container_raw = entry.split(":", 1)

        # Expand and resolve host path
        host_expanded = os.path.expandvars(host_raw)
        host_path = pathlib.Path(host_expanded)
        if not host_path.is_absolute():
            host_path = (relative_path / host_path).resolve()

        # Expand environment variables in container path
        container_path = os.path.expandvars(container_raw)

        resolved.append((str(host_path), container_path))

    return resolved


def printlocals(locals_dict,verbose=False):
    print("=== Current Argument Values ===")
    for key, value in locals_dict.items():
        if key != "ctx":
            if isinstance(value, dict) or isinstance(value, List):
                if(verbose):
                    print(f"{key:10} =")
                    print(json.dumps(value, indent=2))
            else:
                print(f"{key:10} = {value}")
        
    print("===============================")

@task
def build(ctx):
    username = os.getenv("USER") or os.getenv("USERNAME")
    uid = os.getuid()
    gid = os.getgid()
    home_dir = os.path.expanduser("~")

    ctx.run(
        f"docker build "
        f"--build-arg USERNAME={username} "
        f"--build-arg UID={uid} "
        f"--build-arg GID={gid} "
        f"--build-arg HOME_DIR={home_dir} "
        f"-t fabrinetes-dev -f Dockerfile .",
        pty=True,
    )

@task
def list(ctx):
    print("============images=========================================================")
    ctx.run("docker images", pty=True)
    print("===========================================================================")
    print("")
    print("===========containers=======================================================")
    ctx.run("docker ps -a", pty=True)
    print("===========================================================================")
    print("")


@task
def run(ctx, file,rm=False,verbose=False,ver=None,name=None, x11=True,usb=False,ask=True):
   
   
    print("===============================")
    ctx.run("docker images", pty=True)
    print("===============================")
    print("")
    print("===============================")
    ctx.run("docker ps -a", pty=True)
    print("===============================")
    print("")


    _config_file_path = pathlib.Path(file).resolve()
    RELATIVE_PATH = _config_file_path.parent
    database = toml.load(str(_config_file_path))
    IMAGE_SETTINGS = database.get("Containers", {}).get(ver, {})

    _image_repository = IMAGE_SETTINGS.get("REPOSITORY", None)
    _image_tag = IMAGE_SETTINGS.get("TAG", "latest")
    IMAGE_NAME = f"{_image_repository}:{_image_tag}"

    MOUNTS_LIST = IMAGE_SETTINGS.get("mounts", [])
    _this_file_path = pathlib.Path(__file__).resolve().parent

    MOUNTS_LIST.append(f"{_this_file_path}/source/bashrc-root:{os.getenv('HOME')}/.bashrc")
    MOUNTS_LIST.append(f"{_this_file_path}/source/project_setup/:/opt/project_setup")

    RESOLVED_MOUNTS_LIST=resolve_mounts(MOUNTS_LIST, RELATIVE_PATH)
    RESOLVED_MOUNTS_LIST:List[Tuple[str, str]]
        
    del database
    del _image_repository
    del _image_tag
    del _config_file_path

    printlocals(locals(),verbose)
    print("")

    cmd_parts=[]
    cmd_parts = ["docker run -dit"]
    if name:
        cmd_parts.append(f"--name {name}")
    else:
        print("Error: You must provide a name for the container using --name")
        sys.exit(1)
        
   
    if rm:
        cmd_parts.append("--rm")
    if x11:
        cmd_parts.append("--net=host")
        cmd_parts.append(f"-e DISPLAY={os.environ['DISPLAY']}")
        cmd_parts.append(f"-e /tmp/.X11-unix:/tmp/.X11-unix")
        cmd_parts.append(f"-v {os.environ['HOME']}/.Xauthority:/home/ykarmon/.Xauthority:ro")
       

    if usb:
        cmd_parts.append("-v /dev/bus/usb:/dev/bus/usb")


    need_to_exit = False
    for mount in RESOLVED_MOUNTS_LIST:
       

        source_str, dest = mount  
        source_path = pathlib.Path(source_str)

        if not source_path.exists():
            print(f"Warning: Mount source '{source_path}' does not exist. Skipping.")
            need_to_exit= True
            continue

        cmd_parts.append(f"-v {str(source_path)}:{dest}")

    if(need_to_exit):
        print("Exiting due to missing mount source.")
        sys.exit(1)

    cmd_parts.append(IMAGE_NAME)
    cmd = " ".join(cmd_parts)

    print(f"Running command: {cmd}")
    print(f"command parts:")
    for part in cmd_parts:
        print(part)

    if(ask):
        answer = input("Do you want to continue? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
    
    ctx.run(cmd, pty=True)


    ctx.run(f"docker exec {name} sudo git config --global --add safe.directory '*'", pty=True, echo=True, warn=True)
    
    
    



   
