#!/bin/bash
# Test script for HDLForge toolbox functionality
# Tests raw packet sending with tcpdump capture

# Don't exit on error - we want to test all commands even if some fail
set +e

INTERFACE="${1:-enp175s0f0np0}"
CAPTURE_FILE="/tmp/toolbox_test_$$.pcap"
HDLFORGE_DIR="$(dirname "$0")"

echo "=========================================="
echo "HDLForge Toolbox Test Script"
echo "=========================================="
echo "Interface: $INTERFACE"
echo "Capture file: $CAPTURE_FILE"
echo ""

# Note: This script requires root privileges for raw socket operations
# The actual commands will fail with permission errors if not run as root

# Check if interface exists (optional - command will fail if interface doesn't exist)
if command -v ip > /dev/null 2>&1; then
    if ! ip link show "$INTERFACE" > /dev/null 2>&1; then
        echo "[!] Warning: Interface $INTERFACE may not exist (continuing anyway)"
    fi
else
    echo "[i] Note: 'ip' command not available, skipping interface check"
fi

# Cleanup function
cleanup() {
    echo ""
    echo "[i] Cleaning up..."
    pkill -f "tcpdump.*$INTERFACE" 2>/dev/null || true
    rm -f "$CAPTURE_FILE"
}
trap cleanup EXIT

# Test 1: Send raw bytes
echo "[TEST 1] Testing send_raw..."
timeout 2 tcpdump -i "$INTERFACE" -w "$CAPTURE_FILE" -c 1 > /dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 0.3
python3 "$HDLFORGE_DIR/tasks.py" toolbox send_raw --interface "$INTERFACE" --data "deadbeef" --verbose 2>&1 | grep -E "\[i\]|\[!x!\]|\[+\]|Error" || true
sleep 0.5
kill $TCPDUMP_PID 2>/dev/null || true
if [ -f "$CAPTURE_FILE" ] && [ -s "$CAPTURE_FILE" ]; then
    echo "[+] Raw packet captured"
    tcpdump -r "$CAPTURE_FILE" -n 2>&1 | head -3
else
    echo "[!] No packet captured (expected - raw bytes may need Ethernet header)"
fi
rm -f "$CAPTURE_FILE"
echo ""

# Test 2: Send ARP packet
echo "[TEST 2] Testing send_arp..."
timeout 2 tcpdump -i "$INTERFACE" -w "$CAPTURE_FILE" -c 1 > /dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 0.3
python3 "$HDLFORGE_DIR/tasks.py" toolbox send_arp --interface "$INTERFACE" --src_ip 192.168.1.10 --dst_ip 192.168.1.1 --verbose 2>&1 | grep -E "\[i\]|\[!x!\]|\[+\]|Error" || true
sleep 0.5
kill $TCPDUMP_PID 2>/dev/null || true
if [ -f "$CAPTURE_FILE" ] && [ -s "$CAPTURE_FILE" ]; then
    echo "[+] ARP packet captured:"
    tcpdump -r "$CAPTURE_FILE" -n -X 2>&1 | head -5
    if tcpdump -r "$CAPTURE_FILE" -n 2>&1 | grep -q "ARP"; then
        echo "[+] ARP packet verified"
    else
        echo "[!] ARP packet not found in capture"
    fi
else
    echo "[!x!] No packet captured"
fi
rm -f "$CAPTURE_FILE"
echo ""

# Test 3: Send ICMP packet
echo "[TEST 3] Testing send_icmp..."
timeout 2 tcpdump -i "$INTERFACE" -w "$CAPTURE_FILE" -c 1 > /dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 0.3
python3 "$HDLFORGE_DIR/tasks.py" toolbox send_icmp --interface "$INTERFACE" --src_ip 192.168.1.10 --dst_ip 192.168.1.1 --verbose 2>&1 | grep -E "\[i\]|\[!x!\]|\[+\]|Error" || true
sleep 0.5
kill $TCPDUMP_PID 2>/dev/null || true
if [ -f "$CAPTURE_FILE" ] && [ -s "$CAPTURE_FILE" ]; then
    echo "[+] ICMP packet captured:"
    tcpdump -r "$CAPTURE_FILE" -n -X 2>&1 | head -5
    if tcpdump -r "$CAPTURE_FILE" -n 2>&1 | grep -q "ICMP"; then
        echo "[+] ICMP packet verified"
    else
        echo "[!] ICMP packet not found in capture"
    fi
else
    echo "[!x!] No packet captured"
fi
rm -f "$CAPTURE_FILE"
echo ""

# Test 4: Send UDP packet
echo "[TEST 4] Testing send_udp..."
timeout 2 tcpdump -i "$INTERFACE" -w "$CAPTURE_FILE" -c 1 > /dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 0.3
python3 "$HDLFORGE_DIR/tasks.py" toolbox send_udp --interface "$INTERFACE" --src_ip 192.168.1.10 --dst_ip 192.168.1.1 --dst_port 53 --verbose 2>&1 | grep -E "\[i\]|\[!x!\]|\[+\]|Error" || true
sleep 0.5
kill $TCPDUMP_PID 2>/dev/null || true
if [ -f "$CAPTURE_FILE" ] && [ -s "$CAPTURE_FILE" ]; then
    echo "[+] UDP packet captured:"
    tcpdump -r "$CAPTURE_FILE" -n -X 2>&1 | head -5
    if tcpdump -r "$CAPTURE_FILE" -n 2>&1 | grep -q "UDP"; then
        echo "[+] UDP packet verified"
    else
        echo "[!] UDP packet not found in capture"
    fi
else
    echo "[!x!] No packet captured"
fi
rm -f "$CAPTURE_FILE"
echo ""

echo "=========================================="
echo "All tests completed"
echo "=========================================="

