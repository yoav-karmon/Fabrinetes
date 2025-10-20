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

# Create user and group dynamically (requires root privileges)
if ! getent group "$USER_GID" > /dev/null; then
    echo "Creating group: $USERNAME (GID:$USER_GID)"
    groupadd --gid "$USER_GID" "$USERNAME"
else
    echo "Group already exists: $(getent group "$USER_GID" | cut -d: -f1)"
fi

if ! getent passwd "$USER_UID" > /dev/null; then
    echo "Creating user: $USERNAME (UID:$USER_UID, HOME:$HOME_DIR)"
    useradd --uid "$USER_UID" --gid "$USER_GID" --shell /bin/bash --create-home --home-dir "$HOME_DIR" "$USERNAME"
    # Set proper ownership of home directory after creation
    chown -R "$USERNAME:$USERNAME" "$HOME_DIR"
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
        chown -R "$USERNAME:$USERNAME" "$HOME_DIR"
        # Set up passwordless sudo for the user (requires root privileges)
        echo "Setting up passwordless sudo for $USERNAME"
        echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
        chmod 0440 "/etc/sudoers.d/$USERNAME"
    else
        echo "Running as root, skipping user modification"
    fi
fi

# Set hostname (requires root privileges)
echo "Setting hostname to: Fabrinetes"
echo "Fabrinetes" > /etc/hostname

# Set up environment variables for the user
export HOME="$HOME_DIR"
export USER="$USERNAME"
export SHELL="/bin/bash"

echo "Dynamic user setup complete!"
echo "Switching to user: $USERNAME"
echo "Working directory: $HOME_DIR"

# Ensure the main process runs as the user
echo "Ensuring main process runs as user: $USERNAME"

# Change to user's home directory first
cd "$HOME_DIR"

# Switch to the user and execute the command
# Use exec to replace the current process with the user's command
exec gosu "$USERNAME" "$@"

