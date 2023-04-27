#!/bin/sh

# Repack rootfs to the ext4 image

PATH=/usr/sbin:$PATH

cd output/images

# Clear previous images

[ -f rootfs ] && rm -rf rootfs
[ -e rootfs.img ] && rm -f rootfs.img

mkdir -p rootfs
tar -xf rootfs.tar --directory rootfs

truncate rootfs.img -s 120M
mkfs.ext4 -d rootfs rootfs.img
