FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Copy package list
COPY packages.txt /tmp/packages.txt

# Install packages from package list
RUN apt-get update && \
    xargs -a /tmp/packages.txt apt-get install -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/packages.txt

# Set up locales
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Copy dynamic entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set entrypoint for dynamic user creation
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
