FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

COPY containers/fabrinetes-dev-docker/packages.txt /tmp/packages.txt
COPY containers/fabrinetes-dev-docker/python-packages.txt /tmp/python-packages.txt

RUN apt-get update \
    && xargs -r -a /tmp/packages.txt apt-get install -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/packages.txt

RUN pip install --no-cache-dir --break-system-packages -r /tmp/python-packages.txt \
    && rm /tmp/python-packages.txt

RUN locale-gen en_US.UTF-8 \
    && update-locale LANG=en_US.UTF-8

RUN printf '#!/bin/bash\nexec "$@"\n' > /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
