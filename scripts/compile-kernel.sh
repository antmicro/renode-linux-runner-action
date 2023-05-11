#!/bin/bash

BUILDROOT_VERSION="2022.11.3"
ARCH="$1"
BOARD="$2"

# This script has 2 parameters: Processor architecture and board name

mkdir -p images
git clone --branch $BUILDROOT_VERSION https://github.com/buildroot/buildroot buildroot

cd buildroot

make BR2_EXTERNAL=../kernel/$ARCH-$BOARD ${BOARD}_defconfig
make -j$(nproc)

cd ..

# Information about needed files in docs/Kernel.md

cp buildroot/output/images/{fw_payload.elf,rootfs.cpio} .
tar cJvf images/kernel-$ARCH-$BOARD.tar.xz ./{fw_payload.elf,rootfs.cpio}
rm -rf ./{fw_payload.elf,rootfs.cpio} buildroot
