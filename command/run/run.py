#!/usr/bin/env python3

import os
import pathlib
from typing import Optional
from command.helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartFlag, CmdPartMounts, CmdPartX11Support, CmdPartArg, CmdPartName, CmdPart, CmdPartHardcoded, CmdPartHostNetworking, CmdPartShmSize
from command.help.help import show_run_help

class CmdPartUser(CmdPart):
    """Command part for user parameter (-u)"""
    
    def __init__(self, user_value: str, comment: Optional[str] = None):
        super().__init__(hardcoded="-u", comment=comment)
        self.user_value = user_value
    
    def comment_str(self) -> str:
        return f"#     {self.hardcoded} {self.user_value}"
    
    def execution_str(self) -> str:
        return f"{self.hardcoded} {self.user_value}"
    
    def resolve(self, container_info) -> bool:
        # User value is already set, no resolution needed
        return True

def run(args, container_info):
    """Run a Docker container with the specified configuration"""
    # Extract arguments
    rm = args.rm
    verbose = args.verbose
    # x11 = args.x11  # Removed - now using config-based X11
    usb = args.usb
    host_net = args.host_net
    ask = args.ask
    help_flag = args.show_help
    shm_size = getattr(args, 'shm_size', None)  # Get shm_size with default None
    
    # Check for help flag first
    if help_flag:
        show_run_help()
        return
    
    # Generate container name
    container_name = container_info.run_name
    if not container_name:
        return
    
    # Create command builder
    builder = CommandBuilder("Run")
    builder.set_base_command(["docker", "run", "-dit"])
    
    # Add WORKDIR environment variable
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory", 
                                          comment="# Set working directory for relative paths"))
    
    # Add user creation environment variables
    current_user = os.getenv('USER', os.getenv('USERNAME', 'user'))
    builder.add_part("container_user", CmdPartEnv("CONTAINER_USER", current_user, 
                                                 comment="# Set container username for entrypoint"))
    builder.add_part("container_uid", CmdPartEnv("CONTAINER_UID", str(os.getuid()), 
                                                comment="# Set container user ID for entrypoint"))
    builder.add_part("container_gid", CmdPartEnv("CONTAINER_GID", str(os.getgid()), 
                                                comment="# Set container group ID for entrypoint"))
    builder.add_part("container_home", CmdPartEnv("CONTAINER_HOME", f"/home/{current_user}", 
                                                 comment="# Set container home directory for entrypoint"))
    
    # Add flags
    if rm:
        builder.add_part("rm", CmdPartFlag("--rm", comment="# Remove container when it exits (from --rm flag)"))
    
    # Add host networking (enabled via --host-net flag OR automatically when X11 is enabled)
    if host_net or container_info.x11_enabled:
        comment = "# Host networking (required for X11 GUI support with docker attach)"
        if host_net and container_info.x11_enabled:
            comment = "# Host networking (enabled via --host-net flag AND X11 GUI support)"
        elif host_net:
            comment = "# Host networking (enabled via --host-net flag)"
        builder.add_part("host_networking", CmdPartHostNetworking(comment=comment))
    
    # Add privileged mode (always enabled for hardware access)
    builder.add_part("privileged", CmdPartFlag("--privileged", comment="# Privileged mode (always enabled for hardware access)"))
    
    # Add X11 support (environment only, NOT network - network is handled above)
    if container_info.x11_enabled:
        builder.add_part("x11_support", CmdPartX11Support(True, 
                         comment="# X11 GUI support (display environment only)"))

    # Add USB support
    if usb:
        builder.add_part("usb", CmdPartFlag("-v /dev/bus/usb:/dev/bus/usb", comment="# Mount USB devices (from --usb flag)"))
    
    # Add shared memory size (default 2g for FPGA development)
    default_shm_size = "2g"
    actual_shm_size = shm_size if shm_size else default_shm_size
    builder.add_part("shm_size", CmdPartShmSize(actual_shm_size, 
                     comment=f"# Shared memory size (default: {default_shm_size}, FPGA tools need large shm)"))
    
    # UNIFIED MOUNT HANDLING: Collect ALL mounts into single list
    all_mounts = []
    
    # Add regular mounts
    if container_info.mounts:
        all_mounts.extend(container_info.mounts)
    
    # Add X11 mounts (if enabled)
    if container_info.x11_enabled:
        all_mounts.extend(container_info.x11_mounts)
    
    # Add USB mounts (if enabled)
    if usb:
        all_mounts.append("/dev/bus/usb:/dev/bus/usb")
    
    # Single unified mount handling - all mounts processed identically
    if all_mounts:
        builder.add_part("mounts", CmdPartMounts(all_mounts, 
                         comment="# Volume mounts (regular + X11 + USB)"))
    elif container_info.x11_enabled:
        # X11 enabled but no mounts - this is an error
        builder.add_part("mounts_error", CmdPartHardcoded("echo 'error: X11 is enabled but no mounts are configured'", 
                         comment="# Volume mounts (regular + X11 + USB)"))
    
    # Note: We don't use --user flag here because the entrypoint script needs root privileges
    # to create users. Instead, we rely on the entrypoint script to switch to the correct user
    # for the main process, and docker exec commands will need to specify the user explicitly
    # builder.add_part("user", CmdPartUser(f"{current_user}:{current_user}", 
    #                                    comment="# Run container as specified user (affects docker exec commands)"))
    
    # Add container name
    builder.add_part("container_name", CmdPartArg("--name", "run_name", 
                                                 comment="# Container name (from config.container.name)"))
    
    # Add image name
    builder.add_part("image_name", CmdPartName("image_docker", 
                                              comment="# Docker image (from config.image.name:tag)",
                                              check_image_exists=True))
    
    # Add command
    builder.add_part("command", CmdPartFlag("/bin/bash", comment="# Interactive bash shell"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    
    print(commented_str)
    print(execution_str)
