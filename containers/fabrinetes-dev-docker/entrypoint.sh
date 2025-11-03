#!/bin/bash
set -e

# Dynamic User Setup Entrypoint Script
# This script creates a user dynamically at runtime instead of static build-time creation

# Get user info from environment variables or use defaults
USERNAME=${CONTAINER_USER:-$(whoami)}
USER_UID=${CONTAINER_UID:-$(id -u)}
USER_GID=${CONTAINER_GID:-$(id -g)}
HOME_DIR=${CONTAINER_HOME:-/home/$USERNAME}

echo "Setting up dynamic user: $USERNAME (UID:$USER_UID, GID:$USER_GID, HOME:$HOME_DIR)"

# Check if CONTAINER_USER is root - if so, switch to root and skip rest of script
if [ "$CONTAINER_USER" = "root" ]; then
    echo "CONTAINER_USER is set to root - switching to root and skipping user setup"
    echo "Verifying root access: $(whoami) (UID: $(id -u))"
    echo "Root mode enabled - executing command as root"
    exec "$@"
fi

# Create user and group dynamically (requires root privileges)
if ! getent group "$USER_GID" > /dev/null; then
    echo "Creating group: $USERNAME (GID:$USER_GID)"
    groupadd --gid "$USER_GID" "$USERNAME"
else
    existing_group=$(getent group "$USER_GID" | cut -d: -f1)
    echo "Group already exists: $existing_group"
    # Rename the group if it's not the expected name
    if [ "$existing_group" != "$USERNAME" ]; then
        echo "Renaming group from $existing_group to $USERNAME"
        groupmod -n "$USERNAME" "$existing_group"
    fi
fi

if ! getent passwd "$USER_UID" > /dev/null; then
    echo "Creating user: $USERNAME (UID:$USER_UID, HOME:$HOME_DIR)"
    useradd --uid "$USER_UID" --gid "$USER_GID" --shell /bin/bash --create-home --home-dir "$HOME_DIR" "$USERNAME"
    # Set proper ownership of home directory after creation
    # Only change ownership of files directly in the home directory, not subdirectories
    chown "$USERNAME:$USERNAME" "$HOME_DIR" 2>/dev/null || true
    # Skip read-only files like .Xauthority - only change writable files
    find "$HOME_DIR" -maxdepth 1 -type f -writable -exec chown "$USERNAME:$USERNAME" {} \; 2>/dev/null || true
    # Set up passwordless sudo for the user (requires root privileges)
    echo "Setting up passwordless sudo for $USERNAME"
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
    chmod 0440 "/etc/sudoers.d/$USERNAME"
else
    echo "User already exists, updating: $USERNAME"
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
        echo "Running as root, skipping user modification"
    fi
fi

# ========================================
# SUDO CONFIGURATION SECTION
# ========================================
echo "=== SUDO CONFIGURATION SECTION ==="
echo "Setting up passwordless sudo for user: $USERNAME"

# Method 1: Create sudoers.d file (preferred method)
echo "Creating sudoers.d file for $USERNAME"
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
chmod 0440 "/etc/sudoers.d/$USERNAME"
echo "✓ Sudoers.d file created: /etc/sudoers.d/$USERNAME"

# Method 2: Add to sudo group as backup
echo "Adding $USERNAME to sudo group"
usermod -aG sudo "$USERNAME" 2>/dev/null || echo "⚠ Warning: Could not add to sudo group"
echo "✓ Added $USERNAME to sudo group"

# Method 3: Add to main sudoers file as additional backup
echo "Adding $USERNAME to main sudoers file"
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> "/etc/sudoers"
echo "✓ Added to main sudoers file"

# Verify sudoers file syntax
echo "Verifying sudoers file syntax"
if visudo -c -f "/etc/sudoers.d/$USERNAME" 2>/dev/null; then
    echo "✓ Sudoers file syntax verified for $USERNAME"
else
    echo "⚠ Warning: sudoers file syntax check failed for $USERNAME"
fi

# Test sudo access
echo "Testing sudo access for $USERNAME"
if sudo -u "$USERNAME" sudo -n whoami 2>/dev/null; then
    echo "✓ Passwordless sudo test PASSED for $USERNAME"
else
    echo "⚠ Warning: Passwordless sudo test FAILED for $USERNAME"
fi

echo "=== END SUDO CONFIGURATION SECTION ==="
echo ""

# Set hostname (requires root privileges)
echo "Setting hostname to: Fabrinetes"
echo "Fabrinetes" > /etc/hostname

# Create a custom bash wrapper that automatically switches to the dynamic user
echo "Creating custom bash wrapper for automatic user switching"
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

echo "Dynamic user setup complete!"
echo "Switching to user: $USERNAME"
echo "Working directory: $HOME_DIR"

# Ensure the main process runs as the user
echo "Ensuring main process runs as user: $USERNAME"

# Switch to the user and execute the command
# Use exec to replace the current process with the user's command
# Note: init_env.sh will be sourced automatically by bashrc-root when bash starts
# Note: The user's shell (bash) will start in their home directory by default
echo "entrypoint.sh: switching to user: $USERNAME and executing command: $@"
echo "entrypoint.sh: completed successfully"
echo ""
exec gosu "$USERNAME" "$@"

