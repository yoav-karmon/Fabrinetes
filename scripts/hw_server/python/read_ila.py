#!/usr/bin/env python3
"""
ILA Value Reader (Python)

This script reads ILA (Integrated Logic Analyzer) values from an FPGA
by programming it with a bitstream and reading probe data.

Usage:
    python3 read_ila.py [server_ip] [bit_file] [ltx_file]
    python3 read_ila.py [server_ip] [project_json]

Arguments:
    server_ip (optional): Hardware server IP address (default: 10.1.130.74)
    bit_file (optional): Path to bitstream file (.bit)
    ltx_file (optional): Path to probe file (.ltx)
    project_json (optional): Path to project JSON file (e.g., phy10gbaser.hdlforge.json)
"""

import subprocess
import sys
import time
import os
import select
import pty
import re
import json
import glob
from pathlib import Path

try:
    from tabulate import tabulate
except ImportError:
    print("ERROR: tabulate library not found. Install with: pip install tabulate")
    sys.exit(1)


class VivadoTCLConsole:
    """Wrapper for communicating with Vivado TCL console via subprocess."""
    
    def __init__(self):
        """Initialize Vivado TCL console process."""
        self.process = None
        self.master_fd = None
        self.prompt = "Vivado% "
        
    def start(self) -> bool:
        """Start Vivado in TCL mode using pty for prompt detection."""
        try:
            self.master_fd, slave_fd = pty.openpty()
            self.process = subprocess.Popen(
                ['vivado', '-mode', 'tcl', '-nolog', '-nojournal'],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                bufsize=1,
                start_new_session=True
            )
            os.close(slave_fd)
            self._read_output(timeout=10, wait_for_prompt=True)
            return True
        except FileNotFoundError:
            print("ERROR: Vivado not found. Please ensure Vivado is in PATH.")
            return False
        except Exception as e:
            print(f"ERROR: Failed to start Vivado: {e}")
            return False
    
    def send_command(self, command: str, timeout: float = 30.0) -> str:
        """Send a TCL command and wait for response."""
        if not self.process:
            return ""
        if self.process.poll() is not None:
            raise RuntimeError(f"Vivado process terminated unexpectedly. Exit code: {self.process.returncode}")
        
        os.write(self.master_fd, (command + '\n').encode())
        output = self._read_output(timeout=timeout, wait_for_prompt=True)
        
        if self.process.poll() is not None:
            raise RuntimeError(f"Vivado process terminated during command execution. Exit code: {self.process.returncode}")
        return output
    
    def _read_output(self, timeout: float = 30.0, wait_for_prompt: bool = True) -> str:
        """Read output until prompt appears, return cleaned output."""
        if not self.process or not self.master_fd:
            return ""
        
        raw_output = ""
        start_time = time.time()
        prompt_found = False
        
        while time.time() - start_time < timeout:
            if self.process.poll() is not None:
                try:
                    remaining = os.read(self.master_fd, 4096).decode('utf-8', errors='replace')
                    if remaining:
                        raw_output += remaining
                except:
                    pass
                break
            
            ready, _, _ = select.select([self.master_fd], [], [], 0.1)
            
            if ready and self.master_fd in ready:
                try:
                    data = os.read(self.master_fd, 4096).decode('utf-8', errors='replace')
                    if data:
                        raw_output += data
                        
                        if wait_for_prompt and self.prompt in raw_output:
                            prompt_found = True
                            break
                except Exception:
                    pass
        
        if not prompt_found and wait_for_prompt:
            print(f"\nWARNING: Timeout after {timeout:.1f}s", file=sys.stderr)
        
        return self._clean_output(raw_output)
    
    def _clean_output(self, raw_output: str) -> str:
        """Clean output: remove prompts, carriage returns, and fix formatting."""
        cleaned = raw_output.replace(self.prompt, '').replace('\r', '')
        lines = cleaned.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if line.lstrip().startswith('#'):
                continue
            if stripped.startswith('INFO:'):
                continue
            if any(stripped.startswith(cmd) for cmd in ['puts ', 'set ', 'source ', 'program_hw_devices', 'read_hw_ila_data']):
                continue
            if len(stripped.split()) == 1 and not any(c in stripped for c in [':', '=', '-', '/', '*']):
                continue
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def close(self):
        """Close Vivado TCL console."""
        if self.process:
            try:
                if self.master_fd:
                    os.write(self.master_fd, b'exit\n')
                self.process.wait(timeout=2)
            except:
                self.process.terminate()
            self.process = None
        if self.master_fd:
            os.close(self.master_fd)
            self.master_fd = None


