#!/usr/bin/env python3

import os
import pathlib
from typing import List, Dict, Optional, Tuple
from abc import ABC, abstractmethod

class CmdPart(ABC):
    """Base class for command parts"""
    
    def __init__(self, prefix: Optional[str] = None, hardcoded: Optional[str] = None, 
                 container_member: Optional[str] = None, comment: Optional[str] = None):
        self.prefix = prefix
        self.hardcoded = hardcoded
        self.container_member = container_member
        self.comment = comment
        self.resolved_value = None
        self.error = None
    
    @abstractmethod
    def comment_str(self) -> str:
        """Return commented version for display"""
        pass
    
    @abstractmethod
    def execution_str(self) -> str:
        """Return executable version (no newlines)"""
        pass
    
    @abstractmethod
    def resolve(self, container_info) -> bool:
        """Resolve values and return True if successful, False if error"""
        pass

class CmdPartFlag(CmdPart):
    """Command part for boolean flags like --rm, --x11"""
    
    def __init__(self, flag_name: str, condition: bool = True, comment: Optional[str] = None):
        super().__init__(hardcoded=flag_name, comment=comment)
        self.condition = condition
    
    def comment_str(self) -> str:
        if self.condition:
            return f"#     {self.hardcoded}"
        return ""
    
    def execution_str(self) -> str:
        if self.condition:
            return self.hardcoded
        return ""
    
    def resolve(self, container_info) -> bool:
        # Flags don't need resolution
        return True

class CmdPartArg(CmdPart):
    """Command part for general arguments"""
    
    def __init__(self, arg_name: str, container_member: str, comment: Optional[str] = None):
        super().__init__(hardcoded=arg_name, container_member=container_member, comment=comment)
    
    def comment_str(self) -> str:
        if self.resolved_value:
            return f"#     {self.hardcoded} {self.resolved_value}"
        return ""
    
    def execution_str(self) -> str:
        if self.resolved_value:
            return f"{self.hardcoded} {self.resolved_value}"
        return ""
    
    def resolve(self, container_info) -> bool:
        if self.container_member:
            self.resolved_value = getattr(container_info, self.container_member, None)
            if self.resolved_value is None:
                self.error = f"Missing {self.container_member}"
                return False
        return True

class CmdPartMount(CmdPart):
    """Command part for volume mounts (-v)"""
    
    def __init__(self, host_path: str, container_path: str, comment: Optional[str] = None):
        super().__init__(hardcoded="-v", comment=comment)
        self.host_path = host_path
        self.container_path = container_path
        self.resolved_host_path = None
        self.resolved_container_path = None
    
    def comment_str(self) -> str:
        if self.resolved_host_path and self.resolved_container_path:
            return f"#     {self.hardcoded} {self.host_path}:{self.container_path}"
        return ""
    
    def execution_str(self) -> str:
        if self.resolved_host_path and self.resolved_container_path:
            return f"{self.hardcoded} {self.resolved_host_path}:{self.resolved_container_path}"
        return ""
    
    def resolve(self, container_info) -> bool:
        # Expand environment variables
        self.resolved_host_path = os.path.expandvars(self.host_path)
        self.resolved_container_path = os.path.expandvars(self.container_path)
        
        # Convert relative paths to absolute paths
        if not os.path.isabs(self.resolved_host_path):
            self.resolved_host_path = os.path.join(container_info.working_directory, self.resolved_host_path)
        
        # Verify host path exists (only for non-environment variable paths)
        if not self.host_path.startswith('$') and not os.path.exists(self.resolved_host_path):
            self.error = f"Mount host path does not exist: {self.host_path}"
            return False
        
        return True

class CmdPartEnv(CmdPart):
    """Command part for environment variables (-e)"""
    
    def __init__(self, env_name: str, env_value: str = None, container_member: str = None, comment: Optional[str] = None):
        super().__init__(hardcoded="-e", comment=comment)
        self.env_name = env_name
        self.env_value = env_value
        self.container_member = container_member
    
    def comment_str(self) -> str:
        if self.resolved_value:
            return f"#     {self.hardcoded} {self.env_name}={self.resolved_value}"
        return ""
    
    def execution_str(self) -> str:
        if self.resolved_value:
            return f"{self.hardcoded} {self.env_name}={self.resolved_value}"
        return ""
    
    def resolve(self, container_info) -> bool:
        if self.container_member:
            self.resolved_value = getattr(container_info, self.container_member, None)
            if self.resolved_value is None:
                self.error = f"Missing {self.container_member}"
                return False
        else:
            self.resolved_value = self.env_value
        return True

