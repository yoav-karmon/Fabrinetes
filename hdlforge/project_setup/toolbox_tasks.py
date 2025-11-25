#!/usr/bin/env python3
"""
Toolbox task handlers for HDLForge
Network utilities and raw packet sending
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
import struct
import socket
import argparse
import subprocess


def list_network_interfaces() -> List[str]:
    """
    List available network interfaces
    
    Returns:
        List of interface names
    """
    interfaces = []
    try:
        # Try using netifaces if available
        try:
            import netifaces
            interfaces = netifaces.interfaces()
        except ImportError:
            # Fallback: read from /proc/net/dev (Linux)
            if os.path.exists('/proc/net/dev'):
                with open('/proc/net/dev', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if ':' in line:
                            iface = line.split(':')[0].strip()
                            # Skip loopback and exclude common virtual interfaces
                            if iface != 'lo' and not iface.startswith('docker') and not iface.startswith('veth'):
                                interfaces.append(iface)
            # Alternative: use ip command if available
            elif subprocess.run(['which', 'ip'], capture_output=True).returncode == 0:
                result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if ': ' in line and 'state' not in line.lower():
                        parts = line.split(':')
                        if len(parts) >= 2:
                            iface = parts[1].strip().split()[0]
                            if iface != 'lo':
                                interfaces.append(iface)
    except Exception:
        pass
    
    return sorted(set(interfaces))


def print_available_interfaces():
    """Print available network interfaces"""
    interfaces = list_network_interfaces()
    if interfaces:
        print("[i] Available network interfaces:")
        for iface in interfaces:
            print(f"    • {iface}")
    else:
        print("[!] No network interfaces found")
    print()


def send_raw_bytes(interface: str, data: bytes, verbose: bool = False):
    """
    Send raw bytes to a network interface
    
    Args:
        interface: Network interface name (e.g., 'enp175s0f0np0')
        data: Raw bytes to send
        verbose: Enable verbose output
    """
    try:
        # Create raw socket (AF_PACKET for Linux, SOCK_RAW for raw packets)
        # ETH_P_ALL = 0x0003 (capture all protocols)
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        sock.bind((interface, 0))
        
        if verbose:
            print(f"[i] Sending {len(data)} bytes to interface {interface}")
            print(f"[i] Data (hex): {data.hex()}")
        
        # Send the raw bytes
        bytes_sent = sock.send(data)
        sock.close()
        
        if verbose:
            print(f"[+] Sent {bytes_sent} bytes successfully")
        
        return bytes_sent
    except PermissionError:
        print("[!x!] Permission denied. Raw socket operations require root privileges.")
        print("[i] Please run with sudo or as root")
        sys.exit(1)
    except OSError as e:
        print(f"[!x!] Error accessing interface {interface}: {e}")
        sys.exit(1)


def create_ethernet_header(dst_mac: str, src_mac: str, eth_type: int = 0x0800) -> bytes:
    """
    Create Ethernet frame header
    
    Args:
        dst_mac: Destination MAC address (format: "aa:bb:cc:dd:ee:ff")
        src_mac: Source MAC address (format: "aa:bb:cc:dd:ee:ff")
        eth_type: Ethernet type (0x0800 for IPv4, 0x0806 for ARP)
    
    Returns:
        Ethernet header as bytes (14 bytes)
    """
    def mac_to_bytes(mac_str: str) -> bytes:
        """Convert MAC address string to bytes"""
        return bytes.fromhex(mac_str.replace(':', '').replace('-', ''))
    
    dst = mac_to_bytes(dst_mac)
    src = mac_to_bytes(src_mac)
    eth_type_bytes = struct.pack('!H', eth_type)
    
    return dst + src + eth_type_bytes


def create_arp_packet(
    op: int = 1,  # 1=request, 2=reply
    src_mac: str = "00:00:00:00:00:00",
    src_ip: str = "192.168.1.1",
    dst_mac: str = "00:00:00:00:00:00",
    dst_ip: str = "192.168.1.2"
) -> bytes:
    """
    Create ARP packet
    
    Args:
        op: ARP operation (1=request, 2=reply)
        src_mac: Source MAC address
        src_ip: Source IP address
        dst_mac: Destination MAC address
        dst_ip: Destination IP address
    
    Returns:
        ARP packet as bytes
    """
    def mac_to_bytes(mac_str: str) -> bytes:
        return bytes.fromhex(mac_str.replace(':', '').replace('-', ''))
    
    def ip_to_bytes(ip_str: str) -> bytes:
        return socket.inet_aton(ip_str)
    
    # ARP header structure
    hardware_type = struct.pack('!H', 1)  # Ethernet
    protocol_type = struct.pack('!H', 0x0800)  # IPv4
    hardware_size = struct.pack('B', 6)  # MAC address length
    protocol_size = struct.pack('B', 4)  # IP address length
    opcode = struct.pack('!H', op)
    
    src_mac_bytes = mac_to_bytes(src_mac)
    src_ip_bytes = ip_to_bytes(src_ip)
    dst_mac_bytes = mac_to_bytes(dst_mac)
    dst_ip_bytes = ip_to_bytes(dst_ip)
    
    arp_packet = (
        hardware_type + protocol_type + hardware_size + protocol_size +
        opcode + src_mac_bytes + src_ip_bytes + dst_mac_bytes + dst_ip_bytes
    )
    
    return arp_packet


def create_icmp_packet(
    icmp_type: int = 8,  # 8=echo request, 0=echo reply
    icmp_code: int = 0,
    identifier: int = 0,
    sequence: int = 0,
    data: bytes = b''
) -> bytes:
    """
    Create ICMP packet
    
    Args:
        icmp_type: ICMP type (8=echo request, 0=echo reply)
        icmp_code: ICMP code
        identifier: ICMP identifier
        sequence: ICMP sequence number
        data: ICMP data payload
    
    Returns:
        ICMP packet as bytes
    """
    # ICMP header
    icmp_type_byte = struct.pack('B', icmp_type)
    icmp_code_byte = struct.pack('B', icmp_code)
    checksum = struct.pack('!H', 0)  # Will be calculated
    identifier_bytes = struct.pack('!H', identifier)
    sequence_bytes = struct.pack('!H', sequence)
    
    icmp_header = icmp_type_byte + icmp_code_byte + checksum + identifier_bytes + sequence_bytes
    icmp_packet = icmp_header + data
    
    # Calculate checksum
    checksum_value = calculate_checksum(icmp_packet)
    icmp_packet = icmp_packet[:2] + struct.pack('!H', checksum_value) + icmp_packet[4:]
    
    return icmp_packet


def create_udp_packet(
    src_port: int,
    dst_port: int,
    data: bytes = b''
) -> bytes:
    """
    Create UDP packet
    
    Args:
        src_port: Source port
        dst_port: Destination port
        data: UDP payload
    
    Returns:
        UDP packet as bytes
    """
    # UDP header
    src_port_bytes = struct.pack('!H', src_port)
    dst_port_bytes = struct.pack('!H', dst_port)
    length = struct.pack('!H', 8 + len(data))  # UDP header (8) + data
    checksum = struct.pack('!H', 0)  # Optional for UDP
    
    udp_packet = src_port_bytes + dst_port_bytes + length + checksum + data
    return udp_packet


def create_ipv4_header(
    src_ip: str,
    dst_ip: str,
    protocol: int = 1,  # 1=ICMP, 17=UDP
    payload_length: int = 0
) -> bytes:
    """
    Create IPv4 header
    
    Args:
        src_ip: Source IP address
        dst_ip: Destination IP address
        protocol: IP protocol (1=ICMP, 17=UDP)
        payload_length: Length of payload in bytes
    
    Returns:
        IPv4 header as bytes (20 bytes)
    """
    version_ihl = 0x45  # Version 4, IHL 5 (20 bytes)
    tos = 0
    total_length = 20 + payload_length
    identification = 0
    flags_fragment = 0
    ttl = 64
    protocol_byte = protocol
    
    src_ip_bytes = socket.inet_aton(src_ip)
    dst_ip_bytes = socket.inet_aton(dst_ip)
    
    # Create header without checksum
    ip_header = struct.pack('!BBHHHBB', version_ihl, tos, total_length, identification, flags_fragment, ttl, protocol_byte)
    ip_header += struct.pack('!H', 0)  # Checksum placeholder
    ip_header += src_ip_bytes + dst_ip_bytes
    
    # Calculate checksum
    checksum_value = calculate_checksum(ip_header)
    ip_header = ip_header[:10] + struct.pack('!H', checksum_value) + ip_header[12:]
    
    return ip_header


def calculate_checksum(data: bytes) -> int:
    """
    Calculate Internet checksum for IP/ICMP headers
    
    Args:
        data: Data to calculate checksum for
    
    Returns:
        Checksum value
    """
    checksum = 0
    # Make sure data length is even
    if len(data) % 2:
        data += b'\x00'
    
    # Sum all 16-bit words
    for i in range(0, len(data), 2):
        word = struct.unpack('!H', data[i:i+2])[0]
        checksum += word
    
    # Add carry bits
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    # One's complement
    return ~checksum & 0xFFFF


def toolbox(c, tool: Optional[str] = None, **kwargs):
    """
    Toolbox command handler
    
    Args:
        c: Invoke context
        tool: Tool name to execute
        **kwargs: Tool-specific arguments
    """
    if tool == "send_raw" or tool is None:
        # Send raw bytes
        interface = kwargs.get('interface')
        data_hex = kwargs.get('data')
        
        if not interface:
            print("[!x!] Interface must be specified with --interface")
            print_available_interfaces()
            print("[i] Usage: hdlforge toolbox send_raw --interface <interface> --data <hex_string>")
            sys.exit(1)
        
        if not data_hex:
            print("[!x!] Data must be specified with --data")
            print("[i] Usage: hdlforge toolbox send_raw --interface <interface> --data <hex_string>")
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
        
        if not interface:
            print("[!x!] Interface must be specified with --interface")
            print_available_interfaces()
            print("[i] Usage: hdlforge toolbox send_arp --interface <interface> [options]")
            sys.exit(1)
        
        # Show defaults if verbose or if using defaults
        defaults_used = []
        if kwargs.get('arp_op') is None:
            defaults_used.append(f"arp_op=1 (request)")
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
        eth_header = create_ethernet_header(dst_mac, src_mac, 0x0806)  # 0x0806 = ARP
        
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
            print("[i] Usage: hdlforge toolbox send_icmp --interface <interface> [options]")
            sys.exit(1)
        
        # Show defaults if using defaults
        defaults_used = []
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
        eth_header = create_ethernet_header(dst_mac, src_mac, 0x0800)  # 0x0800 = IPv4
        
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
            print("[i] Usage: hdlforge toolbox send_udp --interface <interface> [options]")
            sys.exit(1)
        
        # Show defaults if using defaults
        defaults_used = []
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
        eth_header = create_ethernet_header(dst_mac, src_mac, 0x0800)  # 0x0800 = IPv4
        
        # Combine all
        full_packet = eth_header + ip_header + udp_packet
        
        print(f"[i] Sending UDP packet (src_port={src_port}, dst_port={dst_port}) on interface {interface}")
        send_raw_bytes(interface, full_packet, kwargs.get('verbose', False))
    
    else:
        print(f"[!x!] Unknown tool: {tool}")
        print("[i] Available tools: send_raw, send_arp, send_icmp, send_udp")
        sys.exit(1)

