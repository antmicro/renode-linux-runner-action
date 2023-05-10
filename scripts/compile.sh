#!/bin/sh

mkdir -p images
git clone --branch 2022.11.3 https://github.com/buildroot/buildroot buildroot

cd buildroot

# Set configuration for initramfs

make BR2_EXTERNAL=../br2-external hifive_unleashed_defconfig
make -j$(nproc)

cd ..

for i in hifive-unleashed-a00.dtb fw_payload.elf Image rootfs.cpio; do
    cp buildroot/output/images/$i images
done

# Clear only target binaries, do not delete host toolchain that will be used again
# More info: https://stackoverflow.com/questions/47320800/how-to-clean-only-target-in-buildroot

cd buildroot

rm -rf output/target
find output/ -name ".stamp_target_installed" -delete
rm -f output/build/host-gcc-final-*/.stamp_host_installed

# Set configuration for rootfs

make BR2_EXTERNAL=../br2-external/rootfs hifive_unleashed_defconfig
make -j$(nproc)

cd ..

cp buildroot/output/images/rootfs.tar images
rm -rf buildroot

tar cJvf images.tar.xz images
