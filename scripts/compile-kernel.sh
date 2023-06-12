#!/bin/bash

BUILDROOT_VERSION="2023.02.1"
ARCH="$1"
BOARD="$2"

# This script has 2 parameters: Processor architecture and board name

mkdir -p images tmp
git clone --branch $BUILDROOT_VERSION https://github.com/buildroot/buildroot buildroot

cd buildroot

make BR2_EXTERNAL=../kernel/$ARCH-$BOARD ${BOARD}_defconfig
make -j$(nproc)

cd ..

# Information about needed files in docs/Kernel.md

if [ -f buildroot/output/images/fw_payload.elf ]; then
    cp buildroot/output/images/fw_payload.elf tmp
fi

if [ -f buildroot/output/images/Image ]; then
    cp buildroot/output/images/Image tmp
elif [ -f buildroot/output/images/vmlinux ]; then
    cp buildroot/output/images/vmlinux tmp
else
    echo "Kernel not found!"
    exit 1
fi

cp buildroot/output/images/rootfs.cpio tmp
cp buildroot/output/images/*.dtb tmp

cd tmp
tar cJvf ../images/kernel-$ARCH-$BOARD.tar.xz ./*
cd ..

rm -rf tmp buildroot
