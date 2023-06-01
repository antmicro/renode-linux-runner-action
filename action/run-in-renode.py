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

from common import run_cmd, FilteredStdout, get_file, error
from devices import add_devices, added_devices
from dependencies import add_packages, add_repos, downloaded_packages, downloaded_default_packages
from images import prepare_shared_directories, prepare_kernel_and_initramfs, burn_rootfs_image

from subprocess import run, CalledProcessError
from datetime import datetime
from time import sleep

import re
import sys
import json
import pexpect as px


CR = r'\r'
HOST_INTERFACE = "eth0"
TAP_INTERFACE = "tap0"
DEFAULT_IMAGE_PATH = "https://github.com/{}/releases/download/{}/image-{}-default.tar.xz"
DEFAULT_KERNEL_PATH = "https://github.com/{}/releases/download/{}/kernel-{}-{}.tar.xz"


default_boards = {
    "riscv64": "hifive_unleashed"
}


def run_renode_in_background():
    """
    Runs Renode in background in the headless mode with telnet enabled on port 1234.
    When starting the Renode fails, it exits from the script with the proper error code.
    """

    try:
        run(["screen", "-d", "-m", "renode", "--disable-xwt"], check=True)
    except CalledProcessError as e:
        sys.exit(e.returncode)

    sleep(5)


def get_machine_name(resc: str) -> str:
    """
    Get machine name from .resc file (used for waiting for command prompt in the Renode console)

    Parameters:
    ----------
    resc: str
        Path to resc file
    """

    with open(resc) as file:
        for line in file:
            match = re.match(r"^\s*\$name\s*\?=\s*\"(.*)\"\s*$", line)
            if match:
                return match.group(1)

    return None


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

    if arch not in default_boards:
        error("Architecture not supportted!")
        sys.exit(1)

    if board == "default":
        board = default_boards[arch]

    if board == "custom" and (resc == "default" or repl == "default"):
        print("You have to provide resc and repl for custom board")
        sys.exit(1)

    if resc != "default":
        get_file(resc, f"action/device/{board}/init.resc")

    if repl != "default":
        get_file(repl, f"action/device/{board}/platform.repl")

    return (arch, board)


def setup_network():
    """
    Setups host tap interface and connect it to Renode.
    """

    child = px.spawn("sh", encoding="utf-8", timeout=10)

    try:
        child.expect_exact('#')
        child.sendline('')

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys.stdout, CR, "")

        run_cmd(child, "#", "telnet 127.0.0.1 1234")

        run_cmd(child, "(monitor)", 'emulation CreateTap "tap0" "tap"')
        child.expect_exact("(monitor)")
        child.sendcontrol("]")
        run_cmd(child, "telnet>", 'quit')

        # This configuration allows simulated Linux to connect to the Internet.
        # Linux in Renode has the static IP 172.16.0.2/16.

        run_cmd(child, "#", f'ip addr add "172.16.0.1/16" dev {TAP_INTERFACE}')
        run_cmd(child, "#", f"ip link set up dev {TAP_INTERFACE}")
        run_cmd(child, "#", f"iptables -A FORWARD -i {TAP_INTERFACE} -o {HOST_INTERFACE} -j ACCEPT")
        run_cmd(child, "#", f"iptables -A FORWARD -i {HOST_INTERFACE} -o {TAP_INTERFACE} -m state --state RELATED,ESTABLISHED -j ACCEPT")
        run_cmd(child, "#", f"iptables -t nat -A POSTROUTING -o {HOST_INTERFACE} -j MASQUERADE")

        child.expect_exact("#")
    except px.TIMEOUT:
        error("Timeout!")


def setup_renode(board: str, network: bool):
    """
    Setups Renode instance and leaves it in the directory where the shared directory is mounted.
    It exits from the script with error code 1 if any of the commands timeouts or kernel panic is detected.

    Parameters:
    ----------
    network: bool
        If true it will configure network in emulated environment
    board:
        selected board, use to choose proper renode init script
    """

    run_renode_in_background()

    if network:
        setup_network()

    machine = get_machine_name(f"action/device/{board}/init.resc")

    if not machine:
        error("Machine name not found")

    child = px.spawn("telnet 127.0.0.1 1234", encoding="utf-8", timeout=10)

    try:
        child.expect_exact("'^]'.")
        child.sendline('')

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys.stdout, CR, "")

        run_cmd(child, "(monitor)", f"include @action/device/{board}/init.resc")

        if network:
            run_cmd(child, f"({machine})", "connector Connect host.tap switch0", timeout=240)

        run_cmd(child, f"({machine})", "start", timeout=240)
        run_cmd(child, f"({machine})", "uart_connect sysbus.uart0")

        index = child.expect(["buildroot login:", "Kernel panic", r"^#"], timeout=240)

        if index == 0:
            child.sendline("root")
        elif index == 1:
            sys.exit(1)
        elif index == 2:
            child.sendline('')

        # Adding devices

        run_cmd(child, "#", "dmesg -n 1")
        for device in added_devices:
            for command in device.add_commands:
                run_cmd(child, "#", command)

        # Set time

        now = datetime.now()

        run_cmd(child, "#", f'date -s "{now.strftime("%Y-%m-%d %H:%M:%S")}"')

        # Network configuration
        # This configuration allows simulated linux to connect to
        # the tap0 interface created in the host

        if network:
            run_cmd(child, "#", "ip addr add 172.16.0.2/16 dev eth0")
            run_cmd(child, "#", "ip route add default via 172.16.0.1")
            run_cmd(child, "#", 'echo "nameserver 1.1.1.1" >> /etc/resolv.conf')  # adds dns server address

        # Preparing rootfs

        run_cmd(child, "#", "mount /dev/vda /mnt")
        run_cmd(child, "#", "cd /mnt")

        run_cmd(child, "#", "mount -t proc /proc proc/")
        run_cmd(child, "#", "mount -t sysfs /sys sys/")
        run_cmd(child, "#", "mount -o bind /dev dev/")
        run_cmd(child, "#", "mount -o bind /run run/")
        run_cmd(child, "#", "mount -o bind /tmp tmp/")
        run_cmd(child, "#", "mkdir -p /mnt/sys/kernel/debug")
        run_cmd(child, "#", "mount -t debugfs nodev /mnt/sys/kernel/debug")

        run_cmd(child, "#", "chroot /mnt /bin/sh")
        run_cmd(child, "#", "cd /home")

        if len(downloaded_packages) > 0:
            setup_python(child)

        child.expect_exact("#")
    except px.TIMEOUT:
        print("Timeout!")
        sys.exit(1)


