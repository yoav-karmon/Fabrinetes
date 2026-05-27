#!/bin/bash
set -e

USERNAME=${CONTAINER_USER:-$(id -un)}
HOME_DIR=${CONTAINER_HOME:-/home/$USERNAME}

detect_mount_uid() {
    local path
    for path in \
        "${FABRINETES:-}" \
        "${FABRINETES_ROOT:-}" \
        "$HOME_DIR/repo/fpga" \
        "$HOME_DIR/repo" \
        "$PWD"
    do
        if [ -n "$path" ] && [ -e "$path" ]; then
            stat -c '%u' "$path"
            return 0
        fi
    done
    id -u
}

detect_mount_gid() {
    local path
    for path in \
        "${FABRINETES:-}" \
        "${FABRINETES_ROOT:-}" \
        "$HOME_DIR/repo/fpga" \
        "$HOME_DIR/repo" \
        "$PWD"
    do
        if [ -n "$path" ] && [ -e "$path" ]; then
            stat -c '%g' "$path"
            return 0
        fi
    done
    id -g
}

USER_UID=${CONTAINER_UID:-$(detect_mount_uid)}
USER_GID=${CONTAINER_GID:-$(detect_mount_gid)}

echo "Setting up dynamic user: $USERNAME (UID:$USER_UID, GID:$USER_GID, HOME:$HOME_DIR)"

if [ "$USERNAME" = "root" ]; then
    exec "$@"
fi

if getent group "$USERNAME" >/dev/null; then
    USER_GROUP="$USERNAME"
elif getent group "$USER_GID" >/dev/null; then
    USER_GROUP=$(getent group "$USER_GID" | cut -d: -f1)
else
    groupadd --gid "$USER_GID" "$USERNAME"
    USER_GROUP="$USERNAME"
fi

if id "$USERNAME" >/dev/null 2>&1; then
    true
elif getent passwd "$USER_UID" >/dev/null; then
    USERNAME=$(getent passwd "$USER_UID" | cut -d: -f1)
else
    useradd \
        --uid "$USER_UID" \
        --gid "$USER_GROUP" \
        --shell /bin/bash \
        --create-home \
        --home-dir "$HOME_DIR" \
        "$USERNAME"
fi

mkdir -p "$HOME_DIR"
if [ "$(getent passwd "$USERNAME" | cut -d: -f6)" != "$HOME_DIR" ]; then
    usermod -d "$HOME_DIR" "$USERNAME"
fi
chown "$USERNAME:$USER_GROUP" "$HOME_DIR" 2>/dev/null || true

echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"
chmod 0440 "/etc/sudoers.d/$USERNAME"
usermod -aG sudo "$USERNAME" 2>/dev/null || true

export HOME="$HOME_DIR"
export USER="$USERNAME"
export SHELL="/bin/bash"

if [ -f /etc/profile.d/init_env.sh ]; then
    # shellcheck disable=SC1091
    source /etc/profile.d/init_env.sh
fi

cd "$HOME_DIR"

if command -v gosu >/dev/null 2>&1; then
    exec gosu "$USERNAME" sleep infinity
fi

exec sleep infinity
