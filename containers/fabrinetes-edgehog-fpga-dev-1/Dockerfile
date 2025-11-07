FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Copy package lists
COPY packages.txt /tmp/packages.txt
COPY python-packages.txt /tmp/python-packages.txt

# Entrypoint script will be mounted at runtime

# Install packages from package list
RUN apt-get update && \
    xargs -a /tmp/packages.txt apt-get install -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/packages.txt

# Install Python packages
RUN pip install --no-cache-dir --break-system-packages -r /tmp/python-packages.txt && \
    rm /tmp/python-packages.txt

# Fix Cocotb path issue - create symlink for user-local path
RUN mkdir -p /home/ubuntu/.local/lib/python3.12/site-packages/cocotb/share/lib/verilator && \
    ln -sf /usr/local/lib/python3.12/dist-packages/cocotb/share/lib/verilator/verilator.cpp /home/ubuntu/.local/lib/python3.12/site-packages/cocotb/share/lib/verilator/verilator.cpp

# Set up locales
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Set entrypoint to run the dynamic user setup script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
