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


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def printlocals(locals_dict):
    print("=== Current Argument Values ===")
    for key, value in locals_dict.items():
        if key != "ctx":  # Skip the context object unless you want to include it
            print(f"{key:10} = {value}")
    print("===============================")

@task()
def build(ctx):
    ctx.run("docker build -t fabrinetes-dev -f Dockerfile .", pty=True)

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
def run(ctx, file,rm=True,ver=None,name=None, x11=False,usb=False,ask=True):
   
   
    print("===============================")
    ctx.run("docker images", pty=True)
    print("===============================")
    print("")
    print("===============================")
    ctx.run("docker ps -a", pty=True)
    print("===============================")
    print("")


   

    database = toml.load(file)
    IMAGE_SETTINGS = database.get("Containers", {}).get(ver, {})
    IMAGE_REPOSITORY = IMAGE_SETTINGS.get("REPOSITORY", None)
    IMAGE_TAG = IMAGE_SETTINGS.get("TAG", "latest")
    IMAGE_NAME = f"{IMAGE_REPOSITORY}:{IMAGE_TAG}"
    MOUNTS_LIST = IMAGE_SETTINGS.get("mounts", [])
    PATH_INJECT_LIST = IMAGE_SETTINGS.get("PATH", [])
    del database

    printlocals(locals())
    print("")

    cmd_parts=[]
    cmd_parts = ["docker", "run", "-dit"]
    if name:
        cmd_parts.extend(["--name", name])
    else:
        print("Error: You must provide a name for the container using --name")
        sys.exit(1)
        
   
    if rm:
        cmd_parts.append("--rm")
    if x11:
        cmd_parts.extend([
            "--net=host",
            "-e", f"DISPLAY={os.environ['DISPLAY']}",
            "-v", "/tmp/.X11-unix:/tmp/.X11-unix",
            "-v", f"{os.environ['HOME']}/.Xauthority:/root/.Xauthority:ro"
        ])

    if usb:
        cmd_parts.append("-v /dev/bus/usb:/dev/bus/usb")


    file_path = pathlib.Path(file)
    folder_path = file_path.resolve().parent.parent
    for mount in MOUNTS_LIST:
        # Expecting format: source:dest
        if ':' not in mount:
            print(f"Warning: Invalid mount format '{mount}' — expected source:dest. Skipping.")
            continue

        source_str, dest = mount.split(':', 1)
        if(not source_str.startswith("/")):
            source_path = folder_path / source_str
            source_path = source_path.resolve()
        else:
            source_path = pathlib.Path(source_str).resolve()

        if not source_path.exists():
            print(f"Warning: Mount source '{source_path}' does not exist. Skipping.")
            continue

        cmd_parts.append(f"-v {str(source_path)}:{dest}")
    cmd_parts.append(IMAGE_NAME)
    cmd = " ".join(cmd_parts)
    print(f"Running command: {' '.join(cmd_parts)}")
    if(ask):
        answer = input("Do you want to continue? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
    
    ctx.run(cmd, pty=True)
    ctx.run(f"docker exec {name} git config --system --add safe.directory '*'",pty=True,echo=True)


   
