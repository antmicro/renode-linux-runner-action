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

from os import walk as os_walk, path as os_path, makedirs as os_makedirs
from subprocess import run, DEVNULL, CalledProcessError
from sys import exit as sys_exit
from dataclasses import dataclass
from tarfile import open as tarfile_open
from shutil import copytree


CR = r'\r'


@dataclass
class shared_directories_action:
    host: str
    target: str


shared_directories_actions: list[shared_directories_action] = []


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


def burn_rootfs_image(user_directory: str, rootfs_size: str):
    """
    Creates a rootfs image to mount on the renode machine. Function copies all files specified by the user or required
    by other functions. When creating the image fails, it exits from the script with the same error code as failing command.

    Parameters
    ----------
    user_directory: str
        absolute path to action user catalog
    rootfs_size: str
        size of the rootfs in a format used by tools like truncate or auto to be calculated automatically
    """

    os_makedirs("images/rootfs")

    with tarfile_open("images/rootfs.tar") as tar:
        tar.extractall("images/rootfs")

    for dir in shared_directories_actions:
        os_makedirs(f"images/rootfs/{dir.target}", exist_ok=True)
        copytree(
            f"{user_directory}/{dir.host}",
            f"images/rootfs/{dir.target}",
            dirs_exist_ok=True
        )

    if rootfs_size == "auto":
        size = 0
        for path, _, files in os_walk("images/rootfs"):
            for f in files:
                fp = os_path.join(path, f)
                if not os_path.islink(fp):
                    size += os_path.getsize(fp)

        rootfs_size = f'{max(size * 2, 5 * 10**7)}'
    try:

        run(["truncate", "images/rootfs.img", "-s", rootfs_size], check=True)
        run(["mkfs.ext4", "-d", "images/rootfs", "images/rootfs.img"],
            check=True,
            stdout=DEVNULL)
    except CalledProcessError as e:
        sys_exit(e.returncode)
