# Copyright 2022 Antmicro Ltd.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Co-authored by: Unai Martinez-Corral (@umarcor)

FROM debian:bullseye AS base

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
    ca-certificates \
    git \
    wget && \
    apt-get autoclean && apt-get clean && apt-get autoremove -y && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*


FROM base as builder

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bc \
    bzip2 \
    cpio \
    file \
    g++ \
    make \
    patch \
    rsync \
    unzip && \
    apt-get autoclean && apt-get clean && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

RUN git clone --branch 2022.08.1 https://github.com/buildroot/buildroot /buildroot

COPY buildroot_patches/*.patch /buildroot/

RUN cd /buildroot && \
    git apply *.patch && \
    make hifive_unleashed_defconfig && \
    make && \
    mkdir /tmp/images && \
    cd output/images && \
    cp hifive-unleashed-a00.dtb fw_payload.elf Image rootfs.cpio /tmp/images


FROM base

COPY --from=builder /tmp/images /images
COPY payload/* /

ARG RENODE_VERSION=1.13.0
RUN wget https://github.com/renode/renode/releases/download/v${RENODE_VERSION}/renode_${RENODE_VERSION}_amd64.deb

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    telnet \
    ./renode_${RENODE_VERSION}_amd64.deb && \
    apt-get autoclean && apt-get clean && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install -r /opt/renode/tests/requirements.txt --no-cache-dir && \
    pip3 install pexpect --no-cache-dir

ENTRYPOINT [ "/run-in-renode.py" ]
