FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install base packages + locales
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
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y verilator

# Set up locales
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

# Install libtinfo5 from Ubuntu 22.04
RUN wget http://security.ubuntu.com/ubuntu/pool/universe/n/ncurses/libtinfo5_6.3-2ubuntu0.1_amd64.deb && \
    dpkg -i libtinfo5_6.3-2ubuntu0.1_amd64.deb && \
    rm libtinfo5_6.3-2ubuntu0.1_amd64.deb

# Install Python and pip-related tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-setuptools \
    python3-wheel \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --break-system-packages invoke toml
RUN pip3 install --break-system-packages tomli_w
RUN pip3 install --break-system-packages pyparsing
RUN pip3 install --break-system-packages cocotb
RUN pip3 install --break-system-packages scapy
RUN pip3 install --break-system-packages typeguard







ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Set working dir and hostname
WORKDIR /root
RUN echo "devbox" > /etc/hostname




