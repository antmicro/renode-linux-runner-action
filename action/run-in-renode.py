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

from command import Task
from common import get_file, error, archs
from devices import add_devices
from dependencies import add_repos, add_packages
from images import prepare_shared_directories, prepare_kernel_and_initramfs, burn_rootfs_image
from dispatcher import CommandDispatcher

from datetime import datetime

import sys
import json
import yaml


DEFAULT_IMAGE_PATH = "https://github.com/{}/releases/download/{}/image-{}-default.tar.xz"
DEFAULT_KERNEL_PATH = "https://github.com/{}/releases/download/{}/kernel-{}-{}.tar.xz"


def configure_board(arch: str, board: str, resc: str, repl: str):
    """
    Set the appropriate board resc and repl

    Parameters:
    ----------
    arch: str
        Selected processor architecture
    board: str:
        selected board, use to choose proper renode init script
    resc: str
        custom resc: URL or path
    repl: str
        custom repl: URL or path
    """

    if arch not in archs:
        error("Architecture not supportted!")

    if board == "default":
        board = archs[arch].default_board

    if board == "custom" and (resc == "default" or repl == "default"):
        error("You have to provide resc and repl for custom board")

    if resc != "default":
        get_file(resc, f"action/device/{board}/init.resc")

    if repl != "default":
        get_file(repl, f"action/device/{board}/platform.repl")

    return (arch, board)


def test_task(test_task_str: str):

    additional_settings = {
        "name": "action_test",
        "shell": "target",
        "requires": ["chroot", "python"],
        "echo": True,
    }

    try:
        return Task.load_from_yaml(test_task_str, config=additional_settings)
    except yaml.YAMLError:
        return Task.form_multiline_string("action_test", test_task_str, config=additional_settings)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        error("Wrong number of arguments")

    try:
        args: dict[str, str] = json.loads(sys.argv[1])
    except json.decoder.JSONDecodeError:
        error(f"JSON decoder error for string: {sys.argv[1]}")

    user_directory = sys.argv[2]
    action_repo = sys.argv[3]
    action_ref = sys.argv[4]

    arch, board = configure_board(
        args.get("arch", "riscv64"),
        args.get("board", "default"),
        args.get("resc", "default"),
        args.get("repl", "default")
    )

    kernel = args.get("kernel", "")
    if kernel.strip() == "" and board == "custom":
        error("You have to provide custom kernel for custom board.")
    elif kernel.strip() == "":
        kernel = DEFAULT_KERNEL_PATH.format(action_repo, action_ref, arch, board)

    prepare_kernel_and_initramfs(kernel)

    prepare_shared_directories(args.get("shared-dir", "") + '\n' + args.get("shared-dirs", ""))

    devices = add_devices(args.get("devices", ""))
    python_packages = add_packages(arch, args.get("python-packages", ""))

    optional_tasks = devices | python_packages

    add_repos(args.get("repos", ""))

    image = args.get("image", "")
    if image.strip() == "":
        image = DEFAULT_IMAGE_PATH.format(action_repo, action_ref, arch)

    burn_rootfs_image(
        user_directory,
        image,
        arch,
        args.get("rootfs-size", "auto"),
        args.get("image-type", "native")
    )

    for it, custom_task in enumerate(args.get("tasks", "").splitlines()):
        get_file(custom_task, f"action/user_tasks/task{it}.yml")

    dispatcher = CommandDispatcher(board, {
        "NOW": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "BOARD": board
    }, optional_tasks)

    for task in optional_tasks:
        dispatcher.enable_task(task, True)

    if args.get("network", "true") != "true" or not archs[arch].network_available:
        for i in ["host", "renode", "target"]:
            dispatcher.enable_task(f"{i}_network", False)

    dispatcher.add_task(test_task(args.get("renode-run", "")))

    dispatcher.evaluate()
