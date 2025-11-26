#!/usr/bin/env python3
"""
Network task handlers for HDLForge
Network utilities and raw packet sending
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
import struct
import socket
import subprocess

# Import shared functions from toolbox_tasks (for backward compatibility during transition)
from toolbox_tasks import (
    list_network_interfaces,
    print_available_interfaces,
    get_interface_mac,
    send_raw_bytes,
    create_ethernet_header,
    create_arp_packet,
    create_icmp_packet,
    create_udp_packet,
    create_ipv4_header,
    calculate_checksum
)


def network(c, tool: Optional[str] = None, **kwargs):
    """
    Network command handler
    
    Args:
        c: Invoke context
        tool: Tool name to execute (send_raw, send_arp, send_icmp, send_udp)
        **kwargs: Tool-specific arguments
    """
    if tool == "send_raw" or tool is None:
        # Send raw bytes
        interface = kwargs.get('interface')
        data_hex = kwargs.get('data')
        
        if not interface:
            print("[!x!] Interface must be specified with --interface")
            print_available_interfaces()
            print("[i] Usage: hdlforge tool --network send_raw --interface <interface> --data <hex_string>")
            sys.exit(1)
        
        if not data_hex:
            print("[!x!] Data must be specified with --data")
            print("[i] Usage: hdlforge tool --network send_raw --interface <interface> --data <hex_string>")
            sys.exit(1)
        
        try:
            data = bytes.fromhex(data_hex.replace(' ', '').replace(':', ''))
        except ValueError as e:
            print(f"[!x!] Invalid hex data: {e}")
            sys.exit(1)
        
        # Note: Raw socket on Linux expects Ethernet frame (minimum 14 bytes for header)
        # If data is less than 14 bytes, it might fail. User should provide full Ethernet frame.
        if len(data) < 14:
            print("[!] Warning: Data is less than 14 bytes (Ethernet header size)")
            print("[i] For raw socket, provide full Ethernet frame or use protocol-specific tools")
        
        send_raw_bytes(interface, data, kwargs.get('verbose', False))
    
    elif tool == "send_arp":
        # Send ARP packet
        interface = kwargs.get('interface')
        op = kwargs.get('arp_op') if kwargs.get('arp_op') is not None else 1  # 1=request, 2=reply
        src_mac = kwargs.get('src_mac') or "00:00:00:00:00:00"
        src_ip = kwargs.get('src_ip') or "192.168.1.1"
        dst_mac = kwargs.get('dst_mac') or "00:00:00:00:00:00"
        dst_ip = kwargs.get('dst_ip') or "192.168.1.2"
        
        # Ethernet MAC addresses (separate from ARP MAC addresses)
        # For ARP requests, default to broadcast destination
        eth_dst_mac = kwargs.get('eth_dst_mac')
        if not eth_dst_mac:
            eth_dst_mac = "ff:ff:ff:ff:ff:ff" if op == 1 else dst_mac  # Broadcast for requests, target MAC for replies
        
        # Get interface MAC address if eth_src_mac not specified
        eth_src_mac = kwargs.get('eth_src_mac')
        if not eth_src_mac:
            interface_mac = get_interface_mac(interface) if interface else None
            if interface_mac:
                eth_src_mac = interface_mac
            else:
                eth_src_mac = src_mac  # Fallback to ARP src_mac if interface MAC not found
        
        if not interface:
            print("[!x!] Interface must be specified with --interface")
            print_available_interfaces()
            print("[i] Usage: hdlforge tool --network send_arp --interface <interface> [options]")
            sys.exit(1)
        
        # Show defaults if verbose or if using defaults
        defaults_used = []
        if kwargs.get('arp_op') is None:
            defaults_used.append(f"arp_op=1 (request)")
        if not kwargs.get('eth_dst_mac'):
            defaults_used.append(f"eth_dst_mac={eth_dst_mac} (broadcast for requests)")
        if not kwargs.get('eth_src_mac'):
            defaults_used.append(f"eth_src_mac={eth_src_mac} (from interface)")
        if not kwargs.get('src_mac'):
            defaults_used.append(f"src_mac={src_mac}")
        if not kwargs.get('src_ip'):
            defaults_used.append(f"src_ip={src_ip}")
        if not kwargs.get('dst_mac'):
            defaults_used.append(f"dst_mac={dst_mac}")
        if not kwargs.get('dst_ip'):
            defaults_used.append(f"dst_ip={dst_ip}")
        
        if defaults_used:
            print("[i] Using default values:")
            for default in defaults_used:
                print(f"    • {default}")
        
        # Create ARP packet
        arp_packet = create_arp_packet(op, src_mac, src_ip, dst_mac, dst_ip)
        
        # Create Ethernet header with ARP type
        eth_header = create_ethernet_header(eth_dst_mac, eth_src_mac, 0x0806)  # 0x0806 = ARP
        
        # Combine Ethernet header + ARP packet
        full_packet = eth_header + arp_packet
        
        print(f"[i] Sending ARP packet (op={op}) on interface {interface}")
        send_raw_bytes(interface, full_packet, kwargs.get('verbose', False))
    
    elif tool == "send_icmp":
        # Send ICMP packet
        interface = kwargs.get('interface')
        src_mac = kwargs.get('src_mac') or "00:00:00:00:00:00"
        dst_mac = kwargs.get('dst_mac') or "ff:ff:ff:ff:ff:ff"
        src_ip = kwargs.get('src_ip') or "192.168.1.1"
        dst_ip = kwargs.get('dst_ip') or "192.168.1.2"
        icmp_type = kwargs.get('icmp_type') if kwargs.get('icmp_type') is not None else 8
        icmp_code = kwargs.get('icmp_code') if kwargs.get('icmp_code') is not None else 0
        identifier = kwargs.get('identifier') if kwargs.get('identifier') is not None else 0
        sequence = kwargs.get('sequence') if kwargs.get('sequence') is not None else 0
        data_str = kwargs.get('data') or ''
        
        if not interface:
            print("[!x!] Interface must be specified with --interface")
            print_available_interfaces()
            print("[i] Usage: hdlforge tool --network send_icmp --interface <interface> [options]")
            sys.exit(1)
        
        # Get interface MAC address if eth_src_mac not specified
        eth_src_mac = kwargs.get('eth_src_mac')
        if not eth_src_mac:
            interface_mac = get_interface_mac(interface) if interface else None
            if interface_mac:
                eth_src_mac = interface_mac
            else:
                eth_src_mac = src_mac  # Fallback to src_mac if interface MAC not found
        
        # Ethernet destination MAC
        eth_dst_mac = kwargs.get('eth_dst_mac') or dst_mac
        
        # Show defaults if using defaults
        defaults_used = []
        if not kwargs.get('eth_src_mac'):
            defaults_used.append(f"eth_src_mac={eth_src_mac} (from interface)")
        if not kwargs.get('eth_dst_mac'):
            defaults_used.append(f"eth_dst_mac={eth_dst_mac}")
        if not kwargs.get('src_mac'):
            defaults_used.append(f"src_mac={src_mac}")
        if not kwargs.get('dst_mac'):
            defaults_used.append(f"dst_mac={dst_mac}")
        if not kwargs.get('src_ip'):
            defaults_used.append(f"src_ip={src_ip}")
        if not kwargs.get('dst_ip'):
            defaults_used.append(f"dst_ip={dst_ip}")
        if kwargs.get('icmp_type') is None:
            defaults_used.append(f"icmp_type={icmp_type} (echo request)")
        if kwargs.get('icmp_code') is None:
            defaults_used.append(f"icmp_code={icmp_code}")
        if kwargs.get('identifier') is None:
            defaults_used.append(f"identifier={identifier}")
        if kwargs.get('sequence') is None:
            defaults_used.append(f"sequence={sequence}")
        
        if defaults_used:
            print("[i] Using default values:")
            for default in defaults_used:
                print(f"    • {default}")
        
        # Convert data from hex string to bytes if provided
        data = b''
        if data_str:
            try:
                data = bytes.fromhex(data_str.replace(' ', '').replace(':', ''))
            except ValueError as e:
                print(f"[!x!] Invalid hex data: {e}")
                sys.exit(1)
        
        # Create ICMP packet
        icmp_packet = create_icmp_packet(icmp_type, icmp_code, identifier, sequence, data)
        
        # Create IPv4 header
        ip_header = create_ipv4_header(src_ip, dst_ip, 1, len(icmp_packet))  # Protocol 1 = ICMP
        
        # Create Ethernet header
        eth_header = create_ethernet_header(eth_dst_mac, eth_src_mac, 0x0800)  # 0x0800 = IPv4
        
        # Combine all
        full_packet = eth_header + ip_header + icmp_packet
        
        print(f"[i] Sending ICMP packet (type={icmp_type}, code={icmp_code}) on interface {interface}")
        send_raw_bytes(interface, full_packet, kwargs.get('verbose', False))
    
    elif tool == "send_udp":
        # Send UDP packet
        interface = kwargs.get('interface')
        src_mac = kwargs.get('src_mac') or "00:00:00:00:00:00"
        dst_mac = kwargs.get('dst_mac') or "ff:ff:ff:ff:ff:ff"
        src_ip = kwargs.get('src_ip') or "192.168.1.1"
        dst_ip = kwargs.get('dst_ip') or "192.168.1.2"
        src_port = kwargs.get('src_port') if kwargs.get('src_port') is not None else 12345
        dst_port = kwargs.get('dst_port') if kwargs.get('dst_port') is not None else 53
        data_str = kwargs.get('data') or ''
        
        if not interface:
            print("[!x!] Interface must be specified with --interface")
            print_available_interfaces()
            print("[i] Usage: hdlforge tool --network send_udp --interface <interface> [options]")
            sys.exit(1)
        
        # Get interface MAC address if eth_src_mac not specified
        eth_src_mac = kwargs.get('eth_src_mac')
        if not eth_src_mac:
            interface_mac = get_interface_mac(interface) if interface else None
            if interface_mac:
                eth_src_mac = interface_mac
            else:
                eth_src_mac = src_mac  # Fallback to src_mac if interface MAC not found
        
        # Ethernet destination MAC
        eth_dst_mac = kwargs.get('eth_dst_mac') or dst_mac
        
        # Show defaults if using defaults
        defaults_used = []
        if not kwargs.get('eth_src_mac'):
            defaults_used.append(f"eth_src_mac={eth_src_mac} (from interface)")
        if not kwargs.get('eth_dst_mac'):
            defaults_used.append(f"eth_dst_mac={eth_dst_mac}")
        if not kwargs.get('src_mac'):
            defaults_used.append(f"src_mac={src_mac}")
        if not kwargs.get('dst_mac'):
            defaults_used.append(f"dst_mac={dst_mac}")
        if not kwargs.get('src_ip'):
            defaults_used.append(f"src_ip={src_ip}")
        if not kwargs.get('dst_ip'):
            defaults_used.append(f"dst_ip={dst_ip}")
        if kwargs.get('src_port') is None:
            defaults_used.append(f"src_port={src_port}")
        if kwargs.get('dst_port') is None:
            defaults_used.append(f"dst_port={dst_port} (DNS)")
        
        if defaults_used:
            print("[i] Using default values:")
            for default in defaults_used:
                print(f"    • {default}")
        
        # Convert data from hex string to bytes if provided
        data = b''
        if data_str:
            try:
                data = bytes.fromhex(data_str.replace(' ', '').replace(':', ''))
            except ValueError as e:
                print(f"[!x!] Invalid hex data: {e}")
                sys.exit(1)
        
        # Create UDP packet
        udp_packet = create_udp_packet(src_port, dst_port, data)
        
        # Create IPv4 header
        ip_header = create_ipv4_header(src_ip, dst_ip, 17, len(udp_packet))  # Protocol 17 = UDP
        
        # Create Ethernet header
        eth_header = create_ethernet_header(eth_dst_mac, eth_src_mac, 0x0800)  # 0x0800 = IPv4
        
        # Combine all
        full_packet = eth_header + ip_header + udp_packet
        
        print(f"[i] Sending UDP packet (src_port={src_port}, dst_port={dst_port}) on interface {interface}")
        send_raw_bytes(interface, full_packet, kwargs.get('verbose', False))
    
    else:
        print(f"[!x!] Unknown tool: {tool}")
        print("[i] Available tools: send_raw, send_arp, send_icmp, send_udp")
        sys.exit(1)