def setup_python(child: px.spawn):
    """
    Install previously downloaded python packages in emulated linux.

    Parameters
    ----------
    child: pexpect.spawn
    The running emulated Linux
    """

    try:
        # pip configuration
        # Disable pip version checking. Pip runs very slowly in Renode without this setting.

        run_cmd(child, "#", "mkdir -p $HOME/.config/pip")
        run_cmd(child, "#", 'echo "[global]" >> $HOME/.config/pip/pip.conf')
        run_cmd(child, "#", 'echo "disable-pip-version-check = True" >> $HOME/.config/pip/pip.conf')

        run_cmd(child, "#", f"pip install {' '.join([f'/var/packages/{package}' for package in downloaded_default_packages])} --no-index --no-deps --no-build-isolation --root-user-action=ignore")
        run_cmd(child, "#", f"pip install {' '.join([f'/var/packages/{package}' for package in downloaded_packages])} --no-index --no-deps --no-build-isolation --root-user-action=ignore", timeout=3600)

        run_cmd(child, "#", "rm -r /var/packages", timeout=3600)
    except px.TIMEOUT:
        error("Timeout!")


def run_cmds_in_renode(commands_to_run: str, fail_fast: bool):
    """
    Runs commands specified by user in the Renode instance.
    It exits the script with error code 1 if any of the commands timeouts.
    When any of the commands fails, it exits the script with the same error code as that command

    Parameters
    ----------
    commands_to_run: str
        The commands specified by the user that should be run in Renode.
        Every command must be placed as the new line of the string.
    fail_fast: bool
        If true, the first non-zero exit code is returned and the following commands are not executed.
        If false, the last non-zero exit code is returned after all commands are executed.
    """

    exit_code = 0

    for cmd in commands_to_run.splitlines():
        try:
            child = px.spawn("telnet 127.0.0.1 1234", encoding="utf-8")

            child.expect_exact("'^]'.", timeout=60)

            print(" ", end="")

            # FilteredStdout is used to remove \r characters from telnet output.
            # GitHub workflow log GUI interprets this sequence as newline.
            child.logfile_read = FilteredStdout(sys.stdout, CR, "")

            child.sendline(cmd)
            child.expect_exact("#", timeout=None)

            child.logfile_read = None
            child.sendline("echo $?")
            child.expect(r'\d+', timeout=10)
            exit_code_local = int(child.match.group(0))

            if exit_code_local != 0:
                exit_code = exit_code_local
                if fail_fast:
                    sys.exit(exit_code)

        except px.TIMEOUT:
            error("Timeout!")

    if not fail_fast and exit_code != 0:
        print(f"Failed! Last exit code: {exit_code}")
        sys.exit(exit_code)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Wrong number of arguments")
        exit(1)

    try:
        args: dict[str, str] = json.loads(sys.argv[1])
    except json.decoder.JSONDecodeError:
        print(f"JSON decoder error for string: {sys.argv[1]}")
        exit(1)

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

    image = args.get("image", "")
    if image.strip() == "":
        image = DEFAULT_IMAGE_PATH.format(action_repo, action_ref, arch)

    add_devices(args.get("devices", ""))
    prepare_kernel_and_initramfs(kernel)
    prepare_shared_directories(args.get("shared-dir", "") + '\n' + args.get("shared-dirs", ""))
    add_packages(arch, args.get("python-packages", ""))
    add_repos(args.get("repos", ""))
    burn_rootfs_image(
        user_directory,
        image,
        arch,
        args.get("rootfs-size", "auto"),
        args.get("image-type", "native")
    )

    renode_run = args.get("renode-run", None)
    assert renode_run, "renode-run argument is mandatory"

    setup_renode(board, args.get("network", "true") == "true")
    run_cmds_in_renode(renode_run, args.get("fail-fast", "true") == "true")
