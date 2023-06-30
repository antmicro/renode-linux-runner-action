#!/bin/bash

BUILDROOT_VERSION="2023.02.2"
ARCH="$1"
NAME="$2"

# This script has 2 parameters: Processor architecture and name of the image

# If name is not specified the default image will be compiled

if [ -z "$NAME" ]; then
    NAME="default"
fi

mkdir -p images
git clone --branch $BUILDROOT_VERSION https://github.com/buildroot/buildroot buildroot

cd buildroot

make BR2_EXTERNAL=../image/$ARCH-$NAME ${ARCH}_defconfig
make -j$(nproc)

cd ..

# Information about needed files in docs/Image.md

cp buildroot/output/images/rootfs.tar images/image-$ARCH-$NAME.tar
xz -z images/image-$ARCH-$NAME.tar

rm -rf buildroot
