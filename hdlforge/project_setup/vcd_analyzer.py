#!/usr/bin/env python3
"""
VCD Analysis Tool with ArgParse

Professional VCD analysis tool with clean function separation, argparse for command-line handling,
and functions that return dictionaries or lists for easy integration.

Supports indexed mode for fast queries on large VCD files.
Index files are stored in .<vcd_filename>.idx/ folder.
"""

import argparse
import os
import pickle
import re
import sys
from pathlib import Path
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


def _sanitize_filename(signal_name: str) -> str:
    """Convert signal name to safe filename."""
    # Replace problematic characters with underscores
    safe_name = signal_name.replace('[', '_').replace(']', '_').replace('.', '_')
    safe_name = safe_name.replace('/', '_').replace('\\', '_').replace(':', '_')
    # Limit length to avoid filesystem issues
    if len(safe_name) > 200:
        safe_name = safe_name[:200]
    return safe_name + '.pkl'


def _analyze_global_clock(timestamps: List[str]) -> Dict[str, Any]:
    """
    Analyze global timestamps to deduce the design's clock period.
    
    VCD files record both rising and falling edges of clocks.
    If timestamps are evenly spaced (e.g., 0, 5000, 10000, 15000...),
    the actual clock period is 2x the spacing (e.g., 10000ps = 10ns).
    
    Returns:
        Dict with clock_period_ps, half_period_ps, frequency_mhz, is_uniform, analysis_msg
    """
    result = {
        'clock_period_ps': None,
        'half_period_ps': None,
        'frequency_mhz': None,
        'is_uniform': False,
        'analysis_msg': ''
    }
    
    if len(timestamps) < 3:
        result['analysis_msg'] = "[Clock Analysis] Not enough timestamps to analyze"
        return result
    
    # Sample first 100 timestamps
    ts_ints = [int(ts) for ts in timestamps[:100]]
    diffs = [ts_ints[i+1] - ts_ints[i] for i in range(len(ts_ints)-1)]
    
    if not diffs:
        result['analysis_msg'] = "[Clock Analysis] No timestamp differences"
        return result
    
    unique_diffs = set(diffs)
    
    if len(unique_diffs) == 1:
        half_period = diffs[0]
        clock_period = half_period * 2
        frequency_mhz = 1e12 / clock_period / 1e6
        
        result['clock_period_ps'] = clock_period
        result['half_period_ps'] = half_period
        result['frequency_mhz'] = frequency_mhz
        result['is_uniform'] = True
        result['analysis_msg'] = (
            f"[Clock Analysis]\n"
            f"  Timestamps uniformly spaced: {half_period}ps between edges\n"
            f"  Clock period: {clock_period}ps ({clock_period/1000}ns)\n"
            f"  Frequency: {frequency_mhz:.2f}MHz\n"
            f"  Using tick = {clock_period}ps for value sampling"
        )
    else:
        min_diff = min(diffs)
        max_diff = max(diffs)
        common_diff = max(set(diffs), key=diffs.count)
        result['analysis_msg'] = (
            f"[Clock Analysis]\n"
            f"  Non-uniform timestamp spacing\n"
            f"  Min: {min_diff}ps, Max: {max_diff}ps, Common: {common_diff}ps\n"
            f"  Using all timestamps"
        )
    
    return result


