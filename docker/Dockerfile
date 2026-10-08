ARG BASE_IMAGE=ubuntu:resolute
FROM ${BASE_IMAGE}

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
ENV DEBIAN_FRONTEND=noninteractive

# Common build/test tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config \
        git curl wget ca-certificates gnupg \
        sudo less vim nano jq unzip zip \
        python3 python3-pip python3-venv \
        iproute2 iputils-ping net-tools procps htop \
        tzdata locales bash-completion \
    && rm -rf /var/lib/apt/lists/*

# Recent Ubuntu images ship a default "ubuntu" user at UID 1000; remove it so
# our dev user can take the host's UID/GID (keeps file ownership clean on ./workspace)
RUN if id ubuntu >/dev/null 2>&1; then userdel -r ubuntu || true; fi \
    && if getent group ${USER_GID} >/dev/null; then \
           groupmod -n ${USERNAME} "$(getent group ${USER_GID} | cut -d: -f1)"; \
       else groupadd -g ${USER_GID} ${USERNAME}; fi \
    && useradd -m -s /bin/bash -u ${USER_UID} -g ${USER_GID} ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

RUN mkdir -p /workspace && chown ${USER_UID}:${USER_GID} /workspace

USER ${USERNAME}
WORKDIR /workspace
CMD ["bash"]
