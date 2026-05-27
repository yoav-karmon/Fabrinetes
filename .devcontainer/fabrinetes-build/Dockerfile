FROM ubuntu:24.04

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    FABRINETES=/opt/Fabrinetes

COPY .devcontainer/fabrinetes-build/packages.txt /tmp/packages.txt
COPY .devcontainer/fabrinetes-build/python-packages.txt /tmp/python-packages.txt

RUN apt-get update \
    && xargs -r -a /tmp/packages.txt apt-get install -y \
    && pip install --no-cache-dir --break-system-packages -r /tmp/python-packages.txt \
    && locale-gen en_US.UTF-8 \
    && update-locale LANG=en_US.UTF-8 \
    && if ! getent group "${USER_GID}" >/dev/null; then groupadd --gid "${USER_GID}" "${USERNAME}"; fi \
    && if getent passwd "${USER_UID}" >/dev/null; then \
         existing_user="$(getent passwd "${USER_UID}" | cut -d: -f1)" \
         && if [ "${existing_user}" != "${USERNAME}" ]; then usermod -l "${USERNAME}" "${existing_user}"; fi \
         && usermod --home "/home/${USERNAME}" --move-home "${USERNAME}" 2>/dev/null || usermod --home "/home/${USERNAME}" "${USERNAME}"; \
       else \
         useradd --uid "${USER_UID}" --gid "${USER_GID}" --shell /bin/bash --create-home "${USERNAME}"; \
       fi \
    && usermod --gid "${USER_GID}" "${USERNAME}" \
    && mkdir -p "/home/${USERNAME}" \
    && chown "${USER_UID}:${USER_GID}" "/home/${USERNAME}" \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
    && chmod 0440 "/etc/sudoers.d/${USERNAME}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/packages.txt /tmp/python-packages.txt

RUN printf '#!/bin/bash\nexec "$@"\n' > /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
