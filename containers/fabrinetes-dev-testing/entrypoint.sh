#!/bin/bash
set -e

# Dynamic User Setup Entrypoint Script
# This script creates a user dynamically at runtime instead of static build-time creation

# Get user info from environment variables or use defaults
USERNAME=${CONTAINER_USER:-$(whoami)}
UID=${CONTAINER_UID:-$(id -u)}
GID=${CONTAINER_GID:-$(id -g)}
HOME_DIR=${CONTAINER_HOME:-/home/$USERNAME}

echo "🔧 Setting up dynamic user: $USERNAME (UID:$UID, GID:$GID, HOME:$HOME_DIR)"

# Create user and group dynamically (requires root privileges)
if ! getent group "$GID" > /dev/null; then
    echo "📁 Creating group: $USERNAME (GID:$GID)"
    groupadd --gid "$GID" "$USERNAME"
else
    echo "📁 Group already exists: $(getent group "$GID" | cut -d: -f1)"
fi

if ! getent passwd "$UID" > /dev/null; then
    echo "👤 Creating user: $USERNAME (UID:$UID, HOME:$HOME_DIR)"
    useradd --uid "$UID" --gid "$GID" --shell /bin/bash --create-home --home-dir "$HOME_DIR" "$USERNAME"
else
    echo "👤 User already exists, updating: $USERNAME"
    usermod -l "$USERNAME" "$(getent passwd "$UID" | cut -d: -f1)"
    usermod -d "$HOME_DIR" -m "$USERNAME"
fi

# Set up passwordless sudo for the user (requires root privileges)
echo "🔐 Setting up passwordless sudo for $USERNAME"
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
chmod 0440 "/etc/sudoers.d/$USERNAME"

# Set hostname (requires root privileges)
echo "🏷️ Setting hostname to: skeleton"
echo "skeleton" > /etc/hostname

# Set up environment variables for the user
export HOME="$HOME_DIR"
export USER="$USERNAME"
export SHELL="/bin/bash"

echo "✅ Dynamic user setup complete!"
echo "🚀 Switching to user: $USERNAME"
echo "📂 Working directory: $HOME_DIR"

# Switch to the user and execute the command
exec su-exec "$USERNAME" "$@"
