FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install basic packages
RUN apt-get update && \
    apt-get install -y locales sudo python3 python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set up locales
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Create user and set hostname (ROOT OPERATIONS - must be done before switching to non-root user)
ARG USERNAME
ARG UID
ARG GID
ARG HOME_DIR

RUN set -eux; \
    # Create or modify user/group (requires root privileges) \
    if getent group "$GID" > /dev/null; then \
        groupmod -n "$USERNAME" "$(getent group "$GID" | cut -d: -f1)"; \
    else \
        groupadd --gid "$GID" "$USERNAME"; \
    fi; \
    if getent passwd "$UID" > /dev/null; then \
        usermod -l "$USERNAME" "$(getent passwd "$UID" | cut -d: -f1)"; \
        usermod -d "${HOME_DIR}" -m "$USERNAME"; \
        groupmod -g "$GID" "$USERNAME"; \
    else \
        useradd --uid "$UID" --gid "$GID" --shell /bin/bash --create-home --home-dir "${HOME_DIR}" "$USERNAME"; \
    fi; \
    # Set up passwordless sudo for the user (requires root privileges) \
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"; \
    chmod 0440 "/etc/sudoers.d/$USERNAME"; \
    # Set hostname (requires root privileges to write to /etc/hostname) \
    echo "skeleton" > /etc/hostname

# Set environment variables and switch to non-root user
ARG HOME_DIR
ENV HOME=${HOME_DIR}
ENV SHELL=/bin/bash

WORKDIR ${HOME_DIR}
USER ${USERNAME}
