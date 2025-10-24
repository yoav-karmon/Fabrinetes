#!/bin/bash
set -e

# Set up logging to /tmp/entrypoint.log with verbose output
LOG_FILE="/tmp/entrypoint.log"
exec > >(tee -a "$LOG_FILE") 2>&1
set -x  # Enable verbose command output

echo "=========================================="
echo "Entrypoint started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# Logging function for timestamped messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Dynamic User Setup Entrypoint Script
# This script creates a user dynamically at runtime instead of static build-time creation

# Get user info from environment variables or use defaults
USERNAME=${CONTAINER_USER:-$(whoami)}
USER_UID=${CONTAINER_UID:-$(id -u)}
USER_GID=${CONTAINER_GID:-$(id -g)}
HOME_DIR=${CONTAINER_HOME:-/home/$USERNAME}

log "Setting up dynamic user: $USERNAME (UID:$USER_UID, GID:$USER_GID, HOME:$HOME_DIR)"

# Check if CONTAINER_USER is root - if so, switch to root and skip rest of script
if [ "$CONTAINER_USER" = "root" ]; then
    log "CONTAINER_USER is set to root - switching to root and skipping user setup"
    log "Verifying root access: $(whoami) (UID: $(id -u))"
    log "Root mode enabled - executing command as root"
    exec "$@"
fi

# Create user and group dynamically (requires root privileges)
if ! getent group "$USER_GID" > /dev/null; then
    log "Creating group: $USERNAME (GID:$USER_GID)"
    groupadd --gid "$USER_GID" "$USERNAME"
else
    existing_group=$(getent group "$USER_GID" | cut -d: -f1)
    log "Group already exists: $existing_group"
    # Rename the group if it's not the expected name
    if [ "$existing_group" != "$USERNAME" ]; then
        log "Renaming group from $existing_group to $USERNAME"
        groupmod -n "$USERNAME" "$existing_group"
    fi
fi

if ! getent passwd "$USER_UID" > /dev/null; then
    log "Creating user: $USERNAME (UID:$USER_UID, HOME:$HOME_DIR)"
    useradd --uid "$USER_UID" --gid "$USER_GID" --shell /bin/bash --create-home --home-dir "$HOME_DIR" "$USERNAME"
    # Set proper ownership of home directory after creation
    # Only change ownership of files directly in the home directory, not subdirectories
    chown "$USERNAME:$USERNAME" "$HOME_DIR" 2>/dev/null || true
    # Skip read-only files like .Xauthority - only change writable files
    find "$HOME_DIR" -maxdepth 1 -type f -writable -exec chown "$USERNAME:$USERNAME" {} \; 2>/dev/null || true
    # Set up passwordless sudo for the user (requires root privileges)
    log "Setting up passwordless sudo for $USERNAME"
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
    chmod 0440 "/etc/sudoers.d/$USERNAME"
else
    log "User already exists, updating: $USERNAME"
    # Don't try to modify root user if we're running as root
    if [ "$USER_UID" != "0" ]; then
        existing_user=$(getent passwd "$USER_UID" | cut -d: -f1)
        if [ "$existing_user" != "$USERNAME" ]; then
            usermod -l "$USERNAME" "$existing_user"
        fi
        # Only move home directory if it doesn't already exist
        if [ ! -d "$HOME_DIR" ]; then
            usermod -d "$HOME_DIR" -m "$USERNAME"
        else
            usermod -d "$HOME_DIR" "$USERNAME"
        fi
        # Set proper ownership of home directory (for both new and existing)
        # Only change ownership of files directly in the home directory, not subdirectories
        chown "$USERNAME:$USERNAME" "$HOME_DIR" 2>/dev/null || true
        # Skip read-only files like .Xauthority - only change writable files
        find "$HOME_DIR" -maxdepth 1 -type f -writable -exec chown "$USERNAME:$USERNAME" {} \; 2>/dev/null || true
    else
        log "Running as root, skipping user modification"
    fi
fi

# ========================================
# SUDO CONFIGURATION SECTION
# ========================================
echo "=== SUDO CONFIGURATION SECTION ==="
log "Setting up passwordless sudo for user: $USERNAME"

# Method 1: Create sudoers.d file (preferred method)
log "Creating sudoers.d file for $USERNAME"
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
chmod 0440 "/etc/sudoers.d/$USERNAME"
echo "✓ Sudoers.d file created: /etc/sudoers.d/$USERNAME"

# Method 2: Add to sudo group as backup
log "Adding $USERNAME to sudo group"
usermod -aG sudo "$USERNAME" 2>/dev/null || echo "⚠ Warning: Could not add to sudo group"
echo "✓ Added $USERNAME to sudo group"

# Method 3: Add to main sudoers file as additional backup
log "Adding $USERNAME to main sudoers file"
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> "/etc/sudoers"
echo "✓ Added to main sudoers file"

# Verify sudoers file syntax
log "Verifying sudoers file syntax"
if visudo -c -f "/etc/sudoers.d/$USERNAME" 2>/dev/null; then
    echo "✓ Sudoers file syntax verified for $USERNAME"
else
    echo "⚠ Warning: sudoers file syntax check failed for $USERNAME"
fi

# Test sudo access
log "Testing sudo access for $USERNAME"
if sudo -u "$USERNAME" sudo -n whoami 2>/dev/null; then
    echo "✓ Passwordless sudo test PASSED for $USERNAME"
else
    echo "⚠ Warning: Passwordless sudo test FAILED for $USERNAME"
fi

echo "=== END SUDO CONFIGURATION SECTION ==="
echo ""

# Set hostname (requires root privileges)
log "Setting hostname to: Fabrinetes"
echo "Fabrinetes" > /etc/hostname

# Create a custom bash wrapper that automatically switches to the dynamic user
log "Creating custom bash wrapper for automatic user switching"
cat > /usr/local/bin/bash << EOF
#!/bin/bash
# Custom bash wrapper that automatically switches to the dynamic user
if [ "\$(id -u)" = "0" ] && [ -n "$CONTAINER_USER" ]; then
    # We're running as root, switch to the container user
    exec gosu "$CONTAINER_USER" /bin/bash "\$@"
else
    # Already running as the correct user, use normal bash
    exec /bin/bash "\$@"
fi
EOF
chmod +x /usr/local/bin/bash

# Set up environment variables for the user
export HOME="$HOME_DIR"
export USER="$USERNAME"
export SHELL="/bin/bash"

log "Dynamic user setup complete!"
log "Switching to user: $USERNAME"
log "Working directory: $HOME_DIR"

# Ensure the main process runs as the user
log "Ensuring main process runs as user: $USERNAME"

# Change to user's home directory first
cd "$HOME_DIR"

# Switch to the user and execute the command
# Use exec to replace the current process with the user's command
# Source environment variables for Cursor/VS Code compatibility
if [ -f "/etc/profile.d/init_env.sh" ]; then
    log "Sourcing environment variables from /etc/profile.d/init_env.sh"
    source /etc/profile.d/init_env.sh
fi

# Execute command with environment variables loaded
exec gosu "$USERNAME" "$@"