class VCDIndexedAnalyzer:
    """
    VCD analyzer with per-signal pickle index for fast queries.
    
    Index structure:
    .<vcd_filename>.idx/
        _meta.pkl       - metadata (vcd mtime, timescale)
        _signals.pkl    - list of all signal names
        _index.pkl      - signal_name -> {filename, width, var_id, msb, lsb}
        _timestamps.pkl - sorted list of all timestamps
        <signal>.pkl    - list of (timestamp, raw_value, hex, int, bin) tuples
    """
    
    def __init__(self, vcd_file: str) -> None:
        """Initialize analyzer - load from index or build new index."""
        self.vcd_file: str = vcd_file
        self.vcd_path: Path = Path(vcd_file).resolve()
        self.index_dir: Path = self.vcd_path.parent / f".{self.vcd_path.name}.idx"
        
        # Cached data (loaded on demand)
        self._meta: Optional[Dict[str, Any]] = None
        self._signals_list: Optional[List[str]] = None
        self._index: Optional[Dict[str, Dict[str, Any]]] = None
        self._timestamps: Optional[List[str]] = None
        self._loaded_signals: Dict[str, List[Tuple]] = {}  # Cache for loaded signal data
        
        # Check if index is valid
        if self._is_index_valid():
            self._load_index_metadata()
        else:
            self._build_index()
    
    def _is_index_valid(self) -> bool:
        """Check if index exists and is up-to-date with VCD file."""
        meta_file = self.index_dir / '_meta.pkl'
        if not meta_file.exists():
            return False
        
        try:
            with open(meta_file, 'rb') as f:
                meta = pickle.load(f)
            
            # Check if VCD file modification time matches
            vcd_mtime = os.path.getmtime(self.vcd_file)
            if meta.get('vcd_mtime') != vcd_mtime:
                return False
            
            # Check all required files exist
            required_files = ['_signals.pkl', '_index.pkl', '_timestamps.pkl']
            for fname in required_files:
                if not (self.index_dir / fname).exists():
                    return False
            
            return True
        except Exception:
            return False
    
    def _load_index_metadata(self) -> None:
        """Load index metadata files (not signal data)."""
        with open(self.index_dir / '_meta.pkl', 'rb') as f:
            self._meta = pickle.load(f)
        with open(self.index_dir / '_signals.pkl', 'rb') as f:
            self._signals_list = pickle.load(f)
        with open(self.index_dir / '_index.pkl', 'rb') as f:
            self._index = pickle.load(f)
        with open(self.index_dir / '_timestamps.pkl', 'rb') as f:
            self._timestamps = pickle.load(f)
    
    def _load_signal_data(self, signal_name: str) -> List[Tuple]:
        """Load signal data from its pickle file."""
        if signal_name in self._loaded_signals:
            return self._loaded_signals[signal_name]
        
        if self._index is None:
            self._load_index_metadata()
        
        if signal_name not in self._index:
            return []
        
        signal_info = self._index[signal_name]
        signal_file = self.index_dir / signal_info['filename']
        
        if not signal_file.exists():
            return []
        
        with open(signal_file, 'rb') as f:
            data = pickle.load(f)
        
        self._loaded_signals[signal_name] = data
        return data
    
    def _build_index(self) -> None:
        """Build index from VCD file."""
        print(f"Building VCD index for {self.vcd_file}...", file=sys.stderr)
        
        # Create index directory
        self.index_dir.mkdir(exist_ok=True)
        
        # Parse VCD file
        signals_info: Dict[str, Dict[str, Any]] = {}  # var_id -> {name, width, msb, lsb, full_path}
        signal_hierarchy: Dict[str, str] = {}  # var_id -> full_path
        scope_stack: List[str] = []
        
        # Per-signal change data: signal_name -> [(timestamp, raw, hex, int, bin), ...]
        signal_changes: Dict[str, List[Tuple]] = {}
        all_timestamps: set = set()
        
        with open(self.vcd_file, 'r') as f:
            # Parse header
            in_header = True
            for line in f:
                line = line.strip()
                
                if line.startswith('$scope'):
                    parts = line.split()
                    if len(parts) >= 4 and parts[1] == 'module' and parts[-1] == '$end':
                        scope_stack.append(parts[2])
                
                elif line.startswith('$upscope'):
                    if scope_stack:
                        scope_stack.pop()
                
                elif line.startswith('$var'):
                    self._parse_var_line(line, scope_stack, signals_info, signal_hierarchy)
                
                elif line.startswith('$enddefinitions'):
                    in_header = False
                    break
            
            # Initialize signal_changes for all signals
            for var_id, info in signals_info.items():
                signal_changes[info['full_path']] = []
            
            # Parse data section
            current_timestamp: Optional[str] = None
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('#'):
                    current_timestamp = line[1:]
                    all_timestamps.add(current_timestamp)
                else:
                    if current_timestamp is None:
                        continue
                    
                    var_id, value = self._parse_value_change(line)
                    if var_id and var_id in signals_info:
                        signal_info = signals_info[var_id]
                        signal_path = signal_info['full_path']
                        converted = self._convert_value(value, signal_info['width'])
                        
                        signal_changes[signal_path].append((
                            current_timestamp,
                            value,
                            converted['hex'],
                            converted['int'],
                            converted['bin']
                        ))
        
        # Sort timestamps
        sorted_timestamps = sorted(all_timestamps, key=int)
        
        # Analyze global clock from timestamps (ONE clock for entire design)
        global_clock = _analyze_global_clock(sorted_timestamps)
        
        # Build index mapping
        index_mapping: Dict[str, Dict[str, Any]] = {}
        signals_list: List[str] = []
        
        for var_id, info in signals_info.items():
            signal_name = info['full_path']
            signals_list.append(signal_name)
            
            # Get and sort signal data
            signal_data = signal_changes[signal_name]
            signal_data.sort(key=lambda x: int(x[0]))
            
            filename = _sanitize_filename(signal_name)
            index_mapping[signal_name] = {
                'filename': filename,
                'var_id': var_id,
                'width': info['width'],
                'msb': info['msb'],
                'lsb': info['lsb']
            }
            
            # Save signal data
            with open(self.index_dir / filename, 'wb') as f:
                pickle.dump(signal_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # Save metadata with global clock analysis
        meta = {
            'vcd_file': str(self.vcd_path),
            'vcd_mtime': os.path.getmtime(self.vcd_file),
            'num_signals': len(signals_list),
            'num_timestamps': len(sorted_timestamps),
            'clock': global_clock  # ONE global clock for entire design
        }
        
        with open(self.index_dir / '_meta.pkl', 'wb') as f:
            pickle.dump(meta, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        with open(self.index_dir / '_signals.pkl', 'wb') as f:
            pickle.dump(signals_list, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        with open(self.index_dir / '_index.pkl', 'wb') as f:
            pickle.dump(index_mapping, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        with open(self.index_dir / '_timestamps.pkl', 'wb') as f:
            pickle.dump(sorted_timestamps, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # Store in memory
        self._meta = meta
        self._signals_list = signals_list
        self._index = index_mapping
        self._timestamps = sorted_timestamps
        
        print(f"Index built: {len(signals_list)} signals, {len(sorted_timestamps)} timestamps", file=sys.stderr)
    
    def _parse_var_line(self, line: str, scope_stack: List[str], 
                        signals_info: Dict, signal_hierarchy: Dict) -> None:
        """Parse a $var definition line (supports wire and reg types)."""
        parts = line.split()
        if len(parts) < 6:
            return
        # Support both 'wire' and 'reg' types (ILA VCDs use 'reg')
        if parts[0] != '$var' or parts[1] not in ('wire', 'reg') or parts[-1] != '$end':
            return
        
        try:
            width = int(parts[2])
            var_id = parts[3]
            
            # Find signal name and range
            range_start_idx = -1
            for i in range(4, len(parts) - 1):
                if parts[i].startswith('[') and parts[i].endswith(']'):
                    range_start_idx = i
                    break
            
            if range_start_idx > 0:
                signal_name_parts = parts[4:range_start_idx]
                range_str = parts[range_start_idx][1:-1]
                if ':' in range_str:
                    msb, lsb = map(int, range_str.split(':'))
                else:
                    msb = lsb = int(range_str)
            else:
                signal_name_parts = parts[4:-1]
                msb = width - 1
                lsb = 0
            
            signal_name = ' '.join(signal_name_parts)
            full_path = '.'.join(scope_stack + [signal_name])
            
            signals_info[var_id] = {
                'name': signal_name,
                'width': width,
                'msb': msb,
                'lsb': lsb,
                'full_path': full_path
            }
            signal_hierarchy[var_id] = full_path
            
        except (ValueError, IndexError):
            pass
    
    def _parse_value_change(self, line: str) -> Tuple[str, str]:
        """Parse a value change line and return (var_id, value)."""
        if line.startswith('0') or line.startswith('1'):
            return line[1:], line[0]
        elif line.startswith('b'):
            match = re.match(r'b([01]+)\s+(\S+)', line)
            if match:
                return match.group(2), match.group(1)
        elif line.startswith('r'):
            match = re.match(r'r([0-9.+-eE]+)\s+(\S+)', line)
            if match:
                return match.group(2), match.group(1)
        return '', ''
    
    def _convert_value(self, raw_value: str, width: int) -> Dict[str, Any]:
        """Convert raw VCD value to multiple representations."""
        binary_value = raw_value
        
        if len(binary_value) < width:
            binary_value = binary_value.zfill(width)
        elif len(binary_value) > width:
            binary_value = binary_value[-width:]
        
        try:
            int_value = int(binary_value, 2)
        except ValueError:
            int_value = 0
        
        hex_width = (width + 3) // 4
        hex_value = f"0x{int_value:0{hex_width}x}"
        
        return {
            'hex': hex_value,
            'int': int_value,
            'bin': binary_value
        }
    
    # Public API - same as original VCDAnalyzer
    
    def get_all_timestamps(self) -> List[str]:
        """Get all timestamps in VCD file."""
        if self._timestamps is None:
            self._load_index_metadata()
        return self._timestamps
    
    def get_all_signal_names(self) -> List[str]:
        """Get all signal names in design."""
        if self._signals_list is None:
            self._load_index_metadata()
        return self._signals_list
    
    def find_signals(self, pattern: str) -> List[str]:
        """Find signals matching pattern using wildcard matching."""
        if self._signals_list is None:
            self._load_index_metadata()
        
        matching_signals: List[str] = []
        for signal_name in self._signals_list:
            if fnmatch(signal_name, pattern):
                matching_signals.append(signal_name)
        return matching_signals
    
    def find_submodules(self, module_path: str) -> List[str]:
        """Find all immediate sub-modules under module_path."""
        if self._signals_list is None:
            self._load_index_metadata()
        
        prefix = module_path + '.'
        submodules: set = set()
        
        for signal_name in self._signals_list:
            if signal_name.startswith(prefix):
                remainder = signal_name[len(prefix):]
                if '_inst' in remainder:
                    parts = remainder.split('.')
                    if parts[0].endswith('_inst'):
                        submodules.add(parts[0])
        
        return sorted(list(submodules))
    
    def find_signals_in_module(self, module_path: str) -> List[str]:
        """Find signals in module excluding sub-module signals."""
        if self._signals_list is None:
            self._load_index_metadata()
        
        prefix = module_path + '.'
        results: List[str] = []
        
        for signal_name in self._signals_list:
            if signal_name.startswith(prefix):
                remainder = signal_name[len(prefix):]
                if '_inst' not in remainder:
                    if 'unnamed' not in signal_name.lower() and 'clk' not in signal_name.lower():
                        results.append(signal_name)
        
        return results
    
    def find_pins_in_module(self, module_path: str) -> List[str]:
        """Find pin signals (_i or _o) in module excluding sub-module signals."""
        signals = self.find_signals_in_module(module_path)
        pins: List[str] = []
        
        for signal_name in signals:
            signal_basename = signal_name.split('.')[-1]
            if signal_basename.endswith('_i') or signal_basename.endswith('_o'):
                pins.append(signal_name)
            elif '_i[' in signal_basename or '_o[' in signal_basename:
                pins.append(signal_name)
            else:
                parts = signal_name.split('.')
                for part in parts:
                    if part.endswith('_i') or part.endswith('_o'):
                        pins.append(signal_name)
                        break
                    if '_i[' in part or '_o[' in part:
                        pins.append(signal_name)
                        break
        
        return pins
    
    def get_all_modules(self) -> List[str]:
        """Get all module paths from signal hierarchy."""
        if self._signals_list is None:
            self._load_index_metadata()
        
        modules: set = set()
        
        for signal_name in self._signals_list:
            parts = signal_name.split('.')
            for i in range(1, len(parts)):
                module_path = '.'.join(parts[:i])
                if module_path.endswith('_inst') or i == 1:
                    modules.add(module_path)
        
        return sorted(list(modules))
    
    def get_clock_info(self) -> Dict[str, Any]:
        """Get global clock analysis for the design."""
        if self._meta is None:
            self._load_index_metadata()
        return self._meta.get('clock', {})
    
    def get_clock_msg(self) -> str:
        """Get formatted clock analysis message."""
        clock = self.get_clock_info()
        return clock.get('analysis_msg', '[Clock Analysis] No clock info available')
    
    def _get_signal_metadata(self, signal_name: str) -> Dict[str, Any]:
        """Get metadata for a signal."""
        if self._index is None:
            self._load_index_metadata()
        
        if signal_name not in self._index:
            return {
                'var_id': None,
                'width': None,
                'msb': None,
                'lsb': None,
                'signal_definition': None
            }
        
        info = self._index[signal_name]
        return {
            'var_id': info['var_id'],
            'width': info['width'],
            'msb': info['msb'],
            'lsb': info['lsb'],
            'signal_definition': f"$var wire {info['width']} {info['var_id']} {signal_name.split('.')[-1]} [{info['msb']}:{info['lsb']}] $end"
        }
    
    def get_signal_edges(self, signal: str, verbose: bool = False) -> List[SignalResult]:
        """Get all edges for a signal with timestamps and values."""
        if not isinstance(signal, str):
            raise TypeError(f"signal must be a string, got {type(signal).__name__}")
        if not signal.strip():
            raise ValueError("signal cannot be empty or whitespace only")
        
        signal_data = self._load_signal_data(signal)
        signal_metadata = self._get_signal_metadata(signal)
        
        edges: List[SignalResult] = []
        for timestamp, raw, hex_val, int_val, bin_val in signal_data:
            edge = SignalResult(
                signal_name=signal,
                time=timestamp,
                calc_value={"hex": hex_val, "int": int_val, "bin": bin_val},
                raw_vcd=raw,
                width=signal_metadata['width'],
                last_vcd_time=timestamp,
                last_vcd_value=raw,
                note={"status": "exact timestamp in VCD"},
                var_id=signal_metadata['var_id'] if verbose else None,
                vcd_line=f"{raw}{signal_metadata['var_id']}" if verbose and signal_metadata['var_id'] else None,
                signal_definition=signal_metadata['signal_definition'] if verbose else None,
                msb=signal_metadata['msb'] if verbose else None,
                lsb=signal_metadata['lsb'] if verbose else None
            )
            edges.append(edge)
        return edges
    
    def _get_signal_value_from_edges(self, signal_edges: List[SignalResult], timestamp: str, 
                                      signal_name: str, verbose: bool = False) -> SignalResult:
        """Get signal value at specific timestamp from pre-loaded edges."""
        if not timestamp.strip():
            raise ValueError("timestamp cannot be empty or whitespace only")
        if not signal_name.strip():
            raise ValueError("signal_name cannot be empty or whitespace only")
        
        try:
            target_time_int = int(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: '{timestamp}'. Must be a number.")
        
        # Binary search for closest edge before or at target time
        closest_edge: Optional[SignalResult] = None
        for edge in signal_edges:
            edge_time_int = int(edge.time)
            if edge_time_int <= target_time_int:
                closest_edge = edge
            else:
                break
        
        if closest_edge is None:
            signal_metadata = self._get_signal_metadata(signal_name)
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
        
        signal_metadata = self._get_signal_metadata(signal_name)
        calc_value = {"hex": closest_edge.calc_value["hex"], 
                      "int": closest_edge.calc_value["int"], 
                      "bin": closest_edge.calc_value["bin"]}
        
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
    
    def get_signal_edges_from_timestamp(self, signal: str, timestamp: str, verbose: bool = False) -> List[SignalResult]:
        """Get all signal edges after the specified timestamp."""
        if not signal.strip():
            raise ValueError("signal cannot be empty or whitespace only")
        if not timestamp.strip():
            raise ValueError("timestamp cannot be empty or whitespace only")
        
        try:
            target_time_int = int(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: '{timestamp}'. Must be a number.")
        
        signal_edges = self.get_signal_edges(signal, verbose)
        
        if not signal_edges:
            raise ValueError(f'No data found for signal "{signal}"')
        
        filtered_edges: List[SignalResult] = []
        for edge in signal_edges:
            edge_time_int = int(edge.time)
            if edge_time_int > target_time_int:
                filtered_edges.append(edge)
        
        return filtered_edges
    
    def validate_signal_exists(self, signal: str) -> None:
        """Validate that a signal exists in the design."""
        if self._signals_list is None:
            self._load_index_metadata()
        
        if signal not in self._signals_list:
            available = self._signals_list[:10] if self._signals_list else []
            raise ValueError(f'Signal "{signal}" not found in design. Available signals: {available}')


# Keep original class as alias for backward compatibility
VCDAnalyzer = VCDIndexedAnalyzer


def verify_arguments(args: argparse.Namespace, analyzer: VCDIndexedAnalyzer) -> None:
    """Verify command-line arguments for consistency and validity."""
    active_commands: int = 0
    if args.timestamps:
        active_commands += 1
    if args.find_signal_names is not None:
        active_commands += 1
    if args.signal is not None:
        active_commands += 1
    
    if active_commands > 1:
        conflicting_args: List[str] = []
        if args.timestamps:
            conflicting_args.append('--timestamps')
        if args.find_signal_names is not None:
            conflicting_args.append('--find_signal_names')
        if args.signal is not None:
            conflicting_args.append('--signal')
        
        raise ValueError(f"Conflicting arguments provided. Only one command allowed at a time: {', '.join(conflicting_args)}")
    
    if args.time is not None:
        if args.signal is None:
            raise ValueError("--time can only be used with --signal")
        try:
            for timestamp in args.time:
                int(timestamp)
        except ValueError:
            raise ValueError(f"Invalid timestamp format for --time: '{args.time}'. All timestamps must be numbers.")
    
    if args.edge is not None:
        if args.signal is None:
            raise ValueError("--edge can only be used with --signal")
        if args.time is None:
            raise ValueError("--edge requires --time to be specified")
        if args.count is None:
            raise ValueError("--edge requires --count to specify number of edges to show.\n"
                           "Usage: --signal <name> --time <timestamp> --edge --count <N>\n"
                           "Example: --signal 'top.clk' --time 0 --edge --count 10")
    
    if args.count is not None:
        if args.signal is None:
            raise ValueError("--count can only be used with --signal")
        if args.time is None:
            raise ValueError("--count requires --time to be specified")
        if args.count <= 0:
            raise ValueError("--count must be > 0")
        if len(args.time) > 1:
            raise ValueError("--count can only be used with a single --time timestamp")
    
    if args.signal is not None and '*' not in args.signal and '?' not in args.signal:
        analyzer.validate_signal_exists(args.signal)


@typechecked
def main() -> None:
    """Main function with argparse setup and command dispatch."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='VCD Analysis Tool')
    
    parser.add_argument('--vcdfilename', required=True, help='VCD file to analyze')
    parser.add_argument('--timestamps', action='store_true', help='List all timestamps')
    parser.add_argument('--list_value_changes_in_module', help='Module path to list value changes (excludes sub-modules)')
    parser.add_argument('--get_modules_list', action='store_true', help='List all modules')
    parser.add_argument('--all', action='store_true', help='Show all signals in module (default: pin signals only)')
    parser.add_argument('--find_signal_names', '--signalnames', nargs='?', const='*', 
                        help='List signal names (optionally filter with wildcard pattern)')
    parser.add_argument('--signal', help='Signal name (supports wildcards)')
    parser.add_argument('--time', nargs='+', help='Filter signal results by timestamp(s) - can specify multiple timestamps')
    parser.add_argument('--edge', nargs='?', const=True, type=int, help='Show signal edges after the --time timestamp (requires --time). Optional number limits edges shown (must be >0)')
    parser.add_argument('--verbose', action='store_true', help='Show all VCD data including var_id, signal definition, and complete VCD metadata')
    parser.add_argument('--radix', choices=['hex', 'int', 'bin'], help='Output format for calc_value: hex, int, or bin. Without this flag, shows all formats in a dictionary')
    parser.add_argument('--count', type=int, help='Show count number of values starting from --time timestamp (requires --time, not allowed with --edge)')
    parser.add_argument('--rebuild-index', action='store_true', help='Force rebuild of VCD index')
    
    args: argparse.Namespace = parser.parse_args()
    
    try:
        # Handle rebuild-index flag
        if args.rebuild_index:
            vcd_path = Path(args.vcdfilename).resolve()
            index_dir = vcd_path.parent / f".{vcd_path.name}.idx"
            if index_dir.exists():
                import shutil
                shutil.rmtree(index_dir)
                print(f"Removed existing index: {index_dir}", file=sys.stderr)
        
        analyzer: VCDIndexedAnalyzer = VCDIndexedAnalyzer(args.vcdfilename)
        verify_arguments(args, analyzer)
        
        if args.timestamps:    
            for timestamp in analyzer.get_all_timestamps():
                print(timestamp)
        
        if args.find_signal_names is not None:
            pattern: str = args.find_signal_names
            filtered_signals: List[str] = analyzer.find_signals(pattern)
            
            if filtered_signals:
                for signal_name in filtered_signals:
                    print(signal_name)
            else:
                print("None")
        
        if args.signal is not None:
            matching_signals: List[str] = analyzer.find_signals(args.signal)
            
            if args.time is not None:
                for signal_name in matching_signals:
                    signal_edges: List[SignalResult] = analyzer.get_signal_edges(signal_name)
                    all_timestamps: List[str] = analyzer.get_all_timestamps()
                    has_edge = args.edge is not None
                    has_count = args.count is not None
                    
                    if has_edge:
                        # --edge mode: show N edges (value changes) after timestamp
                        # Validation ensures --count is provided with --edge
                        timestamp = args.time[0]
                        
                        # Always show value at time 0 first
                        print(f"\n=== value @ 0ns ===")
                        value_at_0: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, '0', signal_name, args.verbose)
                        value_at_0.note = {"status": "initial value"}
                        print(value_at_0.to_string(args.verbose, args.radix))
                        
                        # Show value at selected time (if not 0)
                        if timestamp != '0':
                            print(f"\n=== value @ {timestamp}ns ===")
                            value_at_time: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                            if timestamp in all_timestamps:
                                value_at_time.note = {"status": "exact timestamp in VCD"}
                            print(value_at_time.to_string(args.verbose, args.radix))
                        
                        # Show edges after the selected time
                        edges_after: List[SignalResult] = analyzer.get_signal_edges_from_timestamp(signal_name, timestamp, args.verbose)
                        
                        # Limit number of edges using --count
                        edges_after = edges_after[:args.count]
                        print(f"\n=== {args.count} edges after {timestamp}ns ===")
                        
                        for edge in edges_after:
                            edge.note = {"status": "exact timestamp in VCD"}
                            print(edge.to_string(args.verbose, args.radix))
                    
                    elif has_count:
                        # --count mode (without --edge): show value at N consecutive timestamps
                        start_timestamp = args.time[0]
                        
                        try:
                            start_time_int: int = int(start_timestamp)
                        except ValueError:
                            raise ValueError(f"Invalid timestamp format: '{start_timestamp}'. Must be a number.")
                        
                        timestamps_to_show: List[str] = [start_timestamp]
                        
                        for ts in all_timestamps:
                            if int(ts) > start_time_int:
                                timestamps_to_show.append(ts)
                        
                        timestamps_to_show.sort(key=int)
                        timestamps_to_show = timestamps_to_show[:args.count]
                        
                        print(f"\n=== {args.count} values starting from {start_timestamp}ns ===")
                        
                        for timestamp in timestamps_to_show:
                            value: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                            if timestamp == start_timestamp:
                                if timestamp in all_timestamps:
                                    value.note = {"status": "exact timestamp in VCD"}
                                else:
                                    value.note = {"status": f"calculated from last value at timestamp {start_timestamp}"}
                            else:
                                value.note = {"status": "exact timestamp in VCD"}
                            print(value.to_string(args.verbose, args.radix))
                    
                    else:
                        # Normal --time mode: just show value at specified timestamps
                        for timestamp in args.time:
                            timestamps_str = ",".join([f"{ts}ns" for ts in args.time])
                            print(f"\n=== value @ {timestamps_str} ===")
                            
                            exact_timestamp_exists: bool = timestamp in all_timestamps
                            
                            if exact_timestamp_exists:
                                value: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                                value.note = {"status": "exact timestamp in VCD"}
                                print(value.to_string(args.verbose, args.radix))
                            else:
                                calculated_value = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                                print(calculated_value.to_string(args.verbose, args.radix))
                    
                    print()
            
            if args.time is None:
                all_timestamps: List[str] = analyzer.get_all_timestamps()
                
                for signal_name in matching_signals:
                    print(f"=== {signal_name} ===")
                    signal_edges: List[SignalResult] = analyzer.get_signal_edges(signal_name, args.verbose)
                    
                    for timestamp in all_timestamps:
                        value: SignalResult = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, args.verbose)
                        print(value.to_string(args.verbose, args.radix))
        
        else:
            pass
    
    except FileNotFoundError:
        print(f"Error: File '{args.vcdfilename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
