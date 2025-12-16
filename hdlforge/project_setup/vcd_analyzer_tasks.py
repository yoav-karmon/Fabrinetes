#!/usr/bin/env python3
"""
VCD Analyzer task handler for HDLForge
Wrapper around vcd_analyzer.py for integration with hdlforge tool command
"""

import sys
import shutil
from pathlib import Path
from vcd_analyzer import VCDIndexedAnalyzer


def vcd_analyzer(c, **kwargs):
    """
    VCD Analyzer command handler
    
    Args:
        c: Invoke context
        **kwargs: VCD analyzer arguments
    """
    # Map kwargs to argparse-like namespace
    class Args:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    args = Args(**kwargs)
    
    # Validate required arguments
    if not getattr(args, 'vcd', None):
        print("[!x!] VCD file must be specified with --vcdfilename")
        print("[i] Usage: hdlforge --tool vcd_analyzer --vcdfilename <vcd_file> [options]")
        sys.exit(1)
    
    # Handle rebuild-index flag
    if getattr(args, 'rebuild_index', False):
        vcd_path = Path(args.vcd).resolve()
        index_dir = vcd_path.parent / f".{vcd_path.name}.idx"
        if index_dir.exists():
            shutil.rmtree(index_dir)
            print(f"Removed existing index: {index_dir}", file=sys.stderr)
    
    try:
        analyzer = VCDIndexedAnalyzer(args.vcd)
        
        # Handle --get_modules_list
        if getattr(args, 'get_modules_list', False):
            modules = analyzer.get_all_modules()
            for module in modules:
                print(module)
            return
        
        # Handle --find_signal_names / --signalnames
        signal_pattern = getattr(args, 'find_signal_names', None)
        if signal_pattern is not None:
            matching_signals = analyzer.find_signals(signal_pattern)
            if matching_signals:
                for signal_name in matching_signals:
                    print(signal_name)
            else:
                print("None")
            return
        
        # Handle --get_values_pins (mapped from list_value_changes_in_module for backward compatibility)
        module_path = getattr(args, 'list_value_changes_in_module', None)
        if module_path is not None:
            use_all = getattr(args, 'all', False)
            
            if use_all:
                signals = analyzer.find_signals_in_module(module_path)
            else:
                signals = analyzer.find_pins_in_module(module_path)
            
            if not signals:
                print("None")
                return
            
            start_time = '0'
            all_timestamps = analyzer.get_all_timestamps()
            clock_info = analyzer.get_clock_info()
            clock_period = clock_info.get('clock_period_ps')
            human = getattr(args, 'human', False)
            
            module_prefix = module_path + '.'
            
            # First pass: collect all signal ranges and values
            signal_data = []
            for signal_name in signals:
                signal_metadata = analyzer._get_signal_metadata(signal_name)
                width = signal_metadata.get('width', 1)
                if width == 0:
                    width = 1
                
                # Remove module prefix from signal name for display
                if signal_name.startswith(module_prefix):
                    display_name = signal_name[len(module_prefix):]
                else:
                    display_name = signal_name
                
                if width == 1:
                    signal_range = f"{display_name}[0]"
                else:
                    signal_range = f"{display_name}[{width-1}:0]"
                
                signal_edges = analyzer.get_signal_edges(signal_name)
                value_at_0 = analyzer._get_signal_value_from_edges(signal_edges, '0', signal_name, False)
                hex_val_0 = value_at_0.calc_value.get('hex', '0x0')
                time_ps_0 = int('0')
                if clock_period:
                    time_ns_0 = time_ps_0 / 1000.0
                    if time_ns_0 == int(time_ns_0):
                        time_str_0 = f"{hex_val_0}@{int(time_ns_0)}"
                    else:
                        time_str_0 = f"{hex_val_0}@{time_ns_0}"
                else:
                    time_str_0 = f"{hex_val_0}@{time_ps_0}"
                
                values = [time_str_0]
                
                if start_time != '0':
                    value_at_start = analyzer._get_signal_value_from_edges(signal_edges, start_time, signal_name, False)
                    hex_val_start = value_at_start.calc_value.get('hex', '0x0')
                    time_ps_start = int(start_time)
                    if clock_period:
                        time_ns_start = time_ps_start / 1000.0
                        if time_ns_start == int(time_ns_start):
                            time_str_start = f"{hex_val_start}@{int(time_ns_start)}"
                        else:
                            time_str_start = f"{hex_val_start}@{time_ns_start}"
                    else:
                        time_str_start = f"{hex_val_start}@{time_ps_start}"
                    values.append(time_str_start)
                
                try:
                    edges_after = analyzer.get_signal_edges_from_timestamp(signal_name, start_time, False)
                except ValueError:
                    edges_after = []
                
                for edge in edges_after:
                    hex_val = edge.calc_value.get('hex', '0x0')
                    time_ps = int(edge.time)
                    if clock_period:
                        time_ns = time_ps / 1000.0
                        if time_ns == int(time_ns):
                            time_str = f"{hex_val}@{int(time_ns)}"
                        else:
                            time_str = f"{hex_val}@{time_ns}"
                    else:
                        time_str = f"{hex_val}@{time_ps}"
                    values.append(time_str)
                
                values_str = ','.join(values)
                signal_data.append((signal_range, values_str))
            
            # Find max length for padding if human-readable
            if human:
                max_len = max(len(signal_range) for signal_range, _ in signal_data)
            
            # Print all signals
            for signal_range, values_str in signal_data:
                if human:
                    padded_signal = signal_range.ljust(max_len)
                    print(f"{padded_signal} edges in ns:{values_str}")
                else:
                    print(f"{signal_range} edges in ns:{values_str}")
            return
    
    except FileNotFoundError:
        print(f"Error: File '{args.vcd}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
