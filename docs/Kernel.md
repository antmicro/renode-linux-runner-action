# Kernel

> **Warning**
> Replacing the default kernel package should be avoided unless you really know what you're doing or you need kernel drivers that we don't provide in the default images.

This section describes in detail how to build `kernel` packages that will be compatible with this action.

First, it is worth mentioning that what we call the `kernel` package is actually a `tar.xz` archive containing `initramfs` and firmware for the emulated system. Currently, we only support the RISC-V architecture and the HiFive Unleashed board, so the `kernel` package should be customized for that particular device.

## Default images available

We currently provide the following `kernel` configurations:

* riscv64:

  * kernel-riscv64-hifive_unleashed.tar.xz

This package contains drivers essential for HiFive Unleashed, but we have also added some other drivers:

* `vivid` for Video4Linux
* `i2c-stub`
* `gpio-mockup`

There is also a Busybox with essential commands.

## Required image components

Your custom `kernel` package should include:

* `fw_payload.elf`: the bootloader and firmware for the HiFive Unleashed platform
* `rootfs.cpio`: a packed `initramfs` compiled for the selected architecture (`riscv64`)

`rootfs.cpio` should contain:

* in the `/boot` directory, the file `Image` that should be the compiled kernel for the selected architecture.
* in the `/boot` directory, the device tree binary file for the specified board with the `.dtb` file extension.
* `/init`, an executable script that redirects output to `ttyS0` device and starts an interactive shell session.
* basic programs like: `sh`, `mount`, `chroot`, `dmesg`, `date`.
* If you want to use networking, you should provide the `ip` command and network stack.

## Create your own custom kernel package

You can build the `kernel` package using any method you like, but we recommend using `buildroot`. It provides a lot of configuration options and will produce the file structure that this action requires.
First, you may want to download the default `kernel` package configuration and modify it. The configuration is stored in the `kernel/<arch-board>` directory.

### Adding Devices and Modifying Other Components

If you want to add devices that we currently do not offer in our build, take a look at the `configs/linux.config.fragment` file. You can add the additional drivers there. You may also want to change the kernel version in `configs/board_defconfig` or add/delete some kernel patches in `patches/linux`.

### Preparing the archive

Download the latest `buildroot` from [GitHub](https://github.com/buildroot/buildroot) and apply your configuration with:

```sh
make BR2_EXTERNAL=path/to/configuration board_name_defconfig
```

and start compiling:

```sh
make -j$(nproc)
```

This will take some time.

Eventually, you should have some files in the `buildroot/output/images` directory. Create the new `tar.xz` archive with the files: `rootfs.cpio` and `fw_payload.elf`. The resulting archive is ready to use with the action.

### Use your kernel

```yaml
- uses: antmicro/renode-linux-runner-action@v0
  with:
    arch: your-arch (i.e. riscv64)
    kernel: path/to/kernel or URL
    renode-run: sh --help
```
