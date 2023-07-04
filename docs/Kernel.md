# Kernel

> **Warning**
> Replacing the default kernel package should be avoided unless you really know what you're doing or you need kernel drivers that we don't provide in the default images.

This section describes in detail how to build `kernel` packages that will be compatible with this action.

Firstly, it is worth mentioning that what we call the `kernel` package is actually a `tar.xz` archive containing `initramfs` and firmware for the emulated system.

## Available default images

We currently provide the following `kernel` configurations:

* riscv64:

  * kernel-riscv64-hifive_unleashed.tar.xz

* arm32:

  * kernel-arm32-zynq_7000.tar.xz

The packages contain a Busybox with essential commands, drivers essential for these boards, and other drivers:

* `vivid` for Video4Linux
* `i2c-stub`
* `gpio-mockup`

## Required image components

Your custom `kernel` package should include:

* A `vmlinux` or `Image` file - a compiled kernel for the selected architecture, and a bootloader and firmware for `vmlinux` kernels
* `fw_payload.elf` - a bootloader and firmware for `Image` kernels
* `rootfs.cpio` - a packaged `initramfs` compiled for the selected architecture
* `.dtb` file - a device tree binary file for the specified board.

`rootfs.cpio` should contain:

* `/init`, an executable script that redirects output to the `ttyS0` device and starts an interactive shell session.
* basic programs like: `sh`, `mount`, `chroot`, `dmesg`, `date`.
* the `ip` command and a network stack, should you want to use networking.

## Create your own custom kernel package

You can build the `kernel` package using any method you like, but we recommend using `buildroot`. It provides many configuration options and will produce the file structure that this action requires.
To start, you can download the default `kernel` package configuration and modify it. The configuration is stored in the `kernel/<arch-board>` directory.

### Adding Devices and Modifying Other Components

If you want to add devices that we currently do not offer in our build, take a look at the `configs/linux.config.fragment` file. You can add the necessary drivers there. You may also want to change the kernel version in `configs/board_defconfig` or add/delete kernel patches in `patches/linux`.

### Preparing the archive

Download the latest `buildroot` from [GitHub](https://github.com/buildroot/buildroot) and apply your configuration with:

```sh
make BR2_EXTERNAL=path/to/configuration board_name_defconfig
```

Start compiling:

```sh
make -j$(nproc)
```

This will take some time.

You should end up with files in the `buildroot/output/images` directory. Create a new `tar.xz` archive with the [required files](#required-image-components). The resulting archive is ready for use with the action.

### Use your kernel

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    arch: your-arch (i.e. riscv64)
    kernel: path/to/kernel or URL
    renode-run: sh --help
```