def find_bit_ltx_files(project_json_path: str):
    """Find bitstream and probe files from project JSON."""
    with open(project_json_path, 'r') as f:
        config = json.load(f)
    
    vivado_config = config.get('vivado', {}).get('config', {})
    project_name = vivado_config.get('project_name', 'phy10gbaser')
    build_dir = vivado_config.get('build_dir', '_vivado')
    
    # Resolve paths
    json_dir = os.path.dirname(os.path.abspath(project_json_path))
    project_path = os.path.join(json_dir, build_dir, project_name)
    
    # Try default paths
    default_bit_pattern = os.path.join(project_path, f"{project_name}.runs", "synth_1", "impl_1", "*.bit")
    default_ltx_pattern = os.path.join(project_path, f"{project_name}.runs", "synth_1", "impl_1", "*.ltx")
    
    bit_files = glob.glob(default_bit_pattern)
    ltx_files = glob.glob(default_ltx_pattern)
    
    # Also check user-added paths
    user_bit_paths = vivado_config.get('bitstream_paths', {}).get('user_added', [])
    user_ltx_paths = vivado_config.get('probe_paths', {}).get('user_added', [])
    
    for path in user_bit_paths:
        resolved = path.replace('${build_dir}', build_dir).replace('${project_name}', project_name)
        full_path = os.path.join(json_dir, resolved)
        if os.path.exists(full_path):
            bit_files.append(full_path)
    
    for path in user_ltx_paths:
        resolved = path.replace('${build_dir}', build_dir).replace('${project_name}', project_name)
        full_path = os.path.join(json_dir, resolved)
        if os.path.exists(full_path):
            ltx_files.append(full_path)
    
    return bit_files, ltx_files


def parse_ila_values(output: str):
    """Parse ILA probe values from output."""
    probes = []
    current_probe = None
    
    for line in output.split('\n'):
        line = line.strip()
        # Look for "probe_name: value" pattern
        match = re.match(r'^(.+?):\s*(.+)$', line)
        if match:
            probe_name = match.group(1).strip()
            probe_value = match.group(2).strip()
            probes.append({'name': probe_name, 'value': probe_value})
    
    return probes


def display_ila_table(probes):
    """Display ILA probe values in a table."""
    if not probes:
        print("\nNo ILA probe values found.")
        return
    
    print("\nILA Probe Values:")
    table = [[i+1, p['name'], p['value']] for i, p in enumerate(probes)]
    print(tabulate(table, headers=['#', 'Probe Name', 'Value'], tablefmt='grid'))


def main():
    """Main entry point."""
    
    # Parse arguments
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "10.1.130.74"
    bit_file = sys.argv[2] if len(sys.argv) > 2 else None
    ltx_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    # If only 2 args and second is a JSON file, use it
    if len(sys.argv) == 3 and sys.argv[2].endswith('.json'):
        project_json = sys.argv[2]
        bit_files, ltx_files = find_bit_ltx_files(project_json)
        if not bit_files:
            print(f"ERROR: No bitstream files found for project {project_json}")
            sys.exit(1)
        if not ltx_files:
            print(f"ERROR: No probe files found for project {project_json}")
            sys.exit(1)
        bit_file = bit_files[0]
        ltx_file = ltx_files[0]
        print(f"Using bitstream: {bit_file}")
        print(f"Using probe file: {ltx_file}")
    
    if not bit_file or not ltx_file:
        print("ERROR: Both bitstream and probe files are required")
        print("Usage: python3 read_ila.py [server_ip] [bit_file] [ltx_file]")
        print("   or: python3 read_ila.py [server_ip] [project_json]")
        sys.exit(1)
    
    if not os.path.exists(bit_file):
        print(f"ERROR: Bitstream file not found: {bit_file}")
        sys.exit(1)
    
    if not os.path.exists(ltx_file):
        print(f"ERROR: Probe file not found: {ltx_file}")
        sys.exit(1)
    
    print("=" * 50)
    print("ILA Value Reader")
    print("=" * 50)
    print(f"Server IP: {server_ip}")
    print(f"Bitstream: {bit_file}")
    print(f"Probe file: {ltx_file}")
    print()
    
    # Get script directory to find TCL helper files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tcl_dir = os.path.join(os.path.dirname(script_dir), 'tcl')
    
    console = VivadoTCLConsole()
    try:
        if not console.start():
            sys.exit(1)
        
        # Source TCL helper files
        tcl_script_dir = tcl_dir.replace('\\', '/')
        console.send_command(f'set script_dir "{tcl_script_dir}"; source [file join $script_dir hw_server_helpers.tcl]')
        console.send_command('source [file join $script_dir ila_helpers.tcl]')
        
        # Initialize hardware server
        console.send_command(f'set hw_server_ip {server_ip}')
        output = console.send_command('set hw_device [init_hw_server $hw_server_ip]')
        
        # Read ILA values
        bit_file_abs = os.path.abspath(bit_file).replace('\\', '/')
        ltx_file_abs = os.path.abspath(ltx_file).replace('\\', '/')
        
        output = console.send_command(f'set probe_values [read_ila_values $hw_device "{bit_file_abs}" "{ltx_file_abs}"]')
        
        # Display values
        output = console.send_command('display_ila_values $probe_values')
        
        # Parse and display in table
        probes = parse_ila_values(output)
        display_ila_table(probes)
        
        print("\nScript completed")
        
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        console.close()


if __name__ == "__main__":
    main()


