# Image

This section describes the workflow for `image` packages compatible with this action. You can treat these images like containers as they provide you with userspace software compiled for a specified processor architecture, independent from device drivers, the kernel, or the bootloader.

## Image type

There are two types of images compatible with this action:

* native: all files are located in a `.tar.xz` archive
* docker: docker container

### Native images

A native image is an archive with a full Linux rootfs. You can add any files you want. The only requirement is a `/bin/sh` and binaries compiled for a specified architecture.

### Docker images

The `docker` image type is a standard Docker image. The action will repack the latest layer into the standard `.tar.xz` archive and everything will continue as in the native image. The Docker images are downloaded from DockerHub. Here is an example of using the `docker` image type:

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    arch: riscv64
    image-type: docker
    image: riscv64/debian:experimental
    renode-run: |
      ls /dev | grep video
      bash bash_test.sh
    devices: vivid
```

## Default images available

Currently, the following `image` configurations are provided:

* riscv64:

  * image-riscv64-default.tar.xz

* arm32:

  * image-arm32-default.tar.xz

These images contain the following software:

* Full busybox 1.36.0 with ash shell
* Python 3.11.2
* pip 22.3.1
* v4l2-utils 1.22.1
* libgpiod tools 1.6.3
* git 2.39.3
* curl 7.88.1

## Required native image components

Your custom `image` package should include the required file system directory structure. To learn more, read [the Filesystem Hierarchy Standard Wikipedia entry](https://en.wikipedia.org/wiki/Filesystem_Hierarchy_Standard):

Additionally you will need:

* a shell executable available from `/bin/sh`
* `pip` available in your $PATH if you want to use [`python-packages`](./Python-packages.md).

## Create your own native image

You can create an `image` package using any method you like, but we recommend using `buildroot`. It provides many configuration options and will produce the file structure required by this action.

To start, you can download the default `image` package configuration and modify it. The configuration is stored in the `image/<arch-name>` directory.

### Adding applications

If you want to add applications that we do not currently offer in our build, take a look at the `configs/riscv64_defconfig` file. There you can add additional applications offered by `buildroot`. You may also want to add specific package configurations or custom patches for them. See the `buildroot` documentation for more.

### Preparing the archive

Download the latest `buildroot` from [GitHub](https://github.com/buildroot/buildroot) and apply your configuration with:

```sh
make BR2_EXTERNAL=path/to/configuration name_defconfig
```

Then start compiling:

```sh
make -j$(nproc)
```

This will take some time.

Eventually, you should end up with a `rootfs.tar` in the `buildroot/output/images` directory. Create an `xz` archive with `xz -z rootfs.tar`.

### Use your image

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    arch: your-arch (i.e. riscv64)
    image-type: native
    image: path/to/image or URL
    renode-run: sh --help
```
