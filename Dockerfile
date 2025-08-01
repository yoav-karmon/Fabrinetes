FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Base system tools, Python, and utilities
RUN apt-get update && apt-get install -y \
    curl \
    git \
    sudo \
    vim \
    bash-completion \
    less \
    ca-certificates \
    iputils-ping \
    net-tools \
    locales \
    wget \
    gtkwave \
    x11-apps \
    git-lfs \
    tcpdump \
    tshark \
    wireshark \
    verilator \
    python3 \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    tmux \
    htop \
    tree \
    jq \
    && apt-get clean && rm -rf /var/lib/apt/lists/*



# Set up locales
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

# Install libtinfo5 from Ubuntu 22.04
RUN wget http://security.ubuntu.com/ubuntu/pool/universe/n/ncurses/libtinfo5_6.3-2ubuntu0.1_amd64.deb && \
    dpkg -i libtinfo5_6.3-2ubuntu0.1_amd64.deb && \
    rm libtinfo5_6.3-2ubuntu0.1_amd64.deb



# Install Python packages
RUN pip3 install --break-system-packages \
    invoke \
    toml \
    tomli_w \
    pyparsing \
    cocotb \
    scapy \
    typeguard







ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Create non-root user 'ykarmon' with UID/GID 1000 and passwordless sudo
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

RUN echo "devbox" > /etc/hostname

WORKDIR ${HOME_DIR}
USER ${USERNAME}





