#!/bin/bash
# ============================================================================
# Hardware Server Chip DNA Reader
# ============================================================================
# Description:
#   Connects to Vivado hardware server and reads chip DNA value
#
# Usage:
#   ./read_dna.sh [server_ip]
#
# Arguments:
#   server_ip (optional): Hardware server IP address (default: 10.1.130.74)
#
# ============================================================================

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set default hardware server IP
HW_SERVER_IP="${1:-10.1.130.74}"

# Run Vivado in batch mode with quiet mode (suppress command echoing)
vivado -mode batch -notrace -source "${SCRIPT_DIR}/tcl/connect_and_read_dna.tcl" -tclargs "${HW_SERVER_IP}"


