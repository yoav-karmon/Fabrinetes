#!/usr/bin/env python3
"""
Vivado Property Management for HDLForge
Executes set_property commands in Vivado and updates JSON from XPR
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Tuple
from update_sources_from_xpr import update_sources_from_xpr


def run_vivado_set_property(
    xpr_file: Path,
    set_property_command: str,
    verbose: bool = True
) -> Tuple[bool, str]:
    """
    Run Vivado set_property command in batch mode.
    
    Args:
        xpr_file: Path to .xpr file
        set_property_command: Raw TCL set_property command (e.g., "set_property -name FILE_TYPE -value SystemVerilog -objects [get_files watch_dog.sv]")
        verbose: If True, print output to screen
    
    Returns:
        Tuple of (success: bool, output: str)
    """
    if not xpr_file.exists():
        return False, f"XPR file not found: {xpr_file}"
    
    # Create temporary TCL script
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tcl', delete=False) as f:
        tcl_script = f.name
        # Write commands
        f.write("# Vivado set_property command\n")
        f.write(f"open_project {xpr_file}\n")
        f.write("\n# User set_property command\n")
        f.write(f"{set_property_command}\n")
        f.write("\n# Close project\n")
        f.write("close_project\n")
        f.write("exit 0\n")
    
    try:
        # Run Vivado in batch mode
        cmd = [
            "vivado",
            "-mode", "batch",
            "-source", tcl_script,
            "-notrace"
        ]
        
        if verbose:
            print(f"[i] Running Vivado set_property command:")
            print(f"    {set_property_command}")
            print()
        
        # Run and capture output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=str(xpr_file.parent)
        )
        
        output_lines = []
        # Print output to screen in real-time
        if verbose:
            print("=" * 80)
            print("Vivado Output:")
            print("=" * 80)
        
        for line in process.stdout:
            line = line.rstrip()
            output_lines.append(line)
            if verbose:
                print(line)
        
        if verbose:
            print("=" * 80)
        
        process.wait()
        output = '\n'.join(output_lines)
        
        # Check for success
        success = process.returncode == 0
        
        # Check for common error patterns
        if not success or "ERROR" in output.upper() or "CRITICAL" in output.upper():
            # Look for specific error messages
            error_lines = [line for line in output_lines 
                          if 'ERROR' in line.upper() or 'CRITICAL' in line.upper()]
            if error_lines:
                error_msg = '\n'.join(error_lines[:5])  # First 5 error lines
                return False, f"Vivado errors:\n{error_msg}"
        
        return success, output
        
    finally:
        # Clean up temp file
        try:
            os.unlink(tcl_script)
        except:
            pass


def set_property(
    project_loader,
    set_property_command: str,
    verbose: bool = True
) -> bool:
    """
    Execute a set_property command in the Vivado project.
    
    Args:
        project_loader: ProjectLoader instance
        set_property_command: Raw TCL set_property command (e.g., "set_property -name FILE_TYPE -value SystemVerilog -objects [get_files watch_dog.sv]")
        verbose: Print output to screen
    
    Returns:
        True if successful, False otherwise
    """
    xpr_file = project_loader.vivado_project_xpr_path
    
    if not xpr_file.exists():
        print(f"[!x!] Project file not found: {xpr_file}")
        return False
    
    # Run command
    success, output = run_vivado_set_property(xpr_file, set_property_command, verbose)
    
    if success:
        print("[+] Property set successfully")
        # Update sources from XPR
        print("[i] Updating sources from XPR...")
        if update_sources_from_xpr(project_loader, xpr_file, project_loader.working_path):
            project_loader.save_project_data()
            print("[+] Sources updated in project file")
        else:
            print("[!] Failed to update sources from XPR")
    else:
        print(f"[!x!] Failed to set property: {output}")
    
    return success


def main():
    """CLI interface for set_property command"""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  set_property <project.xpr> <set_property_command>")
        print("  Example: set_property project.xpr 'set_property -name FILE_TYPE -value SystemVerilog -objects [get_files watch_dog.sv]'")
        sys.exit(1)
    
    xpr_file = Path(sys.argv[1])
    set_property_command = sys.argv[2]
    
    success, output = run_vivado_set_property(xpr_file, set_property_command, verbose=True)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

