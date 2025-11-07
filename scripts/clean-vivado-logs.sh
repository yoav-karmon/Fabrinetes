#!/bin/bash

# Clean Vivado Log Files Script
# This script removes common Vivado log and temporary files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=false
VERBOSE=false
TARGET_DIR="."

# Function to print usage
usage() {
    echo "Usage: $0 [OPTIONS] [DIRECTORY]"
    echo ""
    echo "Clean Vivado log and temporary files"
    echo ""
    echo "Options:"
    echo "  -d, --dry-run       Show what would be deleted without actually deleting"
    echo "  -v, --verbose       Show detailed output"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Arguments:"
    echo "  DIRECTORY           Target directory to clean (default: current directory)"
    echo ""
    echo "Examples:"
    echo "  $0                          # Clean current directory"
    echo "  $0 /path/to/project         # Clean specific directory"
    echo "  $0 -d                       # Dry run in current directory"
    echo "  $0 -v /path/to/project      # Verbose clean of specific directory"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo -e "${RED}Error: Unknown option $1${NC}" >&2
            usage
            exit 1
            ;;
        *)
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

# Validate target directory
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}Error: Directory '$TARGET_DIR' does not exist${NC}" >&2
    exit 1
fi

# Convert to absolute path
TARGET_DIR=$(cd "$TARGET_DIR" && pwd)

echo "Cleaning Vivado log files in: $TARGET_DIR"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY RUN] No files will be deleted${NC}"
fi
echo ""

# Counter for deleted files
DELETED_COUNT=0
DELETED_SIZE=0

# Function to remove files/directories
remove_item() {
    local item="$1"
    local item_type="$2"
    
    if [ -e "$item" ]; then
        local size=0
        if [ -f "$item" ]; then
            size=$(stat -f%z "$item" 2>/dev/null || stat -c%s "$item" 2>/dev/null || echo 0)
        elif [ -d "$item" ]; then
            size=$(du -sb "$item" 2>/dev/null | cut -f1 || echo 0)
        fi
        
        if [ "$VERBOSE" = true ]; then
            if [ "$DRY_RUN" = true ]; then
                echo -e "${YELLOW}[WOULD DELETE]${NC} $item_type: $item ($(numfmt --to=iec-i --suffix=B $size 2>/dev/null || echo "${size}B"))"
            else
                echo -e "${GREEN}[DELETING]${NC} $item_type: $item ($(numfmt --to=iec-i --suffix=B $size 2>/dev/null || echo "${size}B"))"
            fi
        fi
        
        if [ "$DRY_RUN" = false ]; then
            if [ -d "$item" ]; then
                rm -rf "$item"
            else
                rm -f "$item"
            fi
        fi
        
        DELETED_COUNT=$((DELETED_COUNT + 1))
        DELETED_SIZE=$((DELETED_SIZE + size))
    fi
}

# Find and remove .jou files (Vivado journal files)
echo "Searching for .jou files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "Journal"
done < <(find "$TARGET_DIR" -type f -name "*.jou" -print0 2>/dev/null || true)

# Find and remove .log files (Vivado log files)
echo "Searching for .log files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "Log"
done < <(find "$TARGET_DIR" -type f -name "*.log" -print0 2>/dev/null || true)

# Find and remove .str files (Vivado strategy files - temporary)
echo "Searching for .str files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "Strategy"
done < <(find "$TARGET_DIR" -type f -name "*.str" -print0 2>/dev/null || true)

# Find and remove .Xil directories (Vivado temporary directories)
echo "Searching for .Xil directories..."
while IFS= read -r -d '' dir; do
    remove_item "$dir" "Xil Directory"
done < <(find "$TARGET_DIR" -type d -name ".Xil" -print0 2>/dev/null || true)

# Find and remove .rpt files (report files - optional, can be regenerated)
echo "Searching for .rpt files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "Report"
done < <(find "$TARGET_DIR" -type f -name "*.rpt" -print0 2>/dev/null || true)

# Find and remove .wdb files (Vivado waveform database - can be large)
echo "Searching for .wdb files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "Waveform Database"
done < <(find "$TARGET_DIR" -type f -name "*.wdb" -print0 2>/dev/null || true)

# Find and remove .wcfg files (Vivado waveform configuration - temporary)
echo "Searching for .wcfg files..."
while IFS= read -r -d '' file; do
    remove_item "$file" "Waveform Config"
done < <(find "$TARGET_DIR" -type f -name "*.wcfg" -print0 2>/dev/null || true)

# Summary
echo ""
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}Dry run complete.${NC}"
    echo "Would delete: $DELETED_COUNT items"
    if [ "$DELETED_SIZE" -gt 0 ]; then
        echo "Total size: $(numfmt --to=iec-i --suffix=B $DELETED_SIZE 2>/dev/null || echo "${DELETED_SIZE}B")"
    fi
else
    echo -e "${GREEN}Clean complete!${NC}"
    echo "Deleted: $DELETED_COUNT items"
    if [ "$DELETED_SIZE" -gt 0 ]; then
        echo "Freed space: $(numfmt --to=iec-i --suffix=B $DELETED_SIZE 2>/dev/null || echo "${DELETED_SIZE}B")"
    fi
fi

