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

from common import run_cmd, FilteredStdout
from devices import add_devices, added_devices
from dependencies import add_packages, add_repos, downloaded_packages
from image import prepare_shared_directories, burn_rootfs_image

from pexpect import spawn as px_spawn, TIMEOUT as px_TIMEOUT
from subprocess import run, CalledProcessError
from sys import stdout as sys_stdout, exit as sys_exit, argv as sys_argv
from json import loads as json_loads, decoder as json_decoder
from datetime import datetime
from time import sleep


CR = r'\r'
HOST_INTERFACE = "eth0"
TAP_INTERFACE = "tap0"


def run_renode_in_background():
    """
    Runs Renode in background in the headless mode with telnet enabled on port 1234.
    When starting the Renode fails, it exits from the script with the proper error code.
    """

    try:
        run(["screen", "-d", "-m", "renode", "--disable-xwt"], check=True)
    except CalledProcessError as e:
        sys_exit(e.returncode)

    sleep(5)


def setup_network():
    """
    Setups host tap interface and connect it to Renode.
    """

    child = px_spawn("sh", encoding="utf-8", timeout=10)

    try:
        child.expect_exact('#')
        child.sendline('')

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys_stdout, CR, "")

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
    except px_TIMEOUT:
        print("Timeout!")
        sys_exit(1)


def setup_renode(network: bool):
    """
    Setups Renode instance and leaves it in the directory where the shared directory is mounted.
    It exits from the script with error code 1 if any of the commands timeouts or kernel panic is detected.

    Parameters:
    ----------
    network: bool
    If true it will configure network in emulated environment
    """

    run_renode_in_background()

    if network:
        setup_network()

    child = px_spawn("telnet 127.0.0.1 1234", encoding="utf-8", timeout=10)

    try:
        child.expect_exact("'^]'.")
        child.sendline('')

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys_stdout, CR, "")

        run_cmd(child, "(monitor)", "include @action/hifive.resc")

        if network:
            run_cmd(child, "(hifive-unleashed)", "connector Connect host.tap switch0")

        run_cmd(child, "(hifive-unleashed)", "start")
        run_cmd(child, "(hifive-unleashed)", "uart_connect sysbus.uart0")

        index = child.expect_exact(["buildroot login:", "Kernel panic"],
                                   timeout=240)
        if index == 0:
            child.sendline("root")
        elif index == 1:
            sys_exit(1)

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
        run_cmd(child, "#", "chroot /mnt /bin/sh")

        run_cmd(child, "#", "mkdir -p /sys/kernel/debug")
        run_cmd(child, "#", "mount -t debugfs nodev /sys/kernel/debug")

        run_cmd(child, "#", "cd /home")

        if len(downloaded_packages) > 0:
            setup_python(child)

        child.expect_exact("#")
    except px_TIMEOUT:
        print("Timeout!")
        sys_exit(1)


def setup_python(child: px_spawn):
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

        run_cmd(child, "#", f"pip install {' '.join([f'/var/packages/{package}' for package in downloaded_packages])} --no-index --no-deps --no-build-isolation")

        run_cmd(child, "#", "rm -r /var/packages", timeout=3600)
    except px_TIMEOUT:
        print("Timeout!")
        sys_exit(1)


def run_cmds_in_renode(commands_to_run: str):
    """
    Runs commands specified by user in the Renode instance.
    It exits the script with error code 1 if any of the commands timeouts.
    When any of the commands fails, it exits the script with the same error code as that command

    Parameters
    ----------
    commands_to_run: str
        The commands specified by the user that should be run in Renode.
        Every command must be placed as the new line of the string.
    """

    for cmd in commands_to_run.splitlines():
        print()
        print(f"Run in Renode: {cmd}")

        try:
            child = px_spawn("telnet 127.0.0.1 1234", encoding="utf-8")

            child.expect_exact("'^]'.", timeout=60)

            # FilteredStdout is used to remove \r characters from telnet output.
            # GitHub workflow log GUI interprets this sequence as newline.
            child.logfile_read = FilteredStdout(sys_stdout, CR, "")

            child.sendline(cmd)
            child.expect_exact("#", timeout=None)

            child.logfile_read = None
            child.sendline("echo $?")
            child.expect(r'\d+', timeout=10)
            exit_code = int(child.match.group(0))

            if exit_code != 0:
                sys_exit(exit_code)

        except px_TIMEOUT:
            print("Timeout!")
            sys_exit(1)


if __name__ == "__main__":
    if len(sys_argv) != 3:
        print("Wrong number of arguments")
        exit(1)

    try:
        args: dict[str, str] = json_loads(sys_argv[1])
    except json_decoder.JSONDecodeError:
        print(f"JSON decoder error for string: {sys_argv[1]}")
        exit(1)

    user_directory = sys_argv[2]

    prepare_shared_directories(args.get("shared-dir", "") + '\n' + args.get("shared-dirs", ""))
    add_devices(args.get("devices", ""))
    add_packages(args.get("python-packages", ""))
    add_repos(args.get("repos", ""))
    burn_rootfs_image(user_directory, args.get("rootfs-size", "auto"))

    renode_run = args.get("renode-run", None)
    assert renode_run, "renode-run argument is mandatory"

    setup_renode(args.get("network", "true") == "true")
    run_cmds_in_renode(renode_run)
