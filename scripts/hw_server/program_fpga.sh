#!/bin/bash
# ============================================================================
# Hardware Server FPGA Programmer
# ============================================================================
# Description:
#   Connects to Vivado hardware server and programs FPGA with bitstream
#
# Usage:
#   ./program_fpga.sh [server_ip] [bitstream_path] [probes_path]
#
# Arguments:
#   server_ip (optional): Hardware server IP address (default: 10.1.130.74)
#   bitstream_path (required): Path to .bit or .vit file
#   probes_path (required): Path to .ltx file
#
# ============================================================================

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set default hardware server IP
HW_SERVER_IP="${1:-10.1.130.74}"

if [ -z "$2" ] || [ -z "$3" ]; then
    echo "ERROR: bitstream_path and probes_path are required"
    echo "Usage: ./program_fpga.sh [server_ip] [bitstream_path] [probes_path]"
    exit 1
fi

BITSTREAM_PATH="$2"
PROBES_PATH="$3"

# Expand tilde and resolve paths
BITSTREAM_PATH="${BITSTREAM_PATH/#\~/$HOME}"
PROBES_PATH="${PROBES_PATH/#\~/$HOME}"

# Convert to absolute paths
BITSTREAM_PATH="$(cd "$(dirname "$BITSTREAM_PATH")" && pwd)/$(basename "$BITSTREAM_PATH")"
PROBES_PATH="$(cd "$(dirname "$PROBES_PATH")" && pwd)/$(basename "$PROBES_PATH")"

# Verify files exist
if [ ! -f "$BITSTREAM_PATH" ]; then
    echo "ERROR: Bitstream file not found: $BITSTREAM_PATH"
    exit 1
fi

if [ ! -f "$PROBES_PATH" ]; then
    echo "ERROR: Probes file not found: $PROBES_PATH"
    exit 1
fi

# Run Vivado in batch mode with quiet mode (suppress command echoing)
vivado -mode batch -notrace -source "${SCRIPT_DIR}/tcl/connect_and_program_fpga.tcl" -tclargs "${HW_SERVER_IP}" "${BITSTREAM_PATH}" "${PROBES_PATH}"

