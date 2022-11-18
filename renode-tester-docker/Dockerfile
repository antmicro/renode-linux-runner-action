FROM debian:bullseye as builder

RUN apt-get update && \
    apt-get install -y wget git file cpio unzip rsync bc make g++ bzip2

RUN git clone --branch 2022.08.1 https://github.com/buildroot/buildroot
WORKDIR /buildroot
COPY buildroot_patches/*.patch ./
RUN git apply *.patch
RUN make hifive_unleashed_defconfig
RUN make

FROM debian:bullseye
RUN mkdir images
COPY --from=builder /buildroot/output/images/hifive-unleashed-a00.dtb /images
COPY --from=builder /buildroot/output/images/fw_payload.elf /images
COPY --from=builder /buildroot/output/images/Image /images
COPY --from=builder /buildroot/output/images/rootfs.cpio /images

RUN apt-get update && apt-get -y install wget python3-dev git expect telnet

ARG RENODE_VERSION=1.13.0
RUN wget https://github.com/renode/renode/releases/download/v${RENODE_VERSION}/renode_${RENODE_VERSION}_amd64.deb && \
    apt-get install -y --no-install-recommends ./renode_${RENODE_VERSION}_amd64.deb && \
    rm ./renode_${RENODE_VERSION}_amd64.deb && \
    rm -rf /var/lib/apt/lists/*
RUN pip3 install -r /opt/renode/tests/requirements.txt --no-cache-dir

COPY renode-setup.sh /
COPY *.expect /
COPY hifive.resc /

WORKDIR /github/workspace
