#!/usr/bin/env python3
"""
VCD Analyzer task handler for HDLForge
Wrapper around vcd_analyzer.py for integration with hdlforge tool command
"""

import sys
import shutil
from pathlib import Path
from typing import Optional, List, Tuple
from vcd_analyzer import VCDAnalyzer, SignalResult


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
        analyzer = VCDAnalyzer(args.vcd)
        
        # Handle --timestamps
        if getattr(args, 'timestamps', False):
            for timestamp in analyzer.get_all_timestamps():
                print(timestamp)
            return
        
        # Handle --find_signal_names
        if getattr(args, 'find_signal_names', None) is not None:
            pattern = args.find_signal_names
            filtered_signals = analyzer.find_signals(pattern)
            if filtered_signals:
                for signal_name in filtered_signals:
                    print(signal_name)
            else:
                print("None")
            return
        
        # Handle signal queries with --value or --edge
        signal = getattr(args, 'signal', None)
        if signal is None:
            return
        
        has_value = getattr(args, 'value', False)
        has_edge = getattr(args, 'edge', False)
        
        # Validate: --value or --edge must be specified
        if not has_value and not has_edge:
            print("[!x!] Either --value or --edge must be specified with --signal")
            print("[i] Usage:")
            print("[i]   --signal <name> --value [--time <t>] [--count <n>]  # Show values at timestamps")
            print("[i]   --signal <name> --edge [--time <t>] [--count <n>]   # Show value changes only")
            sys.exit(1)
        
        if has_value and has_edge:
            print("[!x!] --value and --edge are mutually exclusive")
            sys.exit(1)
        
        # Get parameters with defaults
        start_time = getattr(args, 'time', '0') or '0'
        count = getattr(args, 'count', None)  # None means all
        verbose = getattr(args, 'verbose', False)
        radix = getattr(args, 'radix', None)
        
        # Find matching signals
        matching_signals = analyzer.find_signals(signal)
        if not matching_signals:
            print(f"[!x!] No signals match pattern: {signal}")
            sys.exit(1)
        
        # Get all timestamps and global clock info (cached in index)
        all_timestamps = analyzer.get_all_timestamps()
        clock_info = analyzer.get_clock_info()
        no_clock = getattr(args, 'no_clock', False)
        clock_period = None if no_clock else clock_info.get('clock_period_ps')
        
        # Print global clock analysis (once)
        if no_clock:
            print("[Clock Analysis] Disabled (--no-clock)")
        else:
            print(analyzer.get_clock_msg())
        print()
        
        # Process each matching signal
        for signal_name in matching_signals:
            signal_edges = analyzer.get_signal_edges(signal_name)
            
            if has_edge:
                # --edge mode: show actual value changes
                print(f"=== {signal_name} edges ===")
                
                # Show value at time 0
                print(f"\n--- Initial value @ 0ns ---")
                value_at_0 = analyzer._get_signal_value_from_edges(signal_edges, '0', signal_name, verbose)
                value_at_0.note = {"status": "initial value"}
                print(value_at_0.to_string(verbose, radix))
                
                # Show value at start time (if not 0)
                if start_time != '0':
                    print(f"\n--- Value @ {start_time}ns ---")
                    value_at_start = analyzer._get_signal_value_from_edges(signal_edges, start_time, signal_name, verbose)
                    if start_time in all_timestamps:
                        value_at_start.note = {"status": "exact timestamp in VCD"}
                    print(value_at_start.to_string(verbose, radix))
                
                # Get edges after start time
                try:
                    edges_after = analyzer.get_signal_edges_from_timestamp(signal_name, start_time, verbose)
                except ValueError:
                    edges_after = []
                
                # Limit count
                if count is not None:
                    edges_after = edges_after[:count]
                    print(f"\n--- {count} edges after {start_time}ns ---")
                else:
                    print(f"\n--- All edges after {start_time}ns ({len(edges_after)} total) ---")
                
                for edge in edges_after:
                    edge.note = {"status": "value change"}
                    print(edge.to_string(verbose, radix))
            
            else:
                # --value mode: show values at consecutive timestamps
                print(f"=== {signal_name} values ===")
                
                try:
                    start_time_int = int(start_time)
                except ValueError:
                    print(f"[!x!] Invalid timestamp: {start_time}")
                    sys.exit(1)
                
                # Build list of timestamps to sample
                if clock_period and clock_info.get('is_uniform'):
                    # Use global clock period for tick-aligned sampling
                    print(f"[Sampling] Using clock period {clock_period}ps")
                    timestamps_to_show = []
                    
                    for ts in all_timestamps:
                        ts_int = int(ts)
                        if ts_int >= start_time_int:
                            if (ts_int - start_time_int) % clock_period == 0 or ts_int == start_time_int:
                                timestamps_to_show.append(ts)
                else:
                    # Non-uniform clock, use all timestamps
                    print(f"[Sampling] Using all timestamps")
                    timestamps_to_show = [ts for ts in all_timestamps if int(ts) >= start_time_int]
                
                # Limit count
                if count is not None:
                    timestamps_to_show = timestamps_to_show[:count]
                    print(f"--- {count} values starting from {start_time}ns ---")
                else:
                    print(f"--- All values starting from {start_time}ns ({len(timestamps_to_show)} total) ---")
                
                print()
                for ts in timestamps_to_show:
                    value = analyzer._get_signal_value_from_edges(signal_edges, ts, signal_name, verbose)
                    value.note = {"status": "sampled value"}
                    print(value.to_string(verbose, radix))
            
            print()  # Newline between signals
    
    except FileNotFoundError:
        print(f"Error: File '{args.vcd}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
