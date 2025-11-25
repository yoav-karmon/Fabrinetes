"""DNA Reading Helper Functions"""

import re
from typing import Tuple, List
from .connect_and_read_dna import VivadoTCLConsole
from .tcl_helpers import send_tcl_command


def format_dna(dna_value: str) -> str:
    """Format DNA value (remove 0x prefix and leading zeros)."""
    dna = dna_value.strip()
    if dna.startswith('0x'):
        dna = dna[2:]
    dna = dna.lstrip('0') or '0'
    return dna.upper()


def read_dna_fuse(console: VivadoTCLConsole) -> str:
    """Try to read DNA using REGISTER.EFUSE.FUSE_DNA."""
    output = send_tcl_command(console, r"set chip_dna [get_property REGISTER.EFUSE.FUSE_DNA $hw_device]; puts $chip_dna", timeout=2)
    
    for line in output.split('\n'):
        line = line.strip()
        if not line or any(line.startswith(x) for x in ['%', 'vivado', 'INFO', 'WARNING', 'ERROR']):
            continue
        match = re.search(r'0x([0-9A-Fa-f]+)', line, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        match = re.search(r'([0-9A-Fa-f]{20,})', line, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return ""


def read_dna_slr0(console: VivadoTCLConsole) -> str:
    """Try to read DNA using REGISTER.DNA.SLR0."""
    output = send_tcl_command(console, r"set chip_dna [get_property REGISTER.DNA.SLR0 $hw_device]; puts $chip_dna", timeout=2)
    
    for line in output.split('\n'):
        line = line.strip()
        if not line or any(line.startswith(x) for x in ['%', 'vivado', 'INFO', 'WARNING', 'ERROR']):
            continue
        match = re.search(r'0x([0-9A-Fa-f]+)', line, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        match = re.search(r'([0-9A-Fa-f]{20,})', line, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return ""


def read_all_slr_dna(console: VivadoTCLConsole) -> List[str]:
    """Read all SLR DNA values."""
    all_dna_values = []
    for slr in ['SLR0', 'SLR1', 'SLR2', 'SLR3']:
        output = send_tcl_command(console, rf"set slr_dna [get_property REGISTER.DNA.{slr} $hw_device]; puts $slr_dna", timeout=2)
        for line in output.split('\n'):
            line = line.strip()
            if not line or any(line.startswith(x) for x in ['%', 'vivado', 'INFO', 'WARNING', 'ERROR']):
                continue
            match = re.search(r'0x([0-9A-Fa-f]+)', line, re.IGNORECASE)
            if match:
                slr_dna = match.group(1).upper().lstrip('0') or '0'
                if len(slr_dna) >= 16:
                    all_dna_values.append(f"{slr}: {slr_dna}")
                break
    return all_dna_values


def read_chip_dna(console: VivadoTCLConsole) -> Tuple[str, List[str]]:
    """Main DNA reading function - tries all methods."""
    print("Reading chip DNA...")
    
    # Method 1: Try REGISTER.EFUSE.FUSE_DNA
    chip_dna = read_dna_fuse(console)
    if chip_dna:
        print("Successfully read DNA using REGISTER.EFUSE.FUSE_DNA")
        all_dna_values = read_all_slr_dna(console)
        return chip_dna, all_dna_values
    
    # Method 2: Try REGISTER.DNA.SLR0
    chip_dna = read_dna_slr0(console)
    if chip_dna:
        print("Successfully read DNA using REGISTER.DNA.SLR0")
        all_dna_values = read_all_slr_dna(console)
        return chip_dna, all_dna_values
    
    return "", []


def display_dna_result(chip_dna: str, all_dna_values: List[str], hw_device: str) -> bool:
    """Display DNA result."""
    if chip_dna:
        formatted_dna = format_dna(chip_dna)
        print("=" * 50)
        if len(all_dna_values) > 1:
            print("Chip DNA (Multiple SLRs detected):")
            print(f"  SLR0: {formatted_dna}")
            for dna_entry in all_dna_values:
                if not dna_entry.startswith("SLR0"):
                    print(f"  {dna_entry}")
            print()
            print(f"Primary DNA (SLR0 / REGISTER.EFUSE.FUSE_DNA): {formatted_dna}")
        else:
            print(f"Chip DNA (REGISTER.EFUSE.FUSE_DNA): {formatted_dna}")
        print("=" * 50)
        return True
    else:
        print("=" * 50)
        print("WARNING: Unable to read chip DNA")
        print("=" * 50)
        print("Possible reasons:")
        print("  1. Device may need to be opened/programmed first")
        print("  2. Device family may not support DNA reading")
        print("  3. Hardware target may need to be refreshed")
        print()
        print(f"Device: {hw_device}")
        return False

