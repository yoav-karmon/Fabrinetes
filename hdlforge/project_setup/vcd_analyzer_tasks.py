#!/usr/bin/env python3
"""
VCD Analyzer task handler for HDLForge
Wrapper around vcd_analyzer.py for integration with hdlforge tool command
"""

import sys
from typing import Optional
from vcd_analyzer import VCDAnalyzer, verify_arguments, SignalResult


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
    
    # Create args object from kwargs
    args = Args(**kwargs)
    
    # Validate required arguments
    if not hasattr(args, 'vcd') or not args.vcd:
        print("[!x!] VCD file must be specified with --vcd")
        print("[i] Usage: hdlforge tool --vcd_analyzer --vcd <vcd_file> [options]")
        sys.exit(1)
    
    try:
        analyzer = VCDAnalyzer(args.vcd)
        verify_arguments(args, analyzer)
        
        if hasattr(args, 'timestamps') and args.timestamps:
            for timestamp in analyzer.get_all_timestamps():
                print(timestamp)
        
        if hasattr(args, 'signalnames') and args.signalnames is not None:
            # Filter signal names with wildcard pattern using cache
            pattern = args.signalnames
            filtered_signals = analyzer.find_signals(pattern)
            
            if filtered_signals:
                for signal_name in filtered_signals:
                    print(signal_name)
            else:
                print("None")
        
        if hasattr(args, 'signal') and args.signal is not None:
            # First run find_signals to get matching signals
            matching_signals = analyzer.find_signals(args.signal)
            
            if hasattr(args, 'time') and args.time is not None:
                # Filter signal results by time(s) - can be multiple timestamps
                for signal_name in matching_signals:
                    # Get signal edges once to avoid repeated expensive calls
                    signal_edges = analyzer.get_signal_edges(signal_name)
                    
                    verbose = getattr(args, 'verbose', False)
                    radix = getattr(args, 'radix', None)
                    
                    if hasattr(args, 'count') and args.count is not None:
                        # --count mode: show count number of values starting from --time timestamp
                        start_timestamp = args.time[0]  # Only single timestamp allowed with --count
                        all_timestamps = analyzer.get_all_timestamps()
                        
                        # Find the starting timestamp index
                        try:
                            start_time_int = int(start_timestamp)
                        except ValueError:
                            raise ValueError(f"Invalid timestamp format: '{start_timestamp}'. Must be a number.")
                        
                        # Always start with the requested timestamp
                        timestamps_to_show = [start_timestamp]
                        
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
                            value = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, verbose)
                            if timestamp == start_timestamp:
                                # First timestamp is always the requested one
                                if timestamp in all_timestamps:
                                    value.note = {"status": "exact timestamp in VCD"}
                                else:
                                    value.note = {"status": f"calculated from last value at timestamp {start_timestamp}"}
                            else:
                                # Subsequent timestamps are from VCD
                                value.note = {"status": "exact timestamp in VCD"}
                            print(value.to_string(verbose, radix))
                    
                    else:
                        # Normal --time mode: show values for specified timestamps
                        # Print combined header for all timestamps
                        timestamps_str = ",".join([f"{ts}ns" for ts in args.time])
                        print(f"\n=== value @ {timestamps_str} ===")
                        
                        # Process each requested timestamp
                        for timestamp in args.time:
                            # Check if exact timestamp exists in VCD
                            all_timestamps = analyzer.get_all_timestamps()
                            exact_timestamp_exists = timestamp in all_timestamps
                            
                            if exact_timestamp_exists:
                                # Exact timestamp found, show normally
                                value = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, verbose)
                                # Override status for exact timestamp
                                value.note = {"status": "exact timestamp in VCD"}
                                print(value.to_string(verbose, radix))
                            else:
                                # Exact timestamp not found, show calculated value for requested timestamp
                                calculated_value = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, verbose)
                                print(calculated_value.to_string(verbose, radix))
                            
                            # If --edge flag is used, show edges after this timestamp
                            if hasattr(args, 'edge') and args.edge is not None:
                                edges_after = analyzer.get_signal_edges_from_timestamp(signal_name, timestamp, verbose)
                                
                                # Limit number of edges if specified and update header accordingly
                                if isinstance(args.edge, int) and not isinstance(args.edge, bool):
                                    edges_after = edges_after[:args.edge]
                                    print(f"\n=== '{args.edge}' edges after {timestamp}ns ===")
                                else:
                                    print(f"\n=== all edges after {timestamp}ns ===")
                                
                                for edge in edges_after:
                                    edge.note = {"status": "exact timestamp in VCD"}
                                    print(edge.to_string(verbose, radix))
                    
                    # Add newline after each signal
                    print()
            
            if not (hasattr(args, 'time') and args.time is not None):
                # Get signal values at all timestamps
                all_timestamps = analyzer.get_all_timestamps()
                verbose = getattr(args, 'verbose', False)
                radix = getattr(args, 'radix', None)
                
                for signal_name in matching_signals:
                    print(f"=== {signal_name} ===")
                    # Get signal edges once to avoid repeated expensive calls
                    signal_edges = analyzer.get_signal_edges(signal_name, verbose)
                    
                    for timestamp in all_timestamps:
                        value = analyzer._get_signal_value_from_edges(signal_edges, timestamp, signal_name, verbose)
                        print(value.to_string(verbose, radix))
    
    except FileNotFoundError:
        print(f"Error: File '{args.vcd}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

