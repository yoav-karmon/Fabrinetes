#!/bin/bash
# Export package lists from a running container

CONTAINER_NAME="$1"
OUTPUT_DIR="containers/exported"

if [[ -z "$CONTAINER_NAME" ]]; then
    echo "Usage: $0 <container-name>"
    echo "Example: $0 fabrinetes-dev-testing-20251008-154737"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Exporting packages from container: $CONTAINER_NAME"

# Export all packages
echo "Exporting all packages..."
docker exec "$CONTAINER_NAME" dpkg-query -W -f='${Package}\n' | sort > "$OUTPUT_DIR/all-packages.txt"

# Export manually installed packages
echo "Exporting manually installed packages..."
docker exec "$CONTAINER_NAME" apt-mark showmanual | sort > "$OUTPUT_DIR/manual-packages.txt"

# Export packages with versions
echo "Exporting packages with versions..."
docker exec "$CONTAINER_NAME" dpkg-query -W -f='${Package}=${Version}\n' | sort > "$OUTPUT_DIR/packages-with-versions.txt"

# Export apt packages
echo "Exporting apt packages..."
docker exec "$CONTAINER_NAME" apt list --installed | grep -v "WARNING" | cut -d/ -f1 | sort > "$OUTPUT_DIR/apt-packages.txt"

# Export Python packages
echo "Exporting Python packages..."
docker exec "$CONTAINER_NAME" pip3 list --format=freeze > "$OUTPUT_DIR/python-packages.txt"

echo "Package lists exported to $OUTPUT_DIR/"
echo "Files created:"
ls -la "$OUTPUT_DIR/"
