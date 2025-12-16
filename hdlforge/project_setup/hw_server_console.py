#!/usr/bin/env python3
"""
Vivado TCL Console - Core communication and hardware operations.

Provides the VivadoTCLConsole class for interacting with Vivado hardware manager.
"""

import os
import pty
import re
import select
import subprocess
import sys
import time
from typing import Optional, List, Dict

from hw_server_tables import print_ila_table, print_ila_triggers_table, print_vio_table


class VivadoTCLConsole:
    """Wrapper for communicating with Vivado TCL console via subprocess."""
    
    def __init__(self, working_dir: str = None, debug: bool = False):
        """Initialize Vivado TCL console process.
        
        Args:
            working_dir: Directory to launch Vivado from (for logs). Defaults to current dir.
            debug: If True, print debug output showing TCL commands and inputs.
        """
        self.process = None
        self.master_fd = None
        self.prompt = "Vivado% "
        self.connected = False
        self.hw_server_host = None
        self.hw_server_port = None
        self.device = None
        self.target = None
        self.working_dir = working_dir or os.getcwd()
        self.debug = debug
        # Unified cache for scanned ILA/VIO data: {'i0': {...}, 'i1': {...}, 'v0': {...}, 'v1': {...}}
        self.core_cache: Dict[str, Dict] = {}
        self.scanned = False  # Whether ILA/VIO have been scanned
    
    def _get_ila_list(self) -> List[Dict]:
        """Get list of ILA cores from cache."""
        return [v for k, v in sorted(self.core_cache.items()) if v.get('type') == 'ila']
    
    def _get_vio_list(self) -> List[Dict]:
        """Get list of VIO cores from cache."""
        return [v for k, v in sorted(self.core_cache.items()) if v.get('type') == 'vio']
    
    def _get_core_by_key(self, key: str) -> Dict:
        """Get core data by cache key (e.g., 'i0', 'v1')."""
        return self.core_cache.get(key, {})
    
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
                start_new_session=True,
                cwd=self.working_dir  # Launch from specified directory for logs
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
    
    def get_property_value(self, property_name: str, object_name: str, timeout: float = 2.0) -> str:
        """Get a property value and extract just the value (not the command echo)."""
        output = self.send_command(f"get_property {property_name} {object_name}", timeout=timeout)
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        filtered = [line for line in lines 
                   if not line.startswith('#') 
                   and not line.startswith('get_property') 
                   and not line.startswith('ERROR:')
                   and not line.startswith('WARNING:')]
        if filtered:
            return filtered[-1]
        return ""
    
    def send_command(self, command: str, timeout: float = 30.0, wait_for_prompt: bool = True) -> str:
        """Send a TCL command and wait for response."""
        if not self.process:
            return ""
        if self.process.poll() is not None:
            raise RuntimeError(f"Vivado process terminated unexpectedly. Exit code: {self.process.returncode}")
        
        # Debug output - show the TCL command
        if self.debug:
            print(f"[DEBUG TCL] {command}")
        
        os.write(self.master_fd, (command + '\n').encode())
        output = self._read_output(timeout=timeout, wait_for_prompt=wait_for_prompt)
        
        # Check for errors in output
        error_lines = []
        for line in output.split('\n'):
            line_stripped = line.strip()
            if 'ERROR:' in line_stripped or 'ERROR [' in line_stripped:
                error_lines.append(line_stripped)
        
        # Debug output - show the actual output/result
        if self.debug and output:
            # Get raw output before cleaning to show actual Vivado response
            # We need to read it again or store it before cleaning
            # For now, show the cleaned output which should have the result
            output_lines = [line.strip() for line in output.split('\n') if line.strip()]
            # Filter out command echoes and show actual results
            result_lines = [line for line in output_lines 
                          if not line.startswith(command.split()[0])  # Don't echo the command
                          and not line.startswith('#')
                          and not line.startswith('INFO:')
                          and not line.startswith('WARNING:')]
            if result_lines:
                for line in result_lines:
                    print(f"[DEBUG TCL]   -> {line}")
        
        # Show errors in debug mode
        if self.debug and error_lines:
            for error_line in error_lines:
                print(f"[DEBUG TCL]   ERROR: {error_line}")
        
        if self.process.poll() is not None:
            raise RuntimeError(f"Vivado process terminated during command execution. Exit code: {self.process.returncode}")
        
        # Return output with error indication
        if error_lines:
            # Mark output as having errors (caller can check for "ERROR:" in output)
            return output
        
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
            if stripped.startswith('INFO:') or stripped.startswith('WARNING:'):
                continue
            if any(stripped.startswith(cmd) for cmd in ['puts ', 'source ', 'lassign ', 'get_property ']):
                continue
            if 'ERROR:' in stripped or '[Labtoolstcl' in stripped or 'does not have' in stripped:
                continue
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def connect_hw_server(self, host: str, port: str) -> bool:
        """Connect to hardware server and initialize hardware."""
        try:
            self.hw_server_host = host
            self.hw_server_port = port
            
            self.send_command("open_hw_manager", timeout=5)
            
            hw_server_url = f"{host}:{port}"
            output = self.send_command(f"connect_hw_server -url {hw_server_url}", timeout=10)
            
            if "ERROR" in output or "error" in output.lower():
                print(f"ERROR: Failed to connect to hw_server at {hw_server_url}")
                return False
            
            output = self.send_command("set targets [get_hw_targets]", timeout=5)
            target_count_output = self.send_command("llength $targets", timeout=2)
            target_count = target_count_output.strip().split()[-1].strip()
            
            try:
                count = int(target_count)
                if count == 0:
                    print("ERROR: No hardware targets found")
                    return False
            except:
                pass
            
            output = self.send_command("set target [lindex $targets 0]", timeout=2)
            target_name = self.get_property_value("NAME", "$target", timeout=2)
            self.target = target_name
            
            output = self.send_command(f"open_hw_target $target", timeout=10)
            
            output = self.send_command("set devices [get_hw_devices]", timeout=5)
            device_count_output = self.send_command("llength $devices", timeout=2)
            device_count = device_count_output.strip().split()[-1].strip()
            
            try:
                count = int(device_count)
                if count == 0:
                    print("ERROR: No devices found on target")
                    return False
            except:
                pass
            
            output = self.send_command("set device [lindex $devices 0]", timeout=2)
            device_name = self.get_property_value("NAME", "$device", timeout=2)
            self.device = device_name
            
            self.send_command("current_hw_device $device", timeout=2)
            
            self.connected = True
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to connect to hardware server: {e}")
            return False
    
    def program_fpga(self, bit_file: str, ltx_file: Optional[str] = None) -> bool:
        """Program FPGA with bit file and optionally attach debug probe."""
        if not self.connected:
            print("ERROR: Not connected to hardware server")
            return False
        
        if not os.path.exists(bit_file):
            print(f"ERROR: Bit file not found: {bit_file}")
            return False
        
        try:
            bit_file_abs = os.path.abspath(bit_file).replace('\\', '/')
            print(f"Programming bit file: {bit_file_abs}")
            
            self.send_command(f'set bit_file_path "{bit_file_abs}"', timeout=2)
            output = self.send_command('set_property PROGRAM.FILE $bit_file_path $device', timeout=5)
            
            output = self.send_command("program_hw_devices $device", timeout=60)
            
            if "ERROR" in output or "error" in output.lower():
                print(f"ERROR: Failed to program FPGA: {output}")
                return False
            
            if ltx_file and os.path.exists(ltx_file):
                ltx_file_abs = os.path.abspath(ltx_file).replace('\\', '/')
                print(f"Attaching debug probe: {ltx_file_abs}")
                
                self.send_command(f'set ltx_file_path "{ltx_file_abs}"', timeout=2)
                self.send_command('set_property PROBES.FILE $ltx_file_path $device', timeout=5)
                self.send_command('set_property FULL_PROBES.FILE $ltx_file_path $device', timeout=5)
                
                self.send_command("refresh_hw_device $device", timeout=10)
            
            print("FPGA programming completed successfully")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to program FPGA: {e}")
            return False
    
    def scan_ila_vio(self, ltx_file: str) -> bool:
        """Scan for ILA and VIO instances and store in memory. ltx_file is REQUIRED."""
        if not self.connected:
            print("ERROR: Not connected to hardware server")
            return False
        
        if not ltx_file:
            print("ERROR: ltx_file is REQUIRED for ILA/VIO scanning")
            return False
        
        if not os.path.exists(ltx_file):
            print(f"ERROR: Debug probe file not found: {ltx_file}")
            return False
        
        try:
            ltx_file_abs = os.path.abspath(ltx_file).replace('\\', '/')
            print(f"Loading debug probe file: {ltx_file_abs}")
            
            self.send_command(f'set ltx_file_path "{ltx_file_abs}"', timeout=2)
            self.send_command('set_property PROBES.FILE $ltx_file_path $device', timeout=5)
            self.send_command('set_property FULL_PROBES.FILE $ltx_file_path $device', timeout=5)
            self.send_command("refresh_hw_device $device", timeout=10)
            print("Debug probe file loaded successfully\n")
            
            # Scan and store ILA/VIO (just list, no tables)
            self._store_ila_list()
            self._store_vio_list()
            self.scanned = True
            
            # Print summary list
            print("=" * 50)
            print("ILA/VIO Scan Complete")
            print("=" * 50)
            
            ila_list = self._get_ila_list()
            if ila_list:
                print(f"\nILA cores ({len(ila_list)}):")
                for i, ila in enumerate(ila_list):
                    print(f"  {i+1}. {ila['name']} (depth: {ila['depth']}, probes: {ila['probe_count']})")
            else:
                print("\nNo ILA cores found")
            
            vio_list = self._get_vio_list()
            if vio_list:
                print(f"\nVIO cores ({len(vio_list)}):")
                for i, vio in enumerate(vio_list):
                    print(f"  {i+1}. {vio['name']} (probes: {vio['probe_count']})")
            else:
                print("\nNo VIO cores found")
            
            print("\n" + "=" * 50)
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to scan ILA/VIO: {e}")
            return False
    
    def _store_ila_list(self) -> None:
        """Scan and store ILA instance list in unified cache."""
        output = self.send_command("set ila_cores [get_hw_ilas]", timeout=10)
        
        ila_count_output = self.send_command("llength $ila_cores", timeout=2)
        ila_count = ila_count_output.strip().split()[-1].strip()
        try:
            count = int(ila_count)
            for i in range(count):
                self.send_command(f"set ila [lindex $ila_cores {i}]", timeout=2)
                ila_name = self.get_property_value("NAME", "$ila", timeout=2)
                cell_name = self.get_property_value("CELL_NAME", "$ila", timeout=2)
                ila_depth = self.get_property_value("C_DATA_DEPTH", "$ila", timeout=2)
                depth_str = ila_depth if ila_depth and not ila_depth.startswith("ERROR") else "unknown"
                device = self.device or "xcvu9p_0"
                
                # Get probe count and names
                self.send_command("set ila_probes [get_hw_probes -of_objects $ila]", timeout=5)
                num_probes_output = self.send_command("llength $ila_probes", timeout=2)
                try:
                    probe_count = int(num_probes_output.strip().split()[-1].strip())
                except:
                    probe_count = 0
                
                # Get probe names
                probe_names = []
                for j in range(min(probe_count, 50)):
                    self.send_command(f"set probe [lindex $ila_probes {j}]", timeout=2)
                    probe_name = self.get_property_value("NAME", "$probe", timeout=2)
                    if probe_name:
                        probe_names.append(probe_name)
                
                cache_key = f"i{i}"
                self.core_cache[cache_key] = {
                    'type': 'ila',
                    'index': i,
                    'name': ila_name,
                    'cell_name': cell_name,
                    'device': device,
                    'depth': depth_str,
                    'probe_count': probe_count,
                    'probe_names': probe_names,
                    'refreshed': False,  # Track if ILA data has been refreshed
                    'status': 'NOT TRIGGERED'
                }
        except:
            pass
    
    def _store_vio_list(self) -> None:
        """Scan and store VIO instance list in unified cache."""
        output = self.send_command("set vio_cores [get_hw_vios]", timeout=10)
        
        vio_count_output = self.send_command("llength $vio_cores", timeout=2)
        vio_count = vio_count_output.strip().split()[-1].strip()
        try:
            count = int(vio_count)
            for i in range(count):
                self.send_command(f"set vio [lindex $vio_cores {i}]", timeout=2)
                vio_name = self.get_property_value("NAME", "$vio", timeout=2)
                cell_name = self.get_property_value("CELL_NAME", "$vio", timeout=2)
                device = self.device or "xcvu9p_0"
                
                # Get probe count and names
                self.send_command("set vio_probes [get_hw_probes -of_objects $vio]", timeout=5)
                num_probes_output = self.send_command("llength $vio_probes", timeout=2)
                try:
                    probe_count = int(num_probes_output.strip().split()[-1].strip())
                except:
                    probe_count = 0
                
                # Get probe names, widths, and directions
                probe_names = []
                probe_widths = {}      # Map probe_name -> width
                probe_directions = {}  # Map probe_name -> 'input' or 'output'
                for j in range(min(probe_count, 50)):
                    self.send_command(f"set probe [lindex $vio_probes {j}]", timeout=2)
                    probe_name = self.get_property_value("NAME", "$probe", timeout=2)
                    if not probe_name:
                        continue

                    probe_names.append(probe_name)

                    # Cache width
                    probe_width = self.get_property_value("WIDTH", "$probe", timeout=2)
                    if probe_width and probe_width.isdigit():
                        probe_widths[probe_name] = int(probe_width)
                    else:
                        probe_widths[probe_name] = None

                    # Prefer explicit DIRECTION property to determine input/output
                    direction = self.get_property_value("DIRECTION", "$probe", timeout=2)
                    direction_upper = direction.upper() if direction and not direction.startswith("ERROR") else ""
                    if "OUT" in direction_upper and "IN" not in direction_upper:
                        probe_directions[probe_name] = 'output'
                    elif "IN" in direction_upper and "OUT" not in direction_upper:
                        probe_directions[probe_name] = 'input'
                    else:
                        # Fallback: infer from which value property is valid
                        input_val = self.get_property_value("INPUT_VALUE", "$probe", timeout=2)
                        output_val = self.get_property_value("OUTPUT_VALUE", "$probe", timeout=2)
                        if input_val and not input_val.startswith("ERROR") and input_val != "":
                            probe_directions[probe_name] = 'input'
                        elif output_val and not output_val.startswith("ERROR") and output_val != "":
                            probe_directions[probe_name] = 'output'
                        else:
                            probe_directions[probe_name] = 'unknown'

                    # Set radix once at scan time based on direction
                    if probe_directions[probe_name] == 'output':
                        # For output probes, we always want OUTPUT_VALUE in HEX
                        self.send_command("set_property OUTPUT_VALUE_RADIX HEX $probe", timeout=2)
                    elif probe_directions[probe_name] == 'input':
                        # For input probes, we always want INPUT_VALUE in HEX
                        self.send_command("set_property INPUT_VALUE_RADIX HEX $probe", timeout=2)
                
                cache_key = f"v{i}"
                self.core_cache[cache_key] = {
                    'type': 'vio',
                    'index': i,
                    'name': vio_name,
                    'cell_name': cell_name,
                    'device': device,
                    'probe_count': probe_count,
                    'probe_names': probe_names,
                    'probe_widths': probe_widths,
                    'probe_directions': probe_directions
                }
        except:
            pass
    
    def print_ila_details(self, index: int) -> bool:
        """Print detailed info for a specific ILA (auto-refreshes data)."""
        ila_list = self._get_ila_list()
        if index < 0 or index >= len(ila_list):
            print(f"ERROR: Invalid ILA index {index+1}")
            return False
        
        ila_info = ila_list[index]
        cache_key = f"i{ila_info['index']}"
        print(f"\n--- ILA: {ila_info['name']} ---")
        
        # Use cached values
        cell_name = ila_info.get('cell_name', '')
        device = ila_info.get('device', self.device or "xcvu9p_0")
        
        if not cell_name:
            print("ERROR: ILA cell name not cached. Please run scan (option 2) first.")
            return False
        
        # Build ILA filter using cached values
        ila_filter = f'[get_hw_ilas -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}]'
        
        print(f"  Data Depth: {ila_info['depth']}")
        
        # Auto-refresh: run immediate trigger and upload data using cached filter
        try:
            print("  Refreshing ILA data...")
            self.send_command(f"run_hw_ila -trigger_now {ila_filter}", timeout=30)
            self.send_command(f"wait_on_hw_ila -timeout 10 {ila_filter}", timeout=15)
            self.send_command(f"upload_hw_ila_data {ila_filter}", timeout=30)
            self.core_cache[cache_key]['refreshed'] = True
            print("  Data captured successfully")
        except Exception as e:
            print(f"  Warning: Could not refresh data: {e}")
        
        # Get current trigger status using cached filter
        trigger_status = self.get_property_value("STATUS.CAPTURE_STATUS", ila_filter, timeout=2)
        status_str = "TRIGGERED" if trigger_status and "TRIGGER" in trigger_status.upper() else "IDLE"
        self.core_cache[cache_key]['status'] = status_str
        print(f"  Trigger Status: {status_str}")
        
        probe_count = ila_info['probe_count']
        probe_names = ila_info.get('probe_names', [])
        
        if probe_count > 0:
            probes_data, triggers_data = self._collect_ila_probes_cached(probe_names, ila_filter)
            print_ila_table(probes_data)
            if triggers_data:
                print_ila_triggers_table(triggers_data)
            if probe_count > 50:
                print(f"  ... and {probe_count - 50} more probes")
        
        return True
    
    def save_ila_data(self, index: int, filename: str = None, fmt: str = "ila") -> bool:
        """Save ILA captured data to file.
        
        Args:
            index: ILA index (0-based)
            filename: Output filename (auto-generated if None)
            fmt: Format - 'ila' (native), 'vcd', or 'csv'
        """
        ila_list = self._get_ila_list()
        if index < 0 or index >= len(ila_list):
            print(f"ERROR: Invalid ILA index {index+1}")
            return False
        
        ila_info = ila_list[index]
        cache_key = f"i{ila_info['index']}"
        
        # Use cached values
        cell_name = ila_info.get('cell_name', '')
        device = ila_info.get('device', self.device or "xcvu9p_0")
        
        if not cell_name:
            print("ERROR: ILA cell name not cached. Please run scan (option 2) first.")
            return False
        
        # Build ILA filter using cached values
        ila_filter = f'[get_hw_ilas -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}]'
        
        # Generate filename if not provided
        if not filename:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = fmt if fmt in ('vcd', 'csv') else 'ila'
            filename = f"ila_{ila_info['name']}_{timestamp}.{ext}"
        
        try:
            # Use cached filter
            # Set current ILA data
            self.send_command(f"current_hw_ila_data [upload_hw_ila_data {ila_filter}]", timeout=30)
            
            # Write to file based on format
            if fmt == "vcd":
                result = self.send_command(f'write_hw_ila_data -vcd_file "{filename}" [current_hw_ila_data]', timeout=10)
            elif fmt == "csv":
                result = self.send_command(f'write_hw_ila_data -csv_file "{filename}" [current_hw_ila_data]', timeout=10)
            else:
                result = self.send_command(f'write_hw_ila_data "{filename}" [current_hw_ila_data]', timeout=10)
            
            if "ERROR" not in result:
                print(f"  ILA data saved to: {filename}")
                return True
            else:
                print(f"  ERROR saving ILA data: {result}")
                return False
        except Exception as e:
            print(f"  ERROR saving ILA data: {e}")
            return False
    
    def print_vio_details(self, index: int, vio_outputs: dict = None, header_prefix: str = "VIO") -> bool:
        """Print detailed info for a specific VIO, with config values if provided.
        
        Args:
            index: VIO index (0-based)
            vio_outputs: Optional config dict for VIO outputs
            header_prefix: Text to use in the header line (e.g. 'VIO', 'Set VIO')
        """
        vio_list = self._get_vio_list()
        if index < 0 or index >= len(vio_list):
            print(f"ERROR: Invalid VIO index {index+1}")
            return False
        
        vio_info = vio_list[index]
        cache_key = f"v{vio_info['index']}"
        print(f"\n--- {header_prefix}: {vio_info['name']} ---")
        
        # Use cached values from scan
        cell_name = vio_info.get('cell_name', '')
        device = vio_info.get('device', self.device or "xcvu9p_0")
        probe_names = vio_info.get('probe_names', [])
        probe_widths = vio_info.get('probe_widths', {})
        probe_directions = vio_info.get('probe_directions', {})
        probe_count = vio_info['probe_count']
        
        if not cell_name:
            print("ERROR: VIO cell name not cached. Please run scan (option 2) first.")
            return False
        
        # Build VIO filter using cached values
        vio_filter = f'[get_hw_vios -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}]'
        
        # Refresh VIO (simple command using cached values)
        self.send_command(f"refresh_hw_vio {vio_filter}", timeout=5)
        
        # Refresh with update_output_values so values reflect hardware
        self.send_command(f"refresh_hw_vio -update_output_values {vio_filter}", timeout=5)
        
        if probe_count > 0:
            # Use cached probe names, widths, and directions to read values directly
            probes_data = self._collect_vio_probes_cached(probe_names, probe_widths, probe_directions, vio_filter, is_synced=True, vio_outputs=vio_outputs)
            print_vio_table(probes_data)
            if probe_count > 50:
                print(f"  ... and {probe_count - 50} more probes")
        else:
            print("  No probes found")
        
        return True
    
    def set_vio_value(self, probe_name: str, value: str, radix: str = "hex", width: int = None, commit: bool = False, force: bool = False) -> bool:
        """Set a VIO output probe value.
        
        Args:
            probe_name: Name of the VIO probe (output only)
            value: Value to set (format depends on radix)
            radix: 'hex', 'bin', 'dec', 'ip', 'mac'
            commit: If True, commit the value after setting
            force: If True, skip confirmation prompt
        
        Returns:
            True if successful
        """
        if not self.connected:
            print("ERROR: Not connected to hardware server")
            return False
        
        try:
            # Find the VIO containing this probe using cache
            vio_info = None
            cache_key = None
            for key, core_data in self.core_cache.items():
                if core_data.get('type') == 'vio':
                    if probe_name in core_data.get('probe_names', []):
                        vio_info = core_data
                        cache_key = key
                        break
            
            if not vio_info:
                print(f"ERROR: Probe {probe_name} not found in any cached VIO. Please run scan (option 2) first.")
                return False
            
            # Use cached values
            cell_name = vio_info.get('cell_name', '')
            device = vio_info.get('device', self.device or "xcvu9p_0")
            
            if not cell_name:
                print("ERROR: VIO cell name not cached. Please run scan (option 2) first.")
                return False
            
            # Build VIO filter using cached values
            vio_filter = f'[get_hw_vios -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}]'
            
            # Check it's an output probe using cached filter
            probe_ref = f'[get_hw_probes {probe_name} -of_objects {vio_filter}]'
            output_val = self.get_property_value("OUTPUT_VALUE", probe_ref, timeout=2)
            if not output_val or output_val.startswith("ERROR"):
                print(f"ERROR: {probe_name} is not an output probe")
                return False
            
            # Use cached width if not provided
            if width is None:
                width = vio_info.get('probe_widths', {}).get(probe_name)
            
            # Convert value based on radix - for Vivado we use decimal format
            tcl_value = self._convert_value_to_decimal(value, radix)
            
            if not force:
                print(f"  Set {probe_name} = {tcl_value}")
                confirm = input("  Confirm? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("  Cancelled")
                    return False
            
            # Build probe reference using cached filter
            probe_ref_set = f'[get_hw_probes {probe_name} -of_objects {vio_filter}]'
            
            # First refresh the VIO using cached filter
            self.send_command(f"refresh_hw_vio {vio_filter}", timeout=5)
            
            # 1. Always set radix to HEX for Vivado (we convert values ourselves)
            self.send_command(f"set_property OUTPUT_VALUE_RADIX HEX {probe_ref_set}", timeout=5)
            
            # 2. Convert value to hex format for Vivado (with padding based on width)
            hex_value = self._convert_value_to_hex_for_vivado(value, radix, width)
            
            # 3. Set value on probe (always as hex, no 0x prefix)
            set_cmd = f'set_property OUTPUT_VALUE {hex_value} {probe_ref_set}'
            result = self.send_command(set_cmd, timeout=5)
            
            # Check for errors in the result
            error_found = False
            for line in result.split('\n'):
                if 'ERROR:' in line or 'ERROR [' in line:
                    print(f"ERROR: {line.strip()}")
                    error_found = True
            
            if error_found:
                print(f"  Command was: {set_cmd}")
                print(f"  Hex value was: {hex_value} (should be {width//4 if width else '?'} hex digits for {width}-bit value)")
                return False
            
            # 4. Commit the probe value using cached filter (WITH braces around probe name for commit)
            probe_ref_commit = f'[get_hw_probes {{{probe_name}}} -of_objects {vio_filter}]'
            commit_cmd = f"commit_hw_vio {probe_ref_commit}"
            commit_result = self.send_command(commit_cmd, timeout=10)
            if "ERROR" in commit_result:
                print(f"  Warning: Error committing {probe_name}: {commit_result}")
            
            # 5. Refresh and read back to verify value was set
            self.send_command(f"refresh_hw_vio {vio_filter}", timeout=5)
            self.send_command(f"refresh_hw_vio -update_output_values {vio_filter}", timeout=5)
            probe_ref_read = f'[get_hw_probes {probe_name} -of_objects {vio_filter}]'
            read_back_raw = self.send_command(f"get_property OUTPUT_VALUE {probe_ref_read}", timeout=5)

            # Extract last non-empty, non-command, non-info line as the value
            read_back_val = ""
            for line in reversed(read_back_raw.split("\n")):
                s = line.strip()
                if not s:
                    continue
                if s.startswith("get_property") or s.startswith("#") or s.startswith("INFO:") or s.startswith("WARNING:"):
                    continue
                read_back_val = s
                break

            # Normalize both values (Vivado may or may not include 0x)
            def _norm_hex(val: str) -> str:
                if not val:
                    return ""
                v = val.strip()
                if v.lower().startswith("0x"):
                    v = v[2:]
                return v.lower()

            if _norm_hex(read_back_val) != _norm_hex(hex_value):
                print(f"  Warning: VIO read-back mismatch for {probe_name}: set={hex_value}, read_back={read_back_val}")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to set VIO value: {e}")
            return False
    
    def _convert_value_to_hex_for_vivado(self, value: str, radix: str, width: int = None) -> str:
        """Convert value from any radix to hex format for Vivado (NO 0x prefix, padded)."""
        if not value or value == "":
            return ""
        
        value = value.strip()
        
        # Calculate hex digits needed (4 bits per hex digit)
        hex_digits = None
        if width:
            hex_digits = (width + 3) // 4  # Round up
        
        if radix == "hex":
            # Already hex, remove 0x prefix and pad if needed
            if value.startswith("0x"):
                hex_part = value[2:]
            else:
                hex_part = value
            
            if hex_digits:
                try:
                    int_val = int(hex_part, 16)
                    return format(int_val, f'0{hex_digits}x')
                except:
                    return hex_part
            return hex_part
        
        elif radix == "bin":
            # Binary to hex
            if value.startswith("0b") or value.startswith("b'"):
                value = value[2:]
            try:
                int_val = int(value, 2)
                if hex_digits:
                    return format(int_val, f'0{hex_digits}x')
                return format(int_val, 'x')
            except:
                return value
        
        elif radix == "dec":
            # Decimal to hex
            try:
                int_val = int(value)
                if hex_digits:
                    return format(int_val, f'0{hex_digits}x')
                return format(int_val, 'x')
            except:
                return value
        
        elif radix == "ip":
            # IP address to hex (always 8 hex digits for 32 bits)
            try:
                parts = value.split('.')
                if len(parts) == 4:
                    int_val = 0
                    for p in parts:
                        int_val = (int_val << 8) | int(p)
                    return format(int_val, '08x')
            except:
                pass
            return value
        
        elif radix == "mac":
            # MAC address to hex (always 12 hex digits for 48 bits)
            try:
                value = value.replace(':', '').replace('-', '')
                return value.lower()
            except:
                return value
        
        return value
    
    def _convert_value_to_decimal(self, value: str, radix: str) -> str:
        """Convert value string to decimal format for Vivado."""
        if not value or value == "":
            return ""
        
        value = value.strip()
        
        if radix == "hex":
            # Hex to decimal
            if value.startswith("0x"):
                value = value[2:]
            try:
                return str(int(value, 16))
            except:
                return value
        
        elif radix == "bin":
            # Binary to decimal
            if value.startswith("0b") or value.startswith("b'"):
                value = value[2:]
            try:
                return str(int(value, 2))
            except:
                return value
        
        elif radix == "dec":
            # Already decimal
            return value
        
        elif radix == "ip":
            # IP address to decimal
            try:
                parts = value.split('.')
                if len(parts) == 4:
                    int_val = 0
                    for p in parts:
                        int_val = (int_val << 8) | int(p)
                    return str(int_val)
            except:
                pass
            return value
        
        elif radix == "mac":
            # MAC address to decimal
            try:
                value = value.replace(':', '').replace('-', '')
                return str(int(value, 16))
            except:
                return value
        
        return value
    
    def _map_radix_to_vivado(self, radix: str) -> str:
        """Map our radix format to Vivado radix constants."""
        radix_map = {
            "hex": "HEX",
            "dec": "UNSIGNED",
            "bin": "BINARY",
            "ip": "UNSIGNED",  # IP is stored as unsigned decimal
            "mac": "UNSIGNED"  # MAC is stored as unsigned decimal
        }
        return radix_map.get(radix.lower(), "HEX")
    
    def commit_vio_values(self, force: bool = False) -> bool:
        """Commit all pending VIO output values.
        
        Args:
            force: If True, skip confirmation prompt
        """
        if not self.connected:
            print("ERROR: Not connected to hardware server")
            return False
        
        try:
            if not force:
                confirm = input("  Commit all VIO values? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("  Cancelled")
                    return False
            
            device = self.device or "xcvu9p_0"
            
            # Commit each pending probe (not VIO!)
            if hasattr(self, '_pending_probe_commits') and self._pending_probe_commits:
                committed_cell_names = set()
                for probe_name, cell_name in self._pending_probe_commits:
                    # Build probe reference with braces around probe name (as shown in GUI)
                    vio_filter = f'get_hw_vios -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}'
                    probe_ref = f'[get_hw_probes {{{probe_name}}} -of_objects [{vio_filter}]]'
                    
                    # Commit the PROBE (not VIO!)
                    commit_cmd = f"commit_hw_vio {probe_ref}"
                    result = self.send_command(commit_cmd, timeout=10)
                    if "ERROR" in result:
                        print(f"  Warning: Error committing {probe_name}: {result}")
                    else:
                        print(f"  Committed: {probe_name}")
                        committed_cell_names.add(cell_name)
                
                # Wait a bit for commit to take effect
                time.sleep(0.5)
                
                # Refresh VIO after commits to update OUTPUT_VALUE properties
                for cell_name in committed_cell_names:
                    vio_filter = f'get_hw_vios -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}'
                    self.send_command(f"refresh_hw_vio -update_output_values [{vio_filter}]", timeout=5)
                
                self._pending_probe_commits.clear()
            else:
                # Commit all VIO cores
                self.send_command("set vio_cores [get_hw_vios]", timeout=5)
                vio_count_output = self.send_command("llength $vio_cores", timeout=2)
                vio_count = int(vio_count_output.strip().split()[-1].strip())
                
                for i in range(vio_count):
                    self.send_command(f"set vio [lindex $vio_cores {i}]", timeout=2)
                    cell_name = self.get_property_value("CELL_NAME", "$vio", timeout=2)
                    
                    if cell_name:
                        vio_ref = f'[get_hw_vios -of_objects [get_hw_devices {device}] -filter {{CELL_NAME=~"{cell_name}"}}]'
                        
                        result = self.send_command(f"commit_hw_vio {vio_ref}", timeout=10)
                        if "ERROR" in result:
                            print(f"  Warning: Error committing {cell_name}: {result}")
                        
                        self.send_command(f"refresh_hw_vio {vio_ref}", timeout=5)
            
            print("  VIO values committed successfully")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to commit VIO values: {e}")
            return False
    
    def _convert_value_to_tcl(self, value: str, radix: str) -> str:
        """Convert value string to TCL hex format with 0x prefix based on radix."""
        if not value or value == "":
            return ""
        
        value = value.strip()
        
        if radix == "hex":
            # Already hex, ensure proper format with 0x prefix
            if value.startswith("0x"):
                return value  # Already has prefix
            return "0x" + value
        
        elif radix == "bin":
            # Binary to hex with 0x prefix
            if value.startswith("0b") or value.startswith("b'"):
                value = value[2:]
            try:
                int_val = int(value, 2)
                return "0x" + format(int_val, 'x')
            except:
                return value
        
        elif radix == "dec":
            # Decimal to hex with 0x prefix
            try:
                int_val = int(value)
                return "0x" + format(int_val, 'x')
            except:
                return value
        
        elif radix == "ip":
            # IP address (192.168.1.1) to hex with 0x prefix
            try:
                parts = value.split('.')
                if len(parts) == 4:
                    int_val = 0
                    for p in parts:
                        int_val = (int_val << 8) | int(p)
                    return "0x" + format(int_val, '08x')
            except:
                pass
            return value
        
        elif radix == "mac":
            # MAC address (aa:bb:cc:dd:ee:ff) to hex with 0x prefix
            try:
                value = value.replace(':', '').replace('-', '')
                return "0x" + value.lower()
            except:
                return value
        
        return value
    
    def get_vio_probe_commit_status(self, probe_name: str) -> str:
        """Get commit status for a specific VIO probe.
        
        Returns: 'COMMITTED', 'UNCOMMITTED', or 'N/A'
        """
        try:
            self.send_command("set vio_cores [get_hw_vios]", timeout=5)
            vio_count_output = self.send_command("llength $vio_cores", timeout=2)
            vio_count = int(vio_count_output.strip().split()[-1].strip())
            
            for i in range(vio_count):
                self.send_command(f"set vio [lindex $vio_cores {i}]", timeout=2)
                self.send_command("set vio_probes [get_hw_probes -of_objects $vio]", timeout=5)
                probe_count_output = self.send_command("llength $vio_probes", timeout=2)
                probe_count = int(probe_count_output.strip().split()[-1].strip())
                
                for j in range(probe_count):
                    self.send_command(f"set probe [lindex $vio_probes {j}]", timeout=2)
                    pname = self.get_property_value("NAME", "$probe", timeout=2)
                    
                    if pname == probe_name or probe_name in pname:
                        # Check if output
                        output_val = self.get_property_value("OUTPUT_VALUE", "$probe", timeout=2)
                        if not output_val or output_val.startswith("ERROR"):
                            return "N/A"
                        
                        # Get activity status
                        activity = self.get_property_value("ACTIVITY", "$probe", timeout=2)
                        
                        # Check if VIO is synced
                        vio_status = self.get_property_value("STATUS", "$vio", timeout=2)
                        if vio_status and "OK" in vio_status:
                            return "COMMITTED"
                        else:
                            return "UNCOMMITTED"
            
            return "N/A"
        except:
            return "N/A"
    
    def _format_sample_value(self, sample: str, width_str: str) -> str:
        """Format sample value with proper prefix: 0x for hex, b' for binary."""
        if not sample:
            return "-"
        
        # Parse width from [N:0] format
        width = 1
        if width_str:
            match = re.match(r'\[(\d+):0\]', width_str)
            if match:
                width = int(match.group(1)) + 1
            elif width_str == '[0]':
                width = 1
        
        # Single bit - use binary notation
        if width == 1:
            return f"b'{sample}"
        
        # Check if it looks like hex (only hex chars)
        if all(c in '0123456789abcdefABCDEF' for c in sample):
            return f"0x{sample}"
        
        # Otherwise return as-is
        return sample
    
    def _collect_ila_probes_cached(self, probe_names: list, ila_filter: str) -> tuple:
        """Collect ILA probe data using cached probe names and simplified filter."""
        probes_data = []
        triggers_data = []
        
        for probe_name in probe_names:
            # Build probe reference using cached filter
            probe_ref = f'[get_hw_probes {probe_name} -of_objects {ila_filter}]'
            
            # Get width (we could cache this too, but for now read it)
            probe_width = self.get_property_value("WIDTH", probe_ref, timeout=2)
            if probe_width and probe_width.isdigit():
                width_int = int(probe_width)
                width_str = f"[{width_int-1}:0]" if width_int > 1 else "[0]"
            else:
                width_str = ""
            
            # Get captured value using list_hw_samples (first sample)
            probe_value = "-"
            try:
                samples_output = self.send_command(f"list_hw_samples -quiet {probe_ref}", timeout=3)
                samples_clean = self._clean_output(samples_output).strip()
                if samples_clean and not samples_clean.startswith("ERROR"):
                    # Filter and get first valid sample value
                    for line in samples_clean.split('\n'):
                        line = line.strip()
                        if (line and 
                            not line.startswith('list_hw_samples') and
                            not line.startswith('#') and
                            not line.startswith('ERROR') and
                            not line.startswith('WARNING')):
                            # Get first sample from space-separated values
                            samples = line.split()
                            for sample in samples:
                                # Skip ellipsis and empty values
                                if sample and sample != '...' and sample != '-':
                                    probe_value = self._format_sample_value(sample, width_str)
                                    break
                            if probe_value != "-":
                                break
            except:
                pass
            
            probes_data.append({'name': probe_name, 'width': width_str, 'value': probe_value})
            
            trigger_val = self.get_property_value("TRIGGER_COMPARE_VALUE", probe_ref, timeout=2)
            if trigger_val and not trigger_val.startswith("ERROR"):
                match = re.search(r"[hb]([0-9A-Fa-fXx_]+)$", trigger_val)
                if match:
                    val_part = match.group(1).replace("_", "").upper()
                    if any(c not in 'X' for c in val_part):
                        triggers_data.append({'name': probe_name, 'width': width_str, 'trigger': trigger_val})
        
        return probes_data, triggers_data
    
    def _collect_ila_probes(self, probe_count: int) -> tuple:
        """Collect ILA probe data including captured values."""
        probes_data = []
        triggers_data = []
        
        for j in range(min(probe_count, 50)):
            self.send_command(f"set probe [lindex $ila_probes {j}]", timeout=2)
            probe_name = self.get_property_value("NAME", "$probe", timeout=2)
            
            probe_width = self.get_property_value("WIDTH", "$probe", timeout=2)
            if probe_width and probe_width.isdigit():
                width_int = int(probe_width)
                width_str = f"[{width_int-1}:0]" if width_int > 1 else "[0]"
            else:
                width_str = ""
            
            # Get captured value using list_hw_samples (first sample)
            probe_value = "-"
            try:
                samples_output = self.send_command("list_hw_samples -quiet $probe", timeout=3)
                samples_clean = self._clean_output(samples_output).strip()
                if samples_clean and not samples_clean.startswith("ERROR"):
                    # Filter and get first valid sample value
                    for line in samples_clean.split('\n'):
                        line = line.strip()
                        if (line and 
                            not line.startswith('list_hw_samples') and
                            not line.startswith('#') and
                            not line.startswith('ERROR') and
                            not line.startswith('WARNING')):
                            # Get first sample from space-separated values
                            samples = line.split()
                            for sample in samples:
                                # Skip ellipsis and empty values
                                if sample and sample != '...' and sample != '-':
                                    probe_value = self._format_sample_value(sample, width_str)
                                    break
                            if probe_value != "-":
                                break
            except:
                pass
            
            probes_data.append({'name': probe_name, 'width': width_str, 'value': probe_value})
            
            trigger_val = self.get_property_value("TRIGGER_COMPARE_VALUE", "$probe", timeout=2)
            if trigger_val and not trigger_val.startswith("ERROR"):
                match = re.search(r"[hb]([0-9A-Fa-fXx_]+)$", trigger_val)
                if match:
                    val_part = match.group(1).replace("_", "").upper()
                    if any(c not in 'X' for c in val_part):
                        triggers_data.append({'name': probe_name, 'width': width_str, 'trigger': trigger_val})
        
        return probes_data, triggers_data
    
    def _collect_vio_probes_cached(self, probe_names: list, probe_widths: dict, probe_directions: dict, vio_filter: str, is_synced: bool, vio_outputs: dict = None) -> list:
        """Collect VIO probe data using cached probe names, widths, directions, and simplified filter."""
        probes_data = []
        
        for probe_name in probe_names:
            # Build probe reference using cached filter
            probe_ref = f'[get_hw_probes {probe_name} -of_objects {vio_filter}]'
            
            # Use cached width
            width_int = probe_widths.get(probe_name)
            if width_int:
                width_str = f"[{width_int-1}:0]" if width_int > 1 else "[0]"
            else:
                width_str = ""
            
            # Use cached direction to read only the appropriate property
            probe_direction = probe_directions.get(probe_name, 'unknown')
            input_val = None
            output_val = None
            
            if probe_direction == 'input':
                # Only read INPUT_VALUE for input probes
                input_val = self.get_property_value("INPUT_VALUE", probe_ref, timeout=2)
            elif probe_direction == 'output':
                # Only read OUTPUT_VALUE for output probes
                output_val = self.get_property_value("OUTPUT_VALUE", probe_ref, timeout=2)
            else:
                # Unknown direction - try both (fallback)
                input_val = self.get_property_value("INPUT_VALUE", probe_ref, timeout=2)
                output_val = self.get_property_value("OUTPUT_VALUE", probe_ref, timeout=2)
            
            # Check config for this output
            config_val = ""
            config_radix = "hex"
            if vio_outputs and probe_name in vio_outputs:
                cfg = vio_outputs[probe_name]
                config_val = cfg.get("value", "")
                config_radix = cfg.get("radix", "hex")
            
            if input_val and not input_val.startswith("ERROR") and input_val != "":
                direction_str = "<-"
                value_str = self._format_sample_value(input_val, width_str)
                commit_str = "-"
            elif output_val and not output_val.startswith("ERROR") and output_val != "":
                direction_str = "->"
                value_str = self._format_value_with_radix(output_val, width_str, config_radix)
                commit_str = "Y" if is_synced else "N"
            else:
                direction_str = "<->"
                value_str = "-"
                commit_str = "-"
            
            probes_data.append({
                'dir': direction_str,
                'name': probe_name,
                'width': width_str,
                'value': value_str,
                'commit': commit_str,
                'config_val': config_val,
                'config_radix': config_radix
            })
        
        return probes_data
    
    def _collect_vio_probes(self, probe_count: int, is_synced: bool, vio_outputs: dict = None) -> list:
        """Collect VIO probe data with optional config values."""
        probes_data = []
        
        for j in range(min(probe_count, 50)):
            self.send_command(f"set probe [lindex $vio_probes {j}]", timeout=2)
            probe_name = self.get_property_value("NAME", "$probe", timeout=2)
            
            probe_width = self.get_property_value("WIDTH", "$probe", timeout=2)
            if probe_width and probe_width.isdigit():
                width_int = int(probe_width)
                width_str = f"[{width_int-1}:0]" if width_int > 1 else "[0]"
            else:
                width_str = ""
            
            input_val = self.get_property_value("INPUT_VALUE", "$probe", timeout=2)
            output_val = self.get_property_value("OUTPUT_VALUE", "$probe", timeout=2)
            
            # Check config for this output
            config_val = ""
            config_radix = "hex"
            if vio_outputs and probe_name in vio_outputs:
                cfg = vio_outputs[probe_name]
                config_val = cfg.get("value", "")
                config_radix = cfg.get("radix", "hex")
            
            if input_val and not input_val.startswith("ERROR") and input_val != "":
                direction_str = "<-"
                value_str = self._format_sample_value(input_val, width_str)
                commit_str = "-"
            elif output_val and not output_val.startswith("ERROR") and output_val != "":
                direction_str = "->"
                value_str = self._format_value_with_radix(output_val, width_str, config_radix)
                commit_str = "Y" if is_synced else "N"
            else:
                direction_str = "<->"
                value_str = "-"
                commit_str = "-"
            
            probes_data.append({
                'dir': direction_str,
                'name': probe_name,
                'width': width_str,
                'value': value_str,
                'commit': commit_str,
                'config_val': config_val,
                'config_radix': config_radix
            })
        
        return probes_data
    
    def _format_value_with_radix(self, value: str, width_str: str, radix: str) -> str:
        """Format value based on specified radix."""
        if not value:
            return "-"
        
        # Parse width from [N:0] format
        width = 32
        if width_str:
            match = re.match(r'\[(\d+):0\]', width_str)
            if match:
                width = int(match.group(1)) + 1
            elif width_str == '[0]':
                width = 1
        
        # Single bit - always binary
        if width == 1:
            return f"b'{value}"
        
        # Clean hex value
        hex_val = value
        if hex_val.startswith("0x"):
            hex_val = hex_val[2:]
        
        try:
            int_val = int(hex_val, 16)
        except:
            return value
        
        if radix == "ip" and width == 32:
            # Format as IP address
            ip_parts = [
                (int_val >> 24) & 0xFF,
                (int_val >> 16) & 0xFF,
                (int_val >> 8) & 0xFF,
                int_val & 0xFF
            ]
            return '.'.join(str(p) for p in ip_parts)
        
        elif radix == "mac" and width == 48:
            # Format as MAC address
            mac_str = format(int_val, '012x')
            return ':'.join(mac_str[i:i+2] for i in range(0, 12, 2))
        
        elif radix == "bin":
            return f"b'{bin(int_val)[2:].zfill(width)}"
        
        elif radix == "dec":
            return f"D'{int_val}"
        
        else:  # hex
            # Calculate number of hex digits needed (4 bits per hex digit)
            hex_digits = (width + 3) // 4  # Round up
            padded_hex = format(int_val, f'0{hex_digits}x').upper()
            return f"0x{padded_hex}"
    
    def scan_jtag(self) -> bool:
        """Scan JTAG targets and read device DNA."""
        if not self.connected:
            print("ERROR: Not connected to hardware server")
            return False
        
        try:
            print("=" * 50)
            print("Scanning JTAG Targets and Device DNA")
            print("=" * 50)
            print(f"hw_server: {self.hw_server_host}:{self.hw_server_port}\n")
            
            try:
                self.send_command("if {[info exists target]} { close_hw_target $target }", timeout=5)
            except:
                pass
            
            output = self.send_command("set all_targets [get_hw_targets]", timeout=5)
            target_count_output = self.send_command("llength $all_targets", timeout=2)
            target_count = target_count_output.strip().split()[-1].strip()
            
            try:
                count = int(target_count)
                if count == 0:
                    print("No hardware targets found")
                    print("Please ensure FPGA devices are connected and powered on")
                    return True
                
                print(f"Found {count} JTAG target(s):\n")
                
                for i in range(count):
                    self._print_jtag_target(i)
                    
            except Exception as e:
                print(f"Error processing targets: {e}")
            
            self._restore_connection()
            
            print("=" * 50)
            print("Scan completed")
            print("=" * 50)
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to scan JTAG: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _print_jtag_target(self, index: int) -> None:
        """Print single JTAG target details."""
        self.send_command(f"set target [lindex $all_targets {index}]", timeout=2)
        target_name = self.get_property_value("NAME", "$target", timeout=2)
        print(f"--- Target {index+1}: {target_name} ---")
        
        output = self.send_command("open_hw_target $target", timeout=10)
        if "ERROR" in output or "error" in output.lower():
            print(f"  Error: Could not open target")
            print("  (Target may be in use or device not responding)\n")
            return
        
        output = self.send_command("set devices [get_hw_devices]", timeout=5)
        device_count_output = self.send_command("llength $devices", timeout=2)
        device_count = device_count_output.strip().split()[-1].strip()
        
        try:
            dev_count = int(device_count)
            if dev_count == 0:
                print("  No devices found on this target")
                self.send_command("close_hw_target $target", timeout=5)
                print()
                return
            
            print(f"  Devices found: {dev_count}")
            
            for j in range(dev_count):
                self._print_jtag_device(j)
            
            self.send_command("close_hw_target $target", timeout=5)
            print()
            
        except Exception as e:
            print(f"  Error processing device: {e}")
            try:
                self.send_command("close_hw_target $target", timeout=5)
            except:
                pass
            print()
    
    def _print_jtag_device(self, index: int) -> None:
        """Print single JTAG device details."""
        self.send_command(f"set device [lindex $devices {index}]", timeout=2)
        device_name = self.get_property_value("NAME", "$device", timeout=2)
        
        try:
            device_type = self.get_property_value("TYPE", "$device", timeout=2)
            if not device_type or device_type.startswith("ERROR"):
                device_type = "unknown"
        except:
            device_type = "unknown"
        
        print(f"\n  Device {index+1}: {device_name}")
        print(f"    Type: {device_type}")
        
        self.send_command("current_hw_device $device", timeout=2)
        
        dna_found = self._try_read_dna()
        
        if not dna_found:
            print("    DNA: Not readable (device may need to be programmed first)")
        
        try:
            is_programmed = self.get_property_value("PROGRAM.IS_PROGRAMMED", "$device", timeout=2)
            if is_programmed and not is_programmed.startswith("ERROR"):
                print(f"    Programmed: {is_programmed}")
        except:
            pass
    
    def _try_read_dna(self) -> bool:
        """Try to read device DNA using multiple methods."""
        # Method 1: FUSE_DNA
        try:
            chip_dna = self.get_property_value("REGISTER.EFUSE.FUSE_DNA", "$device", timeout=5)
            if chip_dna and chip_dna != "UNREADABLE" and not chip_dna.startswith("ERROR"):
                if chip_dna.startswith("0x"):
                    chip_dna = chip_dna[2:]
                chip_dna = chip_dna.upper()
                print(f"    DNA (FUSE_DNA): {chip_dna}")
                return True
        except:
            pass
        
        # Method 2: SLR DNA
        for slr in ["SLR0", "SLR1", "SLR2", "SLR3"]:
            try:
                slr_dna = self.get_property_value(f"REGISTER.DNA.{slr}", "$device", timeout=5)
                if slr_dna and slr_dna != "Unreadable" and not slr_dna.startswith("ERROR"):
                    print(f"    DNA ({slr}): {slr_dna}")
                    return True
            except:
                pass
        
        return False
    
    def _restore_connection(self) -> None:
        """Restore connection to first target/device after JTAG scan."""
        try:
            self.send_command("set targets [get_hw_targets]", timeout=5)
            self.send_command("set target [lindex $targets 0]", timeout=2)
            self.send_command("open_hw_target $target", timeout=10)
            self.send_command("set devices [get_hw_devices]", timeout=5)
            self.send_command("set device [lindex $devices 0]", timeout=2)
            self.send_command("current_hw_device $device", timeout=2)
        except:
            pass
    
    def close(self) -> None:
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

