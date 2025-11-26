#!/usr/bin/env python3
"""
VCD Analysis Tool with ArgParse

Professional VCD analysis tool with clean function separation, argparse for command-line handling,
and functions that return dictionaries or lists for easy integration.
"""

import argparse
import re
import sys
from typing import Dict, List, Any, Optional, Tuple, Union
from fnmatch import fnmatch
from typeguard import typechecked
from dataclasses import dataclass


@dataclass
class SignalResult:
    """Data class for signal analysis results."""
    signal_name: str
    time: str
    calc_value: Dict[str, Any]
    raw_vcd: Optional[str]
    width: Optional[int]
    last_vcd_time: Optional[str]
    last_vcd_value: Optional[str]
    note: Dict[str, Any]
    # Verbose fields (only populated when --verbose is used)
    var_id: Optional[str] = None
    vcd_line: Optional[str] = None
    signal_definition: Optional[str] = None
    msb: Optional[int] = None
    lsb: Optional[int] = None
    
    def __str__(self) -> str:
        """String representation of the signal result."""
        return self.to_string(verbose=False)
    
    def to_string(self, verbose: bool = False, radix: Optional[str] = None) -> str:
        """String representation of the signal result with optional verbose fields and radix formatting."""
        # Validate arguments
        if not isinstance(verbose, bool):
            raise TypeError(f"verbose must be a boolean, got {type(verbose).__name__}")
        
        if radix is not None and not isinstance(radix, str):
            raise TypeError(f"radix must be a string or None, got {type(radix).__name__}")
        
        if radix is not None and radix not in ['hex', 'int', 'bin']:
            raise ValueError(f"radix must be one of ['hex', 'int', 'bin'], got '{radix}'")
        
        # Validate internal data
        if not isinstance(self.calc_value, dict):
            raise ValueError(f"calc_value must be a dictionary, got {type(self.calc_value).__name__}")
        
        if radix and radix not in self.calc_value:
            raise KeyError(f"radix '{radix}' not found in calc_value. Available keys: {list(self.calc_value.keys())}")
        
        # Format calc_value based on radix
        if radix and radix in ['hex', 'int', 'bin']:
            calc_value_formatted = self.calc_value[radix]
        else:
            calc_value_formatted = self.calc_value
        
        result_dict = {
            'time': self.time,
            'calc_value': calc_value_formatted,
            'width': self.width,
            'note': self.note
        }
        
        if verbose:
            result_dict['vcd'] = {
                'raw_vcd': self.raw_vcd,
                'last_vcd_time': self.last_vcd_time,
                'last_vcd_value': self.last_vcd_value,
                'var_id': self.var_id,
                'vcd_line': self.vcd_line,
                'signal_definition': self.signal_definition,
                'msb': self.msb,
                'lsb': self.lsb
            }
        
        return f"{{{self.signal_name}: {result_dict}}}"


class LazyProperty:
    """Descriptor for lazy loading of properties."""
    
    def __init__(self, func: Any) -> None:
        self.func: Any = func
        self.name: str = func.__name__
    
    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        value: Any = self.func(instance)
        setattr(instance, self.name, value)
        return value


