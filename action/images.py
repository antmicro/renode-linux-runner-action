# Copyright 2022-2023 Antmicro Ltd.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from common import run_cmd, get_file, error

from subprocess import run, DEVNULL, CalledProcessError
from dataclasses import dataclass

import os
import re
import sys
import json
import shutil
import tarfile
import requests
import dockersave
import pexpect as px


@dataclass
class shared_directories_action:
    host: str
    target: str


shared_directories_actions: list[shared_directories_action] = []


def docker_image_parse(image: str) -> tuple[str]:

    result = re.match(r"^(.*)\/(.*):(.*)$", image)
    if result:
        return (result.group(1), result.group(2), result.group(3))

    result = re.match(r"^(.*)\/(.*)$", image)
    if result:
        return (result.group(1), result.group(2), "latest")

    result = re.match(r"^(.*):(.*)$", image)
    if result:
        return ("library", result.group(1), result.group(2))

    return ("library", image, "latest")


def prepare_shared_directories(shared_directories: str):
    """
    Creates list of directories to share

    Parameters
    ----------
    shared_directories: str
        list of directories that the user wanted to share with emulated Linux
    """

    global shared_directories_actions

    shared_directories: list[list[str]] = [directory.split(' ') for directory in shared_directories.split('\n')]

    for directory in shared_directories:
        if len(directory) == 1 and directory[0] != '':
            shared_directories_actions.append(
                shared_directories_action(
                    directory[0],
                    '/home',
                )
            )
        elif len(directory) > 1:
            shared_directories_actions.append(
                shared_directories_action(
                    directory[0],
                    directory[1],
                )
            )


def prepare_kernel_and_initramfs(kernel: str):
    """
    Get the kernel package (kernel + initramfs + bootlader + firmware) and extract kernel and device tree from cpio archive.

    Parameters
    ----------
    kernel: str
        path or URL to the kernel package
    """

    get_file(kernel, "kernel.tar.xz")

    os.makedirs("images")

    with tarfile.open("kernel.tar.xz") as tar:
        tar.extractall("images")

    child = px.spawn(f'sh -c "cd {os.getcwd()};exec /bin/sh"', encoding="utf-8", timeout=10)

    try:
        child.expect_exact('#')
        child.sendline('')

        run_cmd(child, "#", "mkdir -p images/initramfs")
        run_cmd(child, "#", "cd images/initramfs && cpio -iv < ../rootfs.cpio")
        run_cmd(child, "#", f"cd {os.getcwd()}")
        run_cmd(child, "#", "cp images/initramfs/boot/Image images")
        run_cmd(child, "#", "cp images/initramfs/boot/*.dtb images")
        run_cmd(child, "#", "rm -rf images/initramfs")

        child.expect_exact('#')
    except px.TIMEOUT:
        error("Timeout!")


def burn_rootfs_image(
        user_directory: str,
        image: str,
        arch: str,
        image_size: str,
        image_type: str):
    """
    Get the rootfs image, copy the user-selected data to the appropriate paths and creates a rootfs image to mount on the renode machine.
    Function copies all files specified by the user or required by other functions. When creating the image fails,
    it exits from the script with the same error code as failing command.

    Parameters
    ----------
    user_directory: str
        absolute path to action user catalog
    image:
        path or URL to the image
    image_size: str
        size of the rootfs in a format used by tools like truncate or auto to be calculated automatically
    image_type: str
        type of the image supported by action native or docker
    """

    os.makedirs("images/rootfs/home", exist_ok=True)

    if image_type == "native":
        get_file(image, "rootfs.tar.xz")
        image = "rootfs.tar.xz"
    elif image_type == "docker":
        library, image, tag = docker_image_parse(image)

        print("Preparing your docker image...")

        try:
            image_proto = dockersave.Image(
                    image=f"{library}/{image}",
                    tag=tag,
                    arch=arch
            )
        except StopIteration:
            print(f"This package is not available for the selected architecture: {arch}!")
            if arch == "riscv64":
                print("INFO: Currently, there are not many official Docker images available for the riscv64 architecture. Alternatives can often be found under 'riscv64/image:tag'.")
            exit(1)
        except requests.HTTPError:
            print(f"Image {library}/{image}:{tag} does not exist!")
            if tag == "latest":
                print("INFO: Perhaps there is no 'latest' tag for this image.")
            exit(1)

        image_proto.download(
            path=f"{os.getcwd()}/images",
            tar=True,
            rm=True,
            tarname="docker-image.tar"
        )

        with tarfile.open("images/docker-image.tar") as tar:
            tar.extractall("images/docker-image")

        with open('images/docker-image/manifest.json') as manifest_f:
            manifest = json.loads(manifest_f.read())

        selected_layer = manifest[0]['Layers'][0]

        image = f"images/docker-image/{selected_layer}"
    else:
        error(f"image type: {image_type} not found")

    with tarfile.open(image) as tar:
        tar.extractall("images/rootfs")

    for dir in shared_directories_actions:
        os.makedirs(f"images/rootfs/{dir.target}", exist_ok=True)
        shutil.copytree(
            f"{user_directory}/{dir.host}" if not dir.host.startswith('/') else dir.host,
            f"images/rootfs/{dir.target}",
            dirs_exist_ok=True
        )

    if image_size == "auto":
        size = 0
        for path, _, files in os.walk("images/rootfs"):
            for f in files:
                fp = os.path.join(path, f)
                if not os.path.islink(fp):
                    size += os.path.getsize(fp)

        image_size = f'{max(size * 2, 5 * 10**7)}'
    try:

        run(["truncate", "images/rootfs.img", "-s", image_size], check=True)
        run(["mkfs.ext4", "-d", "images/rootfs", "images/rootfs.img"],
            check=True,
            stdout=DEVNULL)
    except CalledProcessError as e:
        sys.exit(e.returncode)
