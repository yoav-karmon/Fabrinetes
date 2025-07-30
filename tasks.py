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





def printlocals(locals_dict):
    print("=== Current Argument Values ===")
    for key, value in locals_dict.items():
        if key != "ctx":  # Skip the context object unless you want to include it
            print(f"{key:10} = {value}")
    print("===============================")

@task()
def build(ctx):
    with ctx.cd("devcontainers"):
        ctx.run("docker build -t fabrinetes-dev -f .devcontainer/Dockerfile .", pty=True)
        ctx.run("docker image prune -f", pty=True)
        ctx.run("docker images fabrinetes-dev", pty=True)

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
def run(ctx, rm=False,name=None, x11=False,usb=False,ask=True):
   
   
    print("===============================")
    ctx.run("docker images", pty=True)
    print("===============================")
    print("")
    print("===============================")
    ctx.run("docker ps -a", pty=True)
    print("===============================")
    print("")


   

    database = toml.load("devcontainers/containers.toml")
    IMAGE_SETTINGS = database.get("Containers", {}).get(name, {})
    IMAGE_REPOSITORY = IMAGE_SETTINGS.get("REPOSITORY", None)
    IMAGE_TAG = IMAGE_SETTINGS.get("TAG", "latest")
    IMAGE_NAME = f"{IMAGE_REPOSITORY}:{IMAGE_TAG}"
    
    MOUNTS_LIST = IMAGE_SETTINGS.get("mounts", [])
    PATH_INJECT_LIST = IMAGE_SETTINGS.get("PATH", [])
    del database

    printlocals(locals())
    print("")

    cmd_parts=[]
    cmd_parts = ["docker", "run", "-it"]
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


    for mount in MOUNTS_LIST:
        # Expecting format: source:dest
        if ':' not in mount:
            print(f"Warning: Invalid mount format '{mount}' — expected source:dest. Skipping.")
            continue

        source, dest = mount.split(':', 1)

        if not os.path.exists(source):
            print(f"Warning: Mount source '{source}' does not exist. Skipping.")
            continue

        cmd_parts.append(f"-v {source}:{dest}")
    cmd_parts.append(IMAGE_NAME)
    # cmd_parts = [
    #     "docker", "run", "-it", "--rm",
    #     "--net=host",
    #     "-e", f"DISPLAY={os.environ['DISPLAY']}",
    #     "-v", "/tmp/.X11-unix:/tmp/.X11-unix",
    #     "-v", f"{os.environ['HOME']}/.Xauthority:/root/.Xauthority:ro",
    #     "-v", "/dev/bus/usb:/dev/bus/usb",
    #     "-v", "/home/ykarmon/AMD/Vivado/2021.2:/opt/vivado",
    #     "-v", f"{os.path.expanduser('~')}/repos:/root/repos",
    #     "fabrinetes-dev"
    # ]
    cmd = " ".join(cmd_parts)
    print(f"Running command: {' '.join(cmd_parts)}")
    if(ask):
        answer = input("Do you want to continue? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
    
    with ctx.cd("devcontainers"):
        ctx.run(cmd, pty=True)

   