class VCDAnalyzer:
    """Professional VCD analyzer with modular query functions."""
    
    def __init__(self, vcd_file: str) -> None:
        """Initialize analyzer and parse VCD file."""
        self.vcd_file: str = vcd_file
        self.signals: Dict[str, Dict[str, Any]] = {}  # {var_id: signal_info}
        self.signal_hierarchy: Dict[str, str] = {}  # {var_id: full_path}
        self.scope_stack: List[str] = []
        self.timestamps: List[Tuple[str, Dict[str, Dict[str, Any]]]] = []  # List of (time, changes_dict)
        self.vcd_dict: Dict[str, List[Dict[str, Any]]] = {}  # {timestamp: [signal_changes]}
        
        self._parse_vcd()
        self._build_vcd_dict()
    
    @typechecked
    def _parse_vcd(self) -> None:
        """Parse VCD file completely."""
        with open(self.vcd_file, 'r') as f:
            lines: List[str] = f.readlines()
        
        # Parse header section
        self._parse_header(lines)
        
        # Parse data section
        self._parse_data(lines)
    
    @typechecked
    def _build_vcd_dict(self) -> None:
        """Build VCD dictionary with timestamps as keys and signal changes as values."""
        for timestamp, changes_dict in self.timestamps:
            signal_changes: List[Dict[str, Any]] = []
            
            for signal_name, signal_data in changes_dict.items():
                signal_change: Dict[str, Any] = {
                    'signal_name': signal_name,
                    **signal_data  # Include raw_vcd, hex, int, binary_value
                }
                signal_changes.append(signal_change)
            
            self.vcd_dict[timestamp] = signal_changes
    
    @LazyProperty
    def all_timestamps_cache(self) -> List[str]:
        """Lazy load timestamps cache."""
        return sorted(self.vcd_dict.keys(), key=int)
    
    @LazyProperty
    def all_signal_names_cache(self) -> List[str]:
        """Lazy load signal names cache."""
        return list(self.signal_hierarchy.values())
    
    @LazyProperty
    def timestamps_with_signals_cache(self) -> List[Dict[str, Any]]:
        """Lazy load timestamps with signals cache."""
        result: List[Dict[str, Any]] = []
        for timestamp, signal_changes in self.vcd_dict.items():
            signal_names: List[str] = [change['signal_name'] for change in signal_changes]
            result.append({
                'time': timestamp,
                'signals': signal_names
            })
        return result
    
    def _parse_header(self, lines: List[str]) -> None:
        """Parse VCD header section line by line."""
        in_header: bool = True
        i: int = 0
        
        while i < len(lines) and in_header:
            line: str = lines[i].strip()
            
            if line.startswith('$scope'):
                # Enter scope - parse: $scope module <name> $end
                parts = line.split()
                if len(parts) >= 4 and parts[0] == '$scope' and parts[1] == 'module' and parts[-1] == '$end':
                    scope_name = parts[2]
                    self.scope_stack.append(scope_name)
            
            elif line.startswith('$upscope'):
                # Exit scope
                if self.scope_stack:
                    self.scope_stack.pop()
            
            elif line.startswith('$var'):
                # Parse variable definition line by line
                self._parse_var_definition_line_by_line(line)
            
            elif line.startswith('$enddefinitions'):
                in_header = False
            
            i += 1
    
    def _parse_var_definition_line_by_line(self, line: str) -> None:
        """Parse a $var definition line by splitting and parsing components."""
        # Format: $var wire <width> <var_id> <signal_name> [<range>] $end
        # Example: $var wire 32 :! parser_filter_sip[0] [31:0] $end
        
        parts = line.split()
        if len(parts) < 6:  # Minimum: $var wire width var_id signal_name $end
            return
            
        if parts[0] != '$var' or parts[1] != 'wire' or parts[-1] != '$end':
            return
            
        try:
            width = int(parts[2])
            var_id = parts[3]
            
            # Find signal name - everything between var_id and the range or $end
            signal_name_parts = []
            range_start_idx = -1
            
            # Look for range pattern [msb:lsb]
            for i in range(4, len(parts) - 1):
                if parts[i].startswith('[') and parts[i].endswith(']'):
                    range_start_idx = i
                    break
            
            if range_start_idx > 0:
                # Signal name is everything between var_id and range
                signal_name_parts = parts[4:range_start_idx]
                # Parse range
                range_str = parts[range_start_idx][1:-1]  # Remove [ and ]
                if ':' in range_str:
                    msb, lsb = map(int, range_str.split(':'))
                else:
                    msb = lsb = int(range_str)
            else:
                # No range, signal name is everything until $end
                signal_name_parts = parts[4:-1]
                msb = width - 1
                lsb = 0
            
            signal_name = ' '.join(signal_name_parts)
            
            # Build hierarchical path
            full_path: str = '.'.join(self.scope_stack + [signal_name])
            
            # Store signal info
            self.signals[var_id] = {
                'name': signal_name,
                'width': width,
                'msb': msb,
                'lsb': lsb,
                'full_path': full_path
            }
            self.signal_hierarchy[var_id] = full_path
            
        except (ValueError, IndexError) as e:
            # Skip malformed lines
            pass
    
    def _parse_data(self, lines: List[str]) -> None:
        """Parse VCD data section."""
        # Find start of data section
        data_start: int = 0
        for i, line in enumerate(lines):
            if line.strip() == '$enddefinitions $end':
                data_start = i + 1
                break
        
        # Skip empty lines at start of data section
        while data_start < len(lines) and not lines[data_start].strip():
            data_start += 1
        
        # Parse timestamps and value changes
        i: int = data_start
        
        while i < len(lines):
            line: str = lines[i].strip()
            
            if line.startswith('#'):
                # New timestamp
                timestamp: str = line[1:]  # Remove '#' prefix
                changes: Dict[str, Dict[str, Any]] = {}
                
                # Parse value changes for this timestamp
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('#'):
                    value_line: str = lines[i].strip()
                    if value_line:
                        var_id: str
                        value: str
                        var_id, value = self._parse_value_change(value_line)
                        if var_id and var_id in self.signals:
                            signal_path: str = self.signal_hierarchy[var_id]
                            converted_value: Dict[str, Any] = self._convert_value(value, self.signals[var_id])
                            changes[signal_path] = converted_value
                    i += 1
                
                if changes:  # Only add timestamp if there are changes
                    self.timestamps.append((timestamp, changes))
            else:
                i += 1
    
    def _parse_value_change(self, line: str) -> Tuple[str, str]:
        """Parse a value change line and return (var_id, value)."""
        if line.startswith('0') or line.startswith('1'):
            # Single bit
            value: str = line[0]
            var_id: str = line[1:]
            return var_id, value
        elif line.startswith('b'):
            # Binary value
            match: Optional[re.Match[str]] = re.match(r'b([01]+)\s+(\S+)', line)
            if match:
                value: str
                var_id: str
                value, var_id = match.groups()
                return var_id, value
        elif line.startswith('r'):
            # Real value
            match: Optional[re.Match[str]] = re.match(r'r([0-9.+-eE]+)\s+(\S+)', line)
            if match:
                value: str
                var_id: str
                value, var_id = match.groups()
                return var_id, value
        
        return '', ''
    
    def _convert_value(self, raw_value: str, signal_info: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw VCD value to multiple representations."""
        width: int = signal_info['width']
        
        # Ensure binary value is properly formatted
        if raw_value.startswith('b'):
            binary_value: str = raw_value[1:]
        else:
            binary_value = raw_value
        
        # Pad binary value to signal width
        if len(binary_value) < width:
            binary_value = binary_value.zfill(width)
        elif len(binary_value) > width:
            binary_value = binary_value[-width:]
        
        # Convert to integer
        try:
            int_value: int = int(binary_value, 2)
        except ValueError:
            int_value = 0
        
        # Convert to hex with leading zeros and 0x prefix
        hex_width: int = (width + 3) // 4  # Calculate hex width needed
        hex_value: str = f"0x{int_value:0{hex_width}x}"
        
        return {
            'raw_vcd': raw_value,
            'hex': hex_value,
            'int': int_value,
            'binary_value': binary_value
        }
    
    # Query Functions (Each Returns Dict/List)
    
    @typechecked
    def get_all_timestamps(self) -> List[str]:
        """Get all timestamps in VCD file."""
        return self.all_timestamps_cache
    
    @typechecked
    def get_all_signal_names(self) -> List[str]:
        """Get all signal names in design."""
        return self.all_signal_names_cache
    
    @typechecked
    def find_signals(self, pattern: str) -> List[str]:
        """Find signals matching pattern using wildcard matching."""
        matching_signals: List[str] = []
        for signal_name in self.all_signal_names_cache:
            if fnmatch(signal_name, pattern):
                matching_signals.append(signal_name)
        return matching_signals
    
    
    @typechecked
    def _get_signal_metadata(self, signal_name: str) -> Dict[str, Any]:
        """Get all metadata for a signal by its full path."""
        for var_id, signal_info in self.signals.items():
            if signal_info['full_path'] == signal_name:
                return {
                    'var_id': var_id,
                    'width': signal_info['width'],
                    'msb': signal_info['msb'],
                    'lsb': signal_info['lsb'],
                    'signal_definition': f"$var wire {signal_info['width']} {var_id} {signal_info['name']} [{signal_info['msb']}:{signal_info['lsb']}] $end"
                }
        return {
            'var_id': None,
            'width': None,
            'msb': None,
            'lsb': None,
            'signal_definition': None
        }
    
    @typechecked
    def _get_signal_value_from_edges(self, signal_edges: List[SignalResult], timestamp: str, signal_name: str, verbose: bool = False) -> SignalResult:
        """Get signal value at specific timestamp from pre-loaded edges (optimized version)."""
        # Validate arguments
        if not isinstance(signal_edges, list):
            raise TypeError(f"signal_edges must be a list, got {type(signal_edges).__name__}")
        
        if not isinstance(timestamp, str):
            raise TypeError(f"timestamp must be a string, got {type(timestamp).__name__}")
        
        if not isinstance(signal_name, str):
            raise TypeError(f"signal_name must be a string, got {type(signal_name).__name__}")
        
        if not isinstance(verbose, bool):
            raise TypeError(f"verbose must be a boolean, got {type(verbose).__name__}")
        
        if not timestamp.strip():
            raise ValueError("timestamp cannot be empty or whitespace only")
        
        if not signal_name.strip():
            raise ValueError("signal_name cannot be empty or whitespace only")
        
        # Validate signal_edges list contents
        for i, edge in enumerate(signal_edges):
            if not isinstance(edge, SignalResult):
                raise TypeError(f"signal_edges[{i}] must be a SignalResult object, got {type(edge).__name__}")
        
        try:
            target_time_int: int = int(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: '{timestamp}'. Must be a number.")
        
        # Find closest edge before or at target time
        closest_edge: Optional[SignalResult] = None
        for edge in signal_edges:
            edge_time_int: int = int(edge.time)
            if edge_time_int <= target_time_int:
                closest_edge = edge
            else:
                break
        
        if closest_edge is None:
            # No edge found, return None values
            signal_metadata: Dict[str, Any] = self._get_signal_metadata(signal_name)
            return SignalResult(
                signal_name=signal_name,
                time=timestamp,
                calc_value={"hex": None, "int": None, "bin": None},
                raw_vcd="None",
                width=signal_metadata['width'],
                last_vcd_time="None",
                last_vcd_value="None",
                note={"status": "no_data"},
                var_id=signal_metadata['var_id'] if verbose else None,
                vcd_line=None,
                signal_definition=signal_metadata['signal_definition'] if verbose else None,
                msb=signal_metadata['msb'] if verbose else None,
                lsb=signal_metadata['lsb'] if verbose else None
            )
        
        # Return the signal data from the closest edge
        signal_metadata: Dict[str, Any] = self._get_signal_metadata(signal_name)
        
        # Handle calc_value - it might be a dict or a single value depending on radix usage
        if isinstance(closest_edge.calc_value, dict):
            calc_value = {"hex": closest_edge.calc_value["hex"], "int": closest_edge.calc_value["int"], "bin": closest_edge.calc_value["bin"]}
        else:
            # If calc_value is a single value (from radix), we need to reconstruct the dict
            # This shouldn't happen in normal flow, but let's handle it gracefully
            calc_value = {"hex": "0x0", "int": 0, "bin": "0"}
        
        return SignalResult(
            signal_name=signal_name,
            time=timestamp,
            calc_value=calc_value,
            raw_vcd=closest_edge.raw_vcd,
            width=closest_edge.width,
            last_vcd_time=closest_edge.time,
            last_vcd_value=closest_edge.raw_vcd,
            note={"status": f"calculated from last value at timestamp {closest_edge.time}"},
            var_id=signal_metadata['var_id'] if verbose else None,
            vcd_line=f"{closest_edge.raw_vcd}{signal_metadata['var_id']}" if verbose and signal_metadata['var_id'] else None,
            signal_definition=signal_metadata['signal_definition'] if verbose else None,
            msb=signal_metadata['msb'] if verbose else None,
            lsb=signal_metadata['lsb'] if verbose else None
        )
    
    
    
    def get_timestamps(self) -> List[Dict[str, Any]]:
        """
        Extract all timestamps with signals that changed at each timestamp.
        Returns: [{time: str, signals: [signal_names]}, ...]
        No values included, just which signals changed.
        """
        return self.timestamps_with_signals_cache
    
    def get_edges_at_timestamp(self, timestamp: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all signal changes at specific timestamp.
        Returns: {signal_name: {raw, hex, int}}
        """
        if timestamp in self.vcd_dict:
            result: Dict[str, Dict[str, Any]] = {}
            for signal_change in self.vcd_dict[timestamp]:
                signal_name: str = signal_change['signal_name']
                result[signal_name] = {
                    'raw_vcd': signal_change['raw_vcd'],
                    'hex': signal_change['hex'],
                    'int': signal_change['int'],
                    'binary_value': signal_change['binary_value']
                }
            return result
        return {}
    
    def get_edge_for_signal_at_timestamp(self, timestamp: str, signal: str) -> Optional[Dict[str, Any]]:
        """
        Filter edges by signal at specific timestamp.
        Returns: {raw, hex, int} or None if no change.
        """
        edges: Dict[str, Dict[str, Any]] = self.get_edges_at_timestamp(timestamp)
        return edges.get(signal)
    
    def get_signal_edges(self, signal: str, verbose: bool = False) -> List[SignalResult]:
        """
        Get all edges for a signal with timestamps and values.
        Returns: List[SignalResult]
        """
        # Validate arguments
        if not isinstance(signal, str):
            raise TypeError(f"signal must be a string, got {type(signal).__name__}")
        
        if not isinstance(verbose, bool):
            raise TypeError(f"verbose must be a boolean, got {type(verbose).__name__}")
        
        if not signal.strip():
            raise ValueError("signal cannot be empty or whitespace only")
        
        # Build edges for this specific signal only (not entire cache)
        edges: List[SignalResult] = []
        for timestamp, signal_changes in self.vcd_dict.items():
            for signal_change in signal_changes:
                if signal_change['signal_name'] == signal:
                    signal_metadata: Dict[str, Any] = self._get_signal_metadata(signal)
                    edge_data = SignalResult(
                        signal_name=signal,
                        time=timestamp,
                        calc_value={"hex": signal_change['hex'], "int": signal_change['int'], "bin": signal_change['binary_value']},
                        raw_vcd=signal_change['raw_vcd'],
                        width=signal_metadata['width'],
                        last_vcd_time=timestamp,
                        last_vcd_value=signal_change['raw_vcd'],
                        note={"status": "exact timestamp in VCD"},
                        var_id=signal_metadata['var_id'] if verbose else None,
                        vcd_line=f"{signal_change['raw_vcd']}{signal_metadata['var_id']}" if verbose and signal_metadata['var_id'] else None,
                        signal_definition=signal_metadata['signal_definition'] if verbose else None,
                        msb=signal_metadata['msb'] if verbose else None,
                        lsb=signal_metadata['lsb'] if verbose else None
                    )
                    edges.append(edge_data)
        return edges
    
    @typechecked
    def get_signal_edges_from_timestamp(self, signal: str, timestamp: str, verbose: bool = False) -> List[SignalResult]:
        """
        Get all signal edges after the specified timestamp (not including the timestamp itself).
        Returns: List[SignalResult]
        """
        # Validate arguments
        if not isinstance(signal, str):
            raise TypeError(f"signal must be a string, got {type(signal).__name__}")
        
        if not isinstance(timestamp, str):
            raise TypeError(f"timestamp must be a string, got {type(timestamp).__name__}")
        
        if not isinstance(verbose, bool):
            raise TypeError(f"verbose must be a boolean, got {type(verbose).__name__}")
        
        if not signal.strip():
            raise ValueError("signal cannot be empty or whitespace only")
        
        if not timestamp.strip():
            raise ValueError("timestamp cannot be empty or whitespace only")
        
        try:
            target_time_int: int = int(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: '{timestamp}'. Must be a number.")
        
        # Get all edges for this signal
        signal_edges: List[SignalResult] = self.get_signal_edges(signal, verbose)
        
        if not signal_edges:
            raise ValueError(f'No data found for signal "{signal}"')
        
        # Filter edges after the target timestamp (not including the timestamp itself)
        filtered_edges: List[SignalResult] = []
        for edge in signal_edges:
            edge_time_int: int = int(edge.time)
            if edge_time_int > target_time_int:
                filtered_edges.append(edge)
        
        return filtered_edges
    
    @typechecked
    def validate_signal_exists(self, signal: str) -> None:
        """
        Validate that a signal exists in the design.
        Raises ValueError if signal is not found.
        """
        if signal not in self.signal_hierarchy.values():
            available_signals: List[str] = list(self.signal_hierarchy.values())[:10]
            raise ValueError(f'Signal "{signal}" not found in design. Available signals: {available_signals}')


def verify_arguments(args: argparse.Namespace, analyzer: VCDAnalyzer) -> None:
    """Verify command-line arguments for consistency and validity."""
    # Count active commands (--edge is not a separate command, it works with --signal)
    active_commands: int = 0
    if args.timestamps:
        active_commands += 1
    if args.signalnames is not None:
        active_commands += 1
    if args.signal is not None:
        active_commands += 1
    
    # Check for conflicting commands
    if active_commands > 1:
        conflicting_args: List[str] = []
        if args.timestamps:
            conflicting_args.append('--timestamps')
        if args.signalnames is not None:
            conflicting_args.append('--signalnames')
        if args.signal is not None:
            conflicting_args.append('--signal')
        
        raise ValueError(f"Conflicting arguments provided. Only one command allowed at a time: {', '.join(conflicting_args)}")
    
    # Validate --time usage
    if args.time is not None:
        if args.signal is None:
            raise ValueError("--time can only be used with --signal")
        try:
            for timestamp in args.time:
                int(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format for --time: '{args.time}'. All timestamps must be numbers.")
    
    # Validate --edge usage
    if args.edge is not None:
        if args.signal is None:
            raise ValueError("--edge can only be used with --signal")
        if args.time is None:
            raise ValueError("--edge requires --time to be specified")
        if isinstance(args.edge, int) and args.edge <= 0:
            raise ValueError("--edge number must be > 0")
    
    # Validate --count usage
    if args.count is not None:
        if args.signal is None:
            raise ValueError("--count can only be used with --signal")
        if args.time is None:
            raise ValueError("--count requires --time to be specified")
        if args.edge is not None:
            raise ValueError("--count cannot be used with --edge")
        if args.count <= 0:
            raise ValueError("--count must be > 0")
        if len(args.time) > 1:
            raise ValueError("--count can only be used with a single --time timestamp")
    
    # Validate signals exist in design (only for exact signal names, not wildcards)
    if args.signal is not None and '*' not in args.signal and '?' not in args.signal:
        analyzer.validate_signal_exists(args.signal)


@typechecked
def main() -> None:
    """Main function with argparse setup and command dispatch."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='VCD Analysis Tool')
    
    parser.add_argument('--vcd', required=True, help='VCD file to analyze')
    parser.add_argument('--timestamps', action='store_true', help='List all timestamps')
    parser.add_argument('--signalnames', nargs='?', const='*', help='List signal names (optionally filter with wildcard pattern)')
    parser.add_argument('--signal', help='Signal name (supports wildcards)')
    parser.add_argument('--time', nargs='+', help='Filter signal results by timestamp(s) - can specify multiple timestamps')
    parser.add_argument('--edge', nargs='?', const=True, type=int, help='Show signal edges after the --time timestamp (requires --time). Optional number limits edges shown (must be >0)')
    parser.add_argument('--verbose', action='store_true', help='Show all VCD data including var_id, signal definition, and complete VCD metadata')
    parser.add_argument('--radix', choices=['hex', 'int', 'bin'], help='Output format for calc_value: hex, int, or bin. Without this flag, shows all formats in a dictionary')
    parser.add_argument('--count', type=int, help='Show count number of values starting from --time timestamp (requires --time, not allowed with --edge)')
    
    args: argparse.Namespace = parser.parse_args()
    
    try:
        analyzer: VCDAnalyzer = VCDAnalyzer(args.vcd)
        verify_arguments(args, analyzer)
        
        
        if args.timestamps:    
            for timestamp in analyzer.get_all_timestamps():
                print(timestamp)
        
        if args.signalnames is not None:
            # Filter signal names with wildcard pattern using cache
            pattern: str = args.signalnames
            filtered_signals: List[str] = analyzer.find_signals(pattern)
            
            if filtered_signals:
                for signal_name in filtered_signals:
                    print(signal_name)
            else:
                print("None")
        
        if args.signal is not None:
            # First run find_signals to get matching signals
            
            matching_signals: List[str] = analyzer.find_signals(args.signal)
            
            if args.time is not None:
                # Filter signal results by time(s) - can be multiple timestamps
                for signal_name in matching_signals:
                    # Get signal edges once to avoid repeated expensive calls
                    signal_edges: List[SignalResult] = analyzer.get_signal_edges(signal_name)
                    
                    if args.count is not None:
                        # --count mode: show count number of values starting from --time timestamp
                        start_timestamp = args.time[0]  # Only single timestamp allowed with --count
                        all_timestamps: List[str] = analyzer.get_all_timestamps()
                        
                        # Find the starting timestamp index
                        try:
                            start_time_int: int = int(start_timestamp)
                        except ValueError:
                            raise ValueError(f"Invalid timestamp format: '{start_timestamp}'. Must be a number.")
                        
                        # Always start with the requested timestamp
                        timestamps_to_show: List[str] = [start_timestamp]
                        
                        # Get additional timestamps > start_timestamp, sorted
                        for ts in all_timestamps:
                            if int(ts) > start_time_int:
                                timestamps_to_show.append(ts)
                        
                        # Sort by timestamp value
                        timestamps_to_show.sort(key=int)
                        
                        # Limit to count
                        timestamps_to_show = timestamps_to_show[:args.count]
                        
                        # Print header
                        print(f"\n=== {args.count} values starting from {start_timestamp}ns ===")
                        
                        # Show values for each timestamp
                        for timestamp in timestamps_to_show:
                            value: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                            if timestamp == start_timestamp:
                                # First timestamp is always the requested one
                                if timestamp in all_timestamps:
                                    value.note = {"status": "exact timestamp in VCD"}
                                else:
                                    value.note = {"status": f"calculated from last value at timestamp {start_timestamp}"}
                            else:
                                # Subsequent timestamps are from VCD
                                value.note = {"status": "exact timestamp in VCD"}
                            print(value.to_string(args.verbose, args.radix))
                    
                    else:
                        # Normal --time mode: show values for specified timestamps
                        # Print combined header for all timestamps
                        timestamps_str = ",".join([f"{ts}ns" for ts in args.time])
                        print(f"\n=== value @ {timestamps_str} ===")
                        
                        # Process each requested timestamp
                        for timestamp in args.time:
                            # Check if exact timestamp exists in VCD
                            all_timestamps: List[str] = analyzer.get_all_timestamps()
                            exact_timestamp_exists: bool = timestamp in all_timestamps
                            
                            if exact_timestamp_exists:
                                # Exact timestamp found, show normally
                                value: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                                # Override status for exact timestamp
                                value.note = {"status": "exact timestamp in VCD"}
                                print(value.to_string(args.verbose, args.radix))
                            else:
                                # Exact timestamp not found, show calculated value for requested timestamp
                                calculated_value = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                                print(calculated_value.to_string(args.verbose, args.radix))
                            
                            # If --edge flag is used, show edges after this timestamp
                            if args.edge is not None:
                                edges_after: List[SignalResult] = analyzer.get_signal_edges_from_timestamp(signal_name, timestamp, args.verbose)
                                
                                # Limit number of edges if specified and update header accordingly
                                if isinstance(args.edge, int) and not isinstance(args.edge, bool):
                                    edges_after = edges_after[:args.edge]
                                    print(f"\n=== '{args.edge}' edges after {timestamp}ns ===")
                                else:
                                    print(f"\n=== all edges after {timestamp}ns ===")
                                
                                for edge in edges_after:
                                    edge.note = {"status": "exact timestamp in VCD"}
                                    print(edge.to_string(args.verbose, args.radix))
                    
                    # Add newline after each signal
                    print()
            if(args.time is None):
                # Get signal values at all timestamps
                all_timestamps: List[str] = analyzer.get_all_timestamps()
                
                for signal_name in matching_signals:
                    print(f"=== {signal_name} ===")
                    # Get signal edges once to avoid repeated expensive calls
                    signal_edges: List[SignalResult] = analyzer.get_signal_edges(signal_name, args.verbose)
                    
                    for timestamp in all_timestamps:
                        value: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                        print(value.to_string(args.verbose, args.radix))
        
        else:
            # No command specified, do nothing
            pass
    
    except FileNotFoundError:
        print(f"Error: File '{args.vcd}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