class CmdPartFile(CmdPart):
    """Command part for file paths with validation"""
    
    def __init__(self, arg_name: str = None, container_member: str = None, comment: Optional[str] = None):
        super().__init__(hardcoded=arg_name, container_member=container_member, comment=comment)
    
    def comment_str(self) -> str:
        if self.resolved_value:
            if self.hardcoded:
                return f"#     {self.hardcoded} {self.resolved_value}"
            else:
                return f"#     {self.resolved_value}"
        return ""
    
    def execution_str(self) -> str:
        if self.resolved_value:
            if self.hardcoded:
                return f"{self.hardcoded} {self.resolved_value}"
            else:
                return self.resolved_value
        return ""
    
    def resolve(self, container_info) -> bool:
        if self.container_member:
            self.resolved_value = getattr(container_info, self.container_member, None)
            if self.resolved_value is None:
                self.error = f"Missing {self.container_member}"
                return False
            
            # Verify file exists
            if not os.path.exists(self.resolved_value):
                self.error = f"File does not exist: {self.resolved_value}"
                return False
        
        return True

class CmdPartMounts(CmdPart):
    """Command part for multiple volume mounts (-v)"""
    
    def __init__(self, mounts: List[str], comment: Optional[str] = None):
        super().__init__(hardcoded="-v", comment=comment)
        self.mounts = mounts
        self.resolved_mounts = []
    
    def comment_str(self) -> str:
        lines = []
        for mount in self.mounts:
            lines.append(f"#     -v {mount}")
        return "\n".join(lines)
    
    def execution_str(self) -> str:
        parts = []
        for host_path, container_path in self.resolved_mounts:
            parts.append(f"-v {host_path}:{container_path}")
        return " ".join(parts)
    
    def resolve(self, container_info) -> bool:
        # Check for empty mounts when X11 is enabled
        if not self.mounts and container_info.x11_enabled:
            # Check if this is an X11-only mount list (no regular mounts)
            regular_mounts = container_info.mounts
            if not regular_mounts:
                self.error = "X11 is enabled but no mounts are configured"
                return False
        
        mount_errors = []
        
        for mount in self.mounts:
            if ':' not in mount:
                mount_errors.append(f"Invalid mount format '{mount}'")
                continue
            
            host_path, container_path = mount.split(':', 1)
            
            # Expand environment variables
            resolved_host_path = os.path.expandvars(host_path)
            resolved_container_path = os.path.expandvars(container_path)
            
            # Convert relative paths to absolute paths
            if not os.path.isabs(resolved_host_path):
                resolved_host_path = os.path.join(container_info.working_directory, resolved_host_path)
            
            # Verify host path exists (only for non-environment variable paths)
            if not host_path.startswith('$') and not os.path.exists(resolved_host_path):
                mount_errors.append(f"Mount host path does not exist: {host_path}")
                continue
            
            self.resolved_mounts.append((resolved_host_path, resolved_container_path))
        
        # If there are mount errors, combine them into a single error message
        if mount_errors:
            self.error = '; '.join(mount_errors)
            return False
        
        return True

class CmdPartX11Support(CmdPart):
    """Command part for X11 support (non-mount parts)"""
    
    def __init__(self, enabled: bool, comment: Optional[str] = None):
        super().__init__(comment=comment)
        self.enabled = enabled
        self.x11_args = []
    
    def comment_str(self) -> str:
        """Return commented version with example values"""
        if self.enabled and self.x11_args:
            lines = []
            lines.append("#     -e DISPLAY=:0")
            return "\n".join(lines)
        return ""
    
    def execution_str(self) -> str:
        """Return executable version with resolved values"""
        if self.enabled and self.x11_args:
            return " ".join(self.x11_args)
        return ""
    
    def resolve(self, container_info) -> bool:
        if not self.enabled:
            return True
        
        # Only add DISPLAY environment variable (networking is handled separately)
        display = os.environ.get('DISPLAY', ':0')
        self.x11_args = [
            f"-e DISPLAY={display}"
        ]
        return True

class CmdPartHostNetworking(CmdPart):
    """Command part for host networking (always enabled)"""
    
    def __init__(self, comment: Optional[str] = None):
        super().__init__(comment=comment)
    
    def comment_str(self) -> str:
        return "#     --net=host"
    
    def execution_str(self) -> str:
        return "--net=host"
    
    def resolve(self, container_info) -> bool:
        return True

class CmdPartHardcoded(CmdPart):
    """Command part for hardcoded values"""
    
    def __init__(self, value: str, comment: Optional[str] = None):
        super().__init__(hardcoded=value, comment=comment)
    
    def comment_str(self) -> str:
        return f"#     {self.hardcoded}"
    
    def execution_str(self) -> str:
        return self.hardcoded
    
    def resolve(self, container_info) -> bool:
        # Hardcoded values don't need resolution
        return True

