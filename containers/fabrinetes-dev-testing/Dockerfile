FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Base system tools, Python, and utilities (lightweight for testing)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    sudo \
    vim \
    bash-completion \
    less \
    ca-certificates \
    locales \
    python3 \
    python3-pip \
    tmux \
    htop \
    tree \
    jq \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set up locales
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

RUN pip3 install --no-cache-dir --break-system-packages \
    invoke \
    toml \
    tabulate

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Create non-root user with passwordless sudo
ARG USERNAME
ARG UID
ARG GID
ARG HOME_DIR

RUN set -eux; \
    \
    # Rename existing group with GID=1000 to $USERNAME, or create it
    if getent group "$GID" > /dev/null; then \
        groupmod -n "$USERNAME" "$(getent group "$GID" | cut -d: -f1)"; \
    else \
        groupadd --gid "$GID" "$USERNAME"; \
    fi; \
    \
    # Rename existing user with UID=1000 to $USERNAME, or create it
    if getent passwd "$UID" > /dev/null; then \
        usermod -l "$USERNAME" "$(getent passwd "$UID" | cut -d: -f1)"; \
        usermod -d "${HOME_DIR}" -m "$USERNAME"; \
        groupmod -g "$GID" "$USERNAME"; \
    else \
        useradd --uid "$UID" --gid "$GID" --shell /bin/bash --create-home --home-dir "${HOME_DIR}" "$USERNAME"; \
    fi; \
    \
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME"; \
    chmod 0440 "/etc/sudoers.d/$USERNAME"

# Set working dir and hostname
ARG HOME_DIR
ENV HOME=${HOME_DIR}
ENV SHELL=/bin/bash

RUN echo "testbox" > /etc/hostname

WORKDIR ${HOME_DIR}
USER ${USERNAME}
