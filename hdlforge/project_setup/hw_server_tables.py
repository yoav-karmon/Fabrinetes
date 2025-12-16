#!/usr/bin/env python3
"""
Table Printing Utilities for HW Server Tool (standalone version).

Provides formatted table output for ILA and VIO probes without external dependencies.
"""

from typing import List, Dict


def print_vio_table(probes_data: List[Dict]) -> None:
    """Print VIO probes as formatted table."""
    if not probes_data:
        print("    No probes found")
        return
    
    # Column widths - removed Sync column since all values are from hardware after refresh
    headers = ["Dir", "Probe Name", "Width", "Value"]
    widths = [max(len(headers[0]), 4),  # Dir
              max(len(headers[1]), max(len(p['name']) for p in probes_data)),  # Name
              max(len(headers[2]), max(len(p['width']) for p in probes_data)),  # Width
              max(len(headers[3]), max(len(str(p['value'])) for p in probes_data))]  # Value
    
    # Print header
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(f"    {sep}")
    header_row = "|" + "|".join(f" {h:^{w}} " for h, w in zip(headers, widths)) + "|"
    print(f"    {header_row}")
    print(f"    {sep}")
    
    # Print rows
    for p in probes_data:
        row = "|" + "|".join([
            f" {p['dir']:^{widths[0]}} ",
            f" {p['name']:<{widths[1]}} ",
            f" {p['width']:>{widths[2]}} ",
            f" {p['value']:>{widths[3]}} "
        ]) + "|"
        print(f"    {row}")
    
    print(f"    {sep}")


def print_ila_table(probes_data: List[Dict]) -> None:
    """Print ILA probes as formatted table with common path extracted."""
    if not probes_data:
        print("    No probes found")
        return
    
    # Find common prefix path using / or . as separators
    names = [p['name'] for p in probes_data]
    prefix = _find_common_prefix(names)
    
    # Print common path if found
    if prefix and len(prefix) > 10:
        print(f"    Path: {prefix}")
        # Strip prefix from names
        for p in probes_data:
            p['short_name'] = p['name'][len(prefix):] if p['name'].startswith(prefix) else p['name']
    else:
        for p in probes_data:
            p['short_name'] = p['name']
    
    # Column widths
    headers = ["Dir", "Signal", "Width", "Value"]
    widths = [max(len(headers[0]), 2),  # Dir (always <-)
              max(len(headers[1]), max(len(p['short_name']) for p in probes_data)),  # Signal
              max(len(headers[2]), max(len(p['width']) for p in probes_data)),  # Width
              max(len(headers[3]), max(len(str(p.get('value', '-'))) for p in probes_data))]  # Value
    
    # Print header
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(f"    {sep}")
    header_row = "|" + "|".join(f" {h:^{w}} " for h, w in zip(headers, widths)) + "|"
    print(f"    {header_row}")
    print(f"    {sep}")
    
    # Print rows
    for p in probes_data:
        row = "|" + "|".join([
            f" {'<-':^{widths[0]}} ",
            f" {p['short_name']:<{widths[1]}} ",
            f" {p['width']:>{widths[2]}} ",
            f" {p.get('value', '-'):>{widths[3]}} "
        ]) + "|"
        print(f"    {row}")
    
    print(f"    {sep}")


def print_ila_triggers_table(triggers_data: List[Dict]) -> None:
    """Print ILA triggers as separate formatted table."""
    if not triggers_data:
        return
    
    print("\n    --- Triggers Set ---")
    
    # Column widths
    headers = ["Signal", "Width", "Trigger Value"]
    
    # Get short signal names
    for t in triggers_data:
        t['short_name'] = t['name'].split('/')[-1].split('.')[-1]
    
    widths = [max(len(headers[0]), max(len(t['short_name']) for t in triggers_data)),
              max(len(headers[1]), max(len(t['width']) for t in triggers_data)),
              max(len(headers[2]), max(len(t['trigger']) for t in triggers_data))]
    
    # Print header
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(f"    {sep}")
    header_row = "|" + "|".join(f" {h:^{w}} " for h, w in zip(headers, widths)) + "|"
    print(f"    {header_row}")
    print(f"    {sep}")
    
    # Print rows
    for t in triggers_data:
        row = "|" + "|".join([
            f" {t['short_name']:<{widths[0]}} ",
            f" {t['width']:>{widths[1]}} ",
            f" {t['trigger']:>{widths[2]}} "
        ]) + "|"
        print(f"    {row}")
    
    print(f"    {sep}")


def _find_common_prefix(names: List[str]) -> str:
    """Find longest common prefix using / or . as separators."""
    if len(names) <= 1:
        return ""
    
    # Find longest common prefix character by character
    prefix = ""
    for chars in zip(*names):
        if len(set(chars)) == 1:
            prefix += chars[0]
        else:
            break
    
    # Trim to last separator (/ or .)
    last_sep = max(prefix.rfind('/'), prefix.rfind('.'))
    if last_sep > 0:
        return prefix[:last_sep + 1]
    return ""

