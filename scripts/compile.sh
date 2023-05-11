#!/bin/bash

BUILDROOT_VERSION="2022.11.3"
ARCH="$1"
TYPE="$2"

# This script has 3 parameters: Processor architecture, type (kernel or image)
# and board name (for kernel type) or name of the image

if [ $TYPE = "kernel" ]; then
    BOARD="$3"
else
    NAME="$3"
fi

# If name is not specified the default image will be compiled

if [ -z "$NAME" ]; then
    NAME="default"
fi

mkdir -p images
git clone --branch $BUILDROOT_VERSION https://github.com/buildroot/buildroot buildroot

cd buildroot

if [ $TYPE = "kernel" ]; then
    make BR2_EXTERNAL=../$TYPE/$ARCH-$BOARD ${BOARD}_defconfig
else
    make BR2_EXTERNAL=../$TYPE/$ARCH-$NAME ${ARCH}_defconfig
fi

make -j$(nproc)

cd ..

# Information about needed files in docs/Kernel.md and docs/Image.md

if [ $TYPE = "kernel" ]; then
    cp buildroot/output/images/{fw_payload.elf,rootfs.cpio} .
    tar cJvf images/kernel-$ARCH-$BOARD.tar.xz ./{fw_payload.elf,rootfs.cpio}
    rm -rf ./{fw_payload.elf,rootfs.cpio}
else
    cp buildroot/output/images/rootfs.tar images/image-$ARCH-$NAME.tar
    xz -z images/image-$ARCH-$NAME.tar
fi

rm -rf buildroot
