# !!! Copyright is missing here

FROM debian:bullseye AS base

RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
    ca-certificates \
    git \
    wget \
 && apt-get autoclean && apt-get clean && apt-get -y autoremove \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*


FROM base as builder

RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
    bc \
    bzip2 \
    cpio \
    file \
    g++ \
    make \
    patch \
    rsync \
    unzip \
 && apt-get autoclean && apt-get clean && apt-get -y autoremove \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --branch 2022.08.1 https://github.com/buildroot/buildroot /buildroot

COPY buildroot_patches/*.patch /buildroot/
RUN cd /buildroot \
 && git apply *.patch \
 && make hifive_unleashed_defconfig \
 && make \
 && mkdir /tmp/images \
 && cd output/images \
 && cp hifive-unleashed-a00.dtb fw_payload.elf Image rootfs.cpio /tmp/images


FROM base

COPY --from=builder /tmp/images /images
COPY payload/* /

ARG RENODE_VERSION=1.13.0
RUN wget https://github.com/renode/renode/releases/download/v${RENODE_VERSION}/renode_${RENODE_VERSION}_amd64.deb

RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
    python3 \
    python3-dev \
    expect \
    telnet \
    ./renode_${RENODE_VERSION}_amd64.deb \
 && apt-get autoclean && apt-get clean && apt-get -y autoremove \
 && rm -rf /var/lib/apt/lists/* \
 && pip3 install -r /opt/renode/tests/requirements.txt --no-cache-dir \
 && pip3 install pexpect --no-cache-dir

ENTRYPOINT [ "/entrypoint.sh" ]
