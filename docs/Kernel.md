# Kernel

> **Warning**
> Replacing the default kernel package should be avoided unless you really know what you're doing or you need kernel drivers that we don't provide in the default images.

This section describes in detail how to build `kernel` packages that will be compatible with this action.

First, it is worth mentioning that what we call the `kernel` package is actually a `tar.xz` archive containing `initramfs` and firmware for the emulated system.

## Default images available

We currently provide the following `kernel` configurations:

* riscv64:

  * kernel-riscv64-hifive_unleashed.tar.xz

* arm32:

  * kernel-arm32-zynq_7000.tar.xz

This packages contains drivers essential for selected boards, but we have also added some other drivers:

* `vivid` for Video4Linux
* `i2c-stub`
* `gpio-mockup`

There is also a Busybox with essential commands.

## Required image components

Your custom `kernel` package should include:

* The file `vmlinux` or `Image`: the compiled kernel for the selected architecture with the bootloader and firmware if vmlinux is provided
* `fw_payload.elf`: (for `Image` kernel) the bootloader and firmware for the board
* `rootfs.cpio`: a packed `initramfs` compiled for the selected architecture
* `.dtb` file: the device tree binary file for the specified board with the `.dtb` file extension.

`rootfs.cpio` should contain:

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

Eventually, you should have some files in the `buildroot/output/images` directory. Create the new `tar.xz` archive with [required files](#required-image-components). The resulting archive is ready to use with the action.

### Use your kernel

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    arch: your-arch (i.e. riscv64)
    kernel: path/to/kernel or URL
    renode-run: sh --help
```
