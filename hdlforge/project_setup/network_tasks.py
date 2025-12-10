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
import time

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

# Import test helper functions for config protocol
# Add path to test helpers
# Path: network_tasks.py -> project_setup -> hdlforge -> Fabrinetes -> repo_root (4 levels)
repo_root = Path(__file__).parent.parent.parent.parent
sources_path = repo_root / "fpga" / "fpga_projects" / "phy10gbaser" / "sources" / "PY"
test_helpers_path = sources_path / "TEST_HELPERS"
test_utils_path = sources_path / "TEST_UTILS"
if test_helpers_path.exists() and test_utils_path.exists():
    sys.path.insert(0, str(sources_path))
    sys.path.insert(0, str(test_helpers_path))
    sys.path.insert(0, str(test_utils_path))
    try:
        from config_block_helpers import build_config_payload, CFG_CMD_READ, CFG_CMD_WRITE
        from tshark_parser import parse_packet_to_json
        import scapy.all as scapy
        TEST_HELPERS_AVAILABLE = True
    except ImportError as e:
        print(f"[!] Warning: Could not import test helpers: {e}", file=sys.stderr)
        print(f"[!]   Looking in: {test_helpers_path}", file=sys.stderr)
        TEST_HELPERS_AVAILABLE = False
else:
    if not test_helpers_path.exists():
        print(f"[!] Warning: Test helpers path not found: {test_helpers_path}", file=sys.stderr)
    if not test_utils_path.exists():
        print(f"[!] Warning: Test utils path not found: {test_utils_path}", file=sys.stderr)
    TEST_HELPERS_AVAILABLE = False


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
    
    elif tool == "config_reg":
        # Config register read/write using regular UDP sockets
        if not TEST_HELPERS_AVAILABLE:
            print("[!x!] Test helpers not available. Cannot use config_reg command.")
            print("[i] Make sure the test helper modules are accessible.")
            sys.exit(1)
        
        fpga_ip = kwargs.get('fpga_ip')
        server_ip = kwargs.get('server_ip') or "192.168.1.1"
        server_port = kwargs.get('server_port') if kwargs.get('server_port') is not None else 1234
        fpga_port = kwargs.get('fpga_port') if kwargs.get('fpga_port') is not None else 5678
        # Get the subcommand (write, read, write-all, read-all) from 'subcmd' parameter
        cmd = kwargs.get('subcmd')
        reg = kwargs.get('reg')
        value = kwargs.get('value')
        
        if not fpga_ip:
            print("[!x!] FPGA IP address must be specified with --fpga-ip")
            print("[i] Usage: hdlforge tool --network config_reg --fpga-ip <ip> --cmd <command> [options]")
            sys.exit(1)
        
        if not cmd:
            print("[!x!] Action must be specified with --action (write, read, write-all, read-all)")
            print("[i] Usage: hdlforge tool --network config_reg --fpga-ip <ip> --action <command> [options]")
            sys.exit(1)
        
        def send_config_udp(server_ip: str, fpga_ip: str, server_port: int, fpga_port: int, payload_hex: str) -> socket.socket:
            """Send UDP packet using regular UDP socket. Returns socket for response receiving."""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(2.0)  # 2 second timeout for response
                try:
                    sock.bind((server_ip, server_port))
                except OSError as e:
                    print(f"[!x!] Error binding to {server_ip}:{server_port}: {e}")
                    print("  Try using a different source IP or port.")
                    sock.close()
                    sys.exit(1)
                payload_bytes = bytes.fromhex(payload_hex)
                sock.sendto(payload_bytes, (fpga_ip, fpga_port))
                print(f"[v] UDP packet sent ({len(payload_bytes)} bytes payload)")
                print(f"    From {server_ip}:{server_port} to {fpga_ip}:{fpga_port}")
                return sock
            except Exception as e:
                print(f"[!x!] Error sending UDP packet: {e}")
                if 'sock' in locals():
                    sock.close()
                sys.exit(1)
        
        def receive_and_parse_response(sock: socket.socket, server_ip: str, server_port: int, expected_cmd_seq: int) -> None:
            """Receive UDP response and parse using dissector."""
            try:
                data, addr = sock.recvfrom(4096)
                sock.close()
                print(f"[v] Response received from {addr[0]}:{addr[1]} ({len(data)} bytes)")
                
                # Convert to Scapy packet (add Ethernet header since we only have UDP payload)
                # We need to reconstruct the full packet for tshark
                # For now, create a minimal Ethernet frame
                eth_header = b'\x00' * 14  # Placeholder Ethernet header
                ip_header_len = 20
                udp_header_len = 8
                # Create minimal IP header
                ip_header = struct.pack('!BBHHHBBH4s4s',
                    0x45, 0, len(data) + udp_header_len + ip_header_len, 0, 0, 64, 17, 0,
                    socket.inet_aton(addr[0]), socket.inet_aton(server_ip))
                # Create UDP header
                udp_header = struct.pack('!HHHH',
                    addr[1], server_port, len(data) + udp_header_len, 0)
                full_packet = eth_header + ip_header + udp_header + data
                
                # Parse with tshark
                try:
                    json_data = parse_packet_to_json(full_packet)
                    if json_data and len(json_data) > 0:
                        layers = json_data[0].get('_source', {}).get('layers', {})
                        fpga_config = layers.get('fpga_config', {})
                        if fpga_config:
                            cmd_seq = int(fpga_config.get('fpga_config.cmd_seq', '0'), 0)
                            cmd_raw = int(fpga_config.get('fpga_config.cmd', '0'), 0)
                            cmd_name = "UNKNOWN"
                            if cmd_raw == 0x00000001:
                                cmd_name = "READ"
                            elif cmd_raw == 0x00000002:
                                cmd_name = "WRITE"
                            core = int(fpga_config.get('fpga_config.core', '0'), 0)
                            addr_val = int(fpga_config.get('fpga_config.addr', '0'), 0)
                            len_val = int(fpga_config.get('fpga_config.len', '0'), 0)
                            
                            print(f"[i] Parsed Response:")
                            print(f"    Command Sequence: {cmd_seq}")
                            print(f"    Command: {cmd_name} (0x{cmd_raw:08X})")
                            print(f"    Core Index: {core}")
                            print(f"    Address: 0x{addr_val:08X} words")
                            print(f"    Data Length: {len_val} words")
                            
                            # Extract data words from UDP payload (skip 20-byte header)
                            if len(data) > 20:
                                data_bytes = data[20:]
                                data_words = []
                                for i in range(0, len(data_bytes), 4):
                                    if i + 4 <= len(data_bytes):
                                        word = int.from_bytes(data_bytes[i:i+4], 'big')
                                        data_words.append(word)
                                if data_words:
                                    print(f"    Data: {[f'0x{w:08X}' for w in data_words]}")
                        else:
                            print("[!] Response received but not recognized as FPGA Config protocol")
                    else:
                        print("[!] Could not parse response with tshark")
                except Exception as e:
                    print(f"[!] Error parsing response: {e}")
                    print(f"    Raw response (hex): {data.hex()}")
            except socket.timeout:
                sock.close()
                print("[!] Timeout waiting for response (2 seconds)")
            except Exception as e:
                sock.close()
                print(f"[!x!] Error receiving response: {e}")
        
        if cmd == 'write':
            if reg is None:
                print("[!x!] Register address must be specified with --reg for write command")
                sys.exit(1)
            if value is None:
                print("[!x!] Value must be specified with --value for write command")
                sys.exit(1)
            if reg < 0 or reg > 15:
                print(f"[!x!] Register address must be 0-15, got {reg}")
                sys.exit(1)
            
            # Parse value (hex or decimal)
            try:
                if isinstance(value, str):
                    value_int = int(value, 0)  # Supports 0x prefix
                else:
                    value_int = int(value)
            except ValueError:
                print(f"[!x!] Invalid value: {value}")
                sys.exit(1)
            
            print(f"[i] Writing register {reg} with value 0x{value_int:08X}")
            payload_hex = build_config_payload(
                cmd_seq=1,
                cfg_cmd=CFG_CMD_WRITE,
                cfg_core=0,
                cfg_addr=reg,  # Address in words
                cfg_len=1,  # 1 word
                data_words=[value_int]
            )
            sock = send_config_udp(server_ip, fpga_ip, server_port, fpga_port, payload_hex)
            sock.close()
        
        elif cmd == 'read':
            if reg is None:
                print("[!x!] Register address must be specified with --reg for read command")
                sys.exit(1)
            if reg < 0 or reg > 15:
                print(f"[!x!] Register address must be 0-15, got {reg}")
                sys.exit(1)
            
            print(f"[i] Reading register {reg}...")
            cmd_seq = 1
            payload_hex = build_config_payload(
                cmd_seq=cmd_seq,
                cfg_cmd=CFG_CMD_READ,
                cfg_core=0,
                cfg_addr=reg,  # Address in words
                cfg_len=1,  # Read 1 word
                data_words=[]
            )
            sock = send_config_udp(server_ip, fpga_ip, server_port, fpga_port, payload_hex)
            receive_and_parse_response(sock, server_ip, server_port, cmd_seq)
        
        elif cmd == 'write-all':
            print("[i] Writing all registers 0-15 with sequential values...")
            for r in range(16):
                value_int = 0x10000000 + r
                payload_hex = build_config_payload(
                    cmd_seq=r + 1,
                    cfg_cmd=CFG_CMD_WRITE,
                    cfg_core=0,
                    cfg_addr=r,  # Address in words
                    cfg_len=1,  # 1 word
                    data_words=[value_int]
                )
                sock = send_config_udp(server_ip, fpga_ip, server_port, fpga_port, payload_hex)
                sock.close()
                time.sleep(0.05)
        
        elif cmd == 'read-all':
            print("[i] Reading all registers 0-15...")
            for r in range(16):
                cmd_seq = r + 1
                payload_hex = build_config_payload(
                    cmd_seq=cmd_seq,
                    cfg_cmd=CFG_CMD_READ,
                    cfg_core=0,
                    cfg_addr=r,  # Address in words
                    cfg_len=1,  # Read 1 word
                    data_words=[]
                )
                sock = send_config_udp(server_ip, fpga_ip, server_port, fpga_port, payload_hex)
                receive_and_parse_response(sock, server_ip, server_port, cmd_seq)
                time.sleep(0.05)
        
        else:
            print(f"[!x!] Unknown command: {cmd}")
            print("[i] Available commands: write, read, write-all, read-all")
            sys.exit(1)
    
    else:
        print(f"[!x!] Unknown tool: {tool}")
        print("[i] Available tools: send_raw, send_arp, send_icmp, send_udp, config_reg")
        sys.exit(1)

