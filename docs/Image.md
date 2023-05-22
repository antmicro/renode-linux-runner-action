# Image

This section details how to work with `image` packages that are compatible with this action. You can treat these images like containers: they provide the userspace software you need, compiled on the specified processor architecture, but have nothing to do with device drivers, the kernel, or the bootloader.

## Image type

There are two types of images that are compatible with this action:

* native: all files are placed in the `.tar.xz` archive
* docker: docker container (not yet supported)

### Native images

A native image is just an archive with a full Linux rootfs. You can add any files you want. The only requirement is a `/bin/sh` and binaries compiled for the specified architecture.

### Docker images

Work in progress...

## Default images available

Currently, the following `image` configurations are provided:

* riscv64:

  * image-riscv64-default.tar.xz

This image contains the following software:

* Full busybox 1.35.0 with ash shell
* Python 3.10.8
* pip 21.2.4
* v4l2-utils 1.22.1
* libgpiod tools 1.6.3
* git 2.31.7
* curl 7.88.1

## Required native image components

Your custom `image` package should include the required file system directory structure; to find out more please read [this](https://en.wikipedia.org/wiki/Filesystem_Hierarchy_Standard):

Additionally you will need:

* shell executable available from `/bin/sh`
* If you want to use [`python-packages`](./Python-packages.md) you need `pip` available in your $PATH.

## Create your own native image

You can create the `image` package using any method you like, but we recommend using `buildroot`. It provides a lot of configuration options and will produce the file structure that this action requires.

First, you may want to download the default `image` package configuration and modify it. The configuration is stored in the `image/<arch-name>` directory.

### Adding the applications

If you want to add applications that we do not currently offer in our build, take a look at the `configs/riscv64_defconfig` file. There you can add the additional applications offered by `buildroot`. You may also want to add specific package configurations or custom patches for them. See the `buildroot` documentation for more.

### Preparing the archive

Download the latest `buildroot` from [GitHub](https://github.com/buildroot/buildroot) and apply your configuration with:

```sh
make BR2_EXTERNAL=path/to/configuration name_defconfig
```

and start compiling:

```sh
make -j$(nproc)
```

This will take some time.

Eventually, you should have a `rootfs.tar` in the `buildroot/output/images` directory. Create the `xz` archive with `xz -z rootfs.tar'.

### Use your image

```yaml
- uses: antmicro/renode-linux-runner-action@v0
  with:
    arch: your-arch (i.e. riscv64)
    image-type: native
    image: path/to/image or URL
    renode-run: sh --help
```