class CmdPartShmSize(CmdPart):
    """Command part for shared memory size parameter"""
    
    def __init__(self, size: str, comment: Optional[str] = None):
        super().__init__(hardcoded=f"--shm-size={size}", comment=comment)
        self.size = size
    
    def comment_str(self) -> str:
        return f"#     {self.hardcoded}"
    
    def execution_str(self) -> str:
        return self.hardcoded
    
    def resolve(self, container_info) -> bool:
        return True

class CmdPartName(CmdPart):
    """Command part for container/image names"""
    
    def __init__(self, container_member: str, comment: Optional[str] = None, check_image_exists: bool = False):
        super().__init__(container_member=container_member, comment=comment)
        self.check_image_exists = check_image_exists
    
    def comment_str(self) -> str:
        if self.resolved_value:
            return f"#     {self.resolved_value}"
        return ""
    
    def execution_str(self) -> str:
        if self.resolved_value:
            return self.resolved_value
        return ""
    
    def resolve(self, container_info) -> bool:
        if self.container_member:
            self.resolved_value = getattr(container_info, self.container_member, None)
            if self.resolved_value is None:
                self.error = f"Missing {self.container_member}"
                return False
            
            # Check if image exists (for run command)
            if self.check_image_exists and not self._check_image_exists(self.resolved_value):
                self.error = f"Image '{self.resolved_value}' not found locally. Try: docker pull {self.resolved_value}"
                return False
        return True
    
    def _check_image_exists(self, image_name):
        """Check if Docker image exists"""
        try:
            import subprocess
            result = subprocess.run(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'], 
                                   capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                images = [img.strip() for img in result.stdout.strip().split('\n') if img.strip()]
                return image_name in images
            return False
        except Exception:
            return False

class CommandBuilder:
    """Builder class for Docker commands"""
    
    def __init__(self, command_type: str):
        self.command_type = command_type
        self.cmd_parts: Dict[str, CmdPart] = {}
        self.base_command = []
    
    def set_base_command(self, command_parts: List[str]):
        """Set the base command (e.g., ['docker', 'run', '-dit'])"""
        self.base_command = command_parts
    
    def add_part(self, name: str, cmd_part: CmdPart):
        """Add a CmdPart to the builder"""
        self.cmd_parts[name] = cmd_part
    
    def build_command(self, container_info) -> Tuple[str, str, List[str]]:
        """
        Build command and return (commented_str, execution_str, errors)
        """
        errors = []
        
        # Resolve all parts
        for name, part in self.cmd_parts.items():
            if not part.resolve(container_info):
                if part.error:
                    errors.append(part.error)
        
        # If there are errors, return error message
        if errors:
            commented_str = self._build_commented_command()
            execution_str = f"echo 'error: {'; '.join(errors)}'"
            return commented_str, execution_str, errors
        
        # Build successful command
        commented_str = self._build_commented_command()
        execution_str = self._build_execution_command()
        
        return commented_str, execution_str, []
    
    def _build_commented_command(self) -> str:
        """Build the commented version of the command"""
        lines = []
        
        # Add header
        lines.append(f"# Docker {self.command_type} Command:")
        lines.append("# " + "=" * 50)
        
        # Add base command
        if self.base_command:
            lines.append(f"# {' '.join(self.base_command)}")
        
        # Add all parts
        for name, part in self.cmd_parts.items():
            comment_line = part.comment_str()
            if comment_line:
                if part.comment and "\n" not in comment_line:
                    # Single line with comment
                    lines.append(f"{comment_line} {part.comment}")
                elif part.comment and "\n" in comment_line:
                    # Multi-line with comment - add comment to last line
                    comment_lines = comment_line.split("\n")
                    for i, line in enumerate(comment_lines):
                        if i == len(comment_lines) - 1 and line.strip():
                            lines.append(f"{line} {part.comment}")
                        else:
                            lines.append(line)
                else:
                    # No comment, just add the line(s)
                    lines.append(comment_line)
        
        # Add footer
        lines.append("# " + "=" * 50)
        lines.append("")
        lines.append("# Executable command:")
        
        return "\n".join(lines)
    
    def _build_execution_command(self) -> str:
        """Build the executable version of the command"""
        parts = []
        
        # Add base command
        parts.extend(self.base_command)
        
        # Add all parts
        for name, part in self.cmd_parts.items():
            execution_part = part.execution_str()
            if execution_part:
                parts.append(execution_part)
        
        return " ".join(parts)

def print_command_header(command_type):
    """Print standardized command header"""
    print(f"# Docker {command_type} Command:")
    print("# " + "=" * 50)

def print_command_footer():
    """Print standardized command footer"""
    print("# " + "=" * 50)
    print()
    print("# Executable command:")

def print_aligned_comment(text, comment_text, comment_column):
    """Print a line with aligned comment"""
    print(f"{text}{' ' * (comment_column - len(text))}{comment_text}")
