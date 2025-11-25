#!/usr/bin/env python3
"""
Hardware Server Connection and Chip DNA Reader (Python)

This script connects to a Vivado hardware server, refreshes the target,
and reads the chip DNA value by communicating with Vivado TCL console.

Usage:
    python3 connect_and_read_dna.py [server_ip]

Arguments:
    server_ip (optional): Hardware server IP address (default: 10.1.130.74)
"""

import subprocess
import sys
import time
import os
import select
import pty
import re
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
                        
                        # Check for prompt
                        if wait_for_prompt and self.prompt in raw_output:
                            prompt_found = True
                            break
                except Exception:
                    pass
        
        if not prompt_found and wait_for_prompt:
            print(f"\nWARNING: Timeout after {timeout:.1f}s", file=sys.stderr)
        
        # Clean and return output
        return self._clean_output(raw_output)
    
    def _clean_output(self, raw_output: str) -> str:
        """Clean output: remove prompts, carriage returns, and fix formatting."""
        # Remove prompts
        cleaned = raw_output.replace(self.prompt, '')
        # Remove carriage returns
        cleaned = cleaned.replace('\r', '')
        
        # Split into lines and filter
        lines = cleaned.split('\n')
        filtered_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip empty lines
            if not stripped:
                continue
            # Skip lines starting with # (TCL comments/source code)
            if line.lstrip().startswith('#'):
                continue
            # Skip INFO messages
            if stripped.startswith('INFO:'):
                continue
            # Skip command echoes
            if any(stripped.startswith(cmd) for cmd in ['puts ', 'set ', 'source ', 'lassign ', 'display_dna_result']):
                continue
            # Skip lines that are just variable names or single return values
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


def parse_hw_targets(output: str):
    """Parse hardware targets from output."""
    targets = []
    in_targets = False
    for line in output.split('\n'):
        if 'Found' in line and 'hardware target' in line:
            in_targets = True
            continue
        if in_targets and line.strip().startswith('- '):
            target_name = line.strip()[2:].strip()
            targets.append(target_name)
        elif in_targets and line.strip() and not line.strip().startswith('-'):
            break
    return targets


def parse_hw_devices(output: str):
    """Parse hardware devices from output."""
    devices = []
    in_devices = False
    for line in output.split('\n'):
        if 'Found' in line and 'hardware device' in line:
            in_devices = True
            continue
        if in_devices and line.strip().startswith('- '):
            device_info = line.strip()[2:].strip()
            # Parse "device_name (type)" format
            match = re.match(r'^(.+?)\s*\((.+?)\)$', device_info)
            if match:
                devices.append({'name': match.group(1), 'type': match.group(2)})
            else:
                devices.append({'name': device_info, 'type': 'unknown'})
        elif in_devices and line.strip() and not line.strip().startswith('-'):
            break
    return devices


def parse_dna_results(output: str):
    """Parse DNA results from output."""
    dna_results = {}
    current_slr = None
    
    for line in output.split('\n'):
        line = line.strip()
        # Check for SLR entries
        slr_match = re.match(r'^SLR(\d+):\s*(.+)$', line)
        if slr_match:
            slr_num = slr_match.group(1)
            dna_value = slr_match.group(2).strip()
            dna_results[f'SLR{slr_num}'] = dna_value
        # Check for primary DNA
        elif 'Primary DNA' in line:
            match = re.search(r'Primary DNA.*?:\s*([0-9A-Fa-f]+)', line)
            if match:
                dna_results['Primary'] = match.group(1)
        # Check for single DNA (non-SLR)
        elif 'Chip DNA' in line and 'REGISTER.EFUSE.FUSE_DNA' in line:
            match = re.search(r':\s*([0-9A-Fa-f]+)', line)
            if match:
                dna_results['Primary'] = match.group(1)
    
    return dna_results


def display_hw_info(targets, devices):
    """Display hardware information in tables."""
    if targets:
        print("\nHardware Targets:")
        table = [[i+1, target] for i, target in enumerate(targets)]
        print(tabulate(table, headers=['#', 'Target'], tablefmt='grid'))
    
    if devices:
        print("\nHardware Devices:")
        table = [[i+1, d['name'], d['type']] for i, d in enumerate(devices)]
        print(tabulate(table, headers=['#', 'Device Name', 'Type'], tablefmt='grid'))


def display_dna_results(dna_results):
    """Display DNA results in a table."""
    if not dna_results:
        print("\nNo DNA data found.")
        return
    
    print("\nChip DNA Results:")
    table = []
    for key, value in sorted(dna_results.items()):
        table.append([key, value])
    
    print(tabulate(table, headers=['Source', 'DNA Value'], tablefmt='grid'))


def main():
    """Main entry point - matches TCL script structure exactly."""
    
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "10.1.130.74"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tcl_dir = os.path.join(os.path.dirname(script_dir), 'tcl')
    
    print("=" * 50)
    print("Hardware Server Connection Script")
    print("=" * 50)
    print(f"Server IP: {server_ip}")
    
    console = VivadoTCLConsole()
    try:
        if not console.start():
            sys.exit(1)
        
        tcl_script_dir = tcl_dir.replace('\\', '/')
        console.send_command(f'set script_dir "{tcl_script_dir}"; source [file join $script_dir hw_server_helpers.tcl]')
        console.send_command('source [file join $script_dir dna_helpers.tcl]')
        console.send_command(f'set hw_server_ip {server_ip}')
        
        # Get hardware initialization output
        output = console.send_command('set hw_device [init_hw_server $hw_server_ip]')
        
        # Parse and display hardware info
        targets = parse_hw_targets(output)
        devices = parse_hw_devices(output)
        display_hw_info(targets, devices)
        
        # Get DNA results
        console.send_command('lassign [read_chip_dna $hw_device] chip_dna all_dna_values')
        output = console.send_command('display_dna_result $chip_dna $all_dna_values $hw_device')
        
        # Parse and display DNA results
        dna_results = parse_dna_results(output)
        display_dna_results(dna_results)
        
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
