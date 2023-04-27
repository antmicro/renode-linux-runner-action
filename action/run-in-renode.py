#!/usr/bin/env python3

# Copyright 2022 Antmicro Ltd.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pexpect import spawn as px_spawn, TIMEOUT as px_TIMEOUT
from subprocess import run, DEVNULL, CalledProcessError
from sys import stdout as sys_stdout, exit as sys_exit, argv as sys_argv
from time import sleep
from re import sub as re_sub, compile as re_compile
from dataclasses import dataclass
from typing import Any, Protocol
from string import hexdigits
from datetime import datetime
from json import loads as json_loads
from os import getcwd as os_getcwd

CR = r'\r'
HOST_INTERFACE = "eth0"
TAP_INTERFACE = "tap0"
RENODE_PIP_PACKAGES_DIR = "./pip_packages"


class FilteredStdout(object):
    """
    Stdout wrapper which replaces found pattern with 'replace' string.
    """
    def __init__(self, stream, pattern: str, replace: str):
        """
        Parameters
        ----------
        stream : stdout
        pattern : regex pattern to match and replace with 'replace'
        replace : string to replace found patterns
        """
        self.stream = stream
        self.pattern = re_compile(pattern)
        self.replace = replace

    def _write(self, string):
        self.stream.write(re_sub(self.pattern, self.replace, string))

    def __getattr__(self, attr):
        if attr == 'write':
            return self._write
        return getattr(self.stream, attr)


class Action(Protocol):
    """
    Called by the add_devices function. Used for some
    command when additional action is required.
    """

    """
    If Action requirements are not satisfied this error will be printed
    """
    error: str

    def __call__(self, *args: Any) -> str:
        raise NotImplementedError

    def check_args(self, *args: Any) -> bool:
        """
        Checks if the passed parameters are correct
        """
        raise NotImplementedError


class GPIO_SplitDevice:
    """
    Replaces the number of GPIO lines with multiple
    devices with a maximum of 32 lines each.
    """
    def __init__(self) -> None:
        self.error = "the first parameter must be lower than the second"

    def __call__(self, *args: str) -> str:

        assert len(args) >= 3, "not enough parameters passed"
        assert args[1].isdecimal() and args[2].isdecimal()

        command: str = args[0]
        l, r = int(args[1]), int(args[2])
        gpio_ranges_params = []

        while r - l > 32:
            gpio_ranges_params += [l, l + 32]
            l += 32

        if l != r:
            gpio_ranges_params += [l, r]

        return [command.split("=")[0] + '=' +
                ','.join([str(i) for i in gpio_ranges_params])]

    def check_args(self, args: list[str]) -> bool:
        return len(args) >= 2 and \
               args[0].isdecimal() and \
               args[1].isdecimal() and \
               int(args[0]) < int(args[1])


class I2C_SetDeviceAddress:
    """
    Set the simulated i2c device address that is connected
    to the i2c bus.
    """
    def __init__(self) -> None:
        self.error = "the address has to be hexadecimal number between 3 and 119"

    def __call__(self, *args: str) -> str:

        assert len(args) >= 2, "not enough parameters passed"

        command: str = args[0]
        addr = args[1]

        return [command.format(addr)]

    def check_args(self, args: list[str]) -> bool:
        return len(args) == 1 and \
               len(args[0]) >= 3 and \
               args[0][0:2] == '0x' and \
               all(c in hexdigits for c in args[0][2:]) and \
               3 <= int(args[0], 16) <= 119


@dataclass
class Device_Prototype:
    """
    Device Prototype: it stores available devices that can be added.
    Fields:
    ----------
    add_commands: list[str]
        commands that is needed to add device
    params: list[str]
        default parameters
    command_action: list[tuple[Action, int]]
        defines number of parameters needed and the
        Action itself
    """
    add_commands: list[str]
    params: list[str]
    command_action: list[tuple[Action, int]]


@dataclass
class Device:
    """
    Device Prototype: stores already added devices
    Fields:
    ----------
    add_commands: list[str]
        parsed commands to add the device
    """
    add_commands: list[str]


available_devices = {
    "vivid": Device_Prototype(
                ["modprobe vivid"],
                [],
                [(None, 0)],
            ),
    "gpio": Device_Prototype(
                ["modprobe gpio-mockup gpio_mockup_ranges={0},{1}"],
                ['0', '32'],
                [(GPIO_SplitDevice, 2)],
            ),
    "i2c": Device_Prototype(
                ["modprobe i2c-stub chip_addr={0}"],
                ["0x1C"],
                [(I2C_SetDeviceAddress, 1)],
    )
}


added_devices: list[Device] = []


default_packages = []


downloaded_packages = []


downloaded_repos = []


def add_devices(devices: str):
    """
    Parses arguments and commands, and adds devices to the
    `available devices` list
    Parameters
    ----------
    devices: str
        raw string from github action, syntax defined in README.md
    """

    for device in devices.splitlines():
        device = device.split()
        device_name = device[0]

        errors_occured = False

        if device_name in available_devices:
            device_proto = available_devices[device_name]

            new_device = Device([])

            args = device[1:]
            args_pointer = 0

            if len(device[1:]) != len(device_proto.params):
                print(f"WARNING: for device {device_name}, wrong number "
                      "of parameters, replaced with the default ones.")
                args = device_proto.params

            for it, command in enumerate(device_proto.add_commands):

                params_action: Action = device_proto.command_action[it][0]
                params_list_len: int = device_proto.command_action[it][1]

                if params_list_len == 0 or not params_action:
                    new_device.add_commands.append(command)
                    continue

                params_action = params_action()
                params = args[args_pointer:args_pointer + params_list_len]

                if params_action.check_args(params):
                    new_device.add_commands += params_action(command, *params)
                else:
                    print(f"ERROR: for device {device_name} {params_action.error}.")
                    errors_occured = True

                args_pointer += params_list_len

            if not errors_occured:
                added_devices.append(new_device)
        else:
            print(f"WARNING: Device {device_name} not found")


def get_package(child: px_spawn, package_name: str):
    """
    Download selected python package for riscv64 platform.

    Parameters
    ----------
    child: px_spawn
        pexpect spawn with shell and python virtual environment enabled
    package_name: str
        package to download
    """

    global downloaded_packages

    child.sendcontrol('c')
    run_cmd(child, "(venv-dir) #", f"pip download {package_name} --platform=linux_riscv64 --no-deps --progress-bar off --disable-pip-version-check")
    child.expect_exact('(venv-dir) #')

    # Removes strange ASCII control codes that appear during some 'pip download' runs.
    ansi_escape = re_compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    output_str: str = ansi_escape.sub('', child.before)

    downloaded_packages += [file.split(' ')[1] for file in output_str.splitlines() if file.startswith('Saved')]


def add_packages(packages: str):
    """
    Download all selected python packages and their dependencies
    for the riscv64 platform to sideload it later to emulated Linux.
    Parameters
    ----------
    packages: str
        raw string from github action, syntax defined in README.md
    """

    child = px_spawn(f'sh -c "cd {os_getcwd()};exec /bin/sh"', encoding="utf-8", timeout=60)

    try:
        child.expect_exact('#')
        child.sendline('')

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys_stdout, CR, "")

        run_cmd(child, "#", ". ./venv-dir/bin/activate")

        # Since the pip version in Ubuntu 22.04 is 22.0.2 and the first stable pip that supporting the --report flag is 23.0,
        # pip needs to be updated in venv. This workaround may be removed later.
        run_cmd(child, "(venv-dir) #", "pip -q install pip==23.0.1 --progress-bar off --disable-pip-version-check")

        for package in default_packages + packages.splitlines():

            print(f"processing: {package}")

            # prepare report
            run_cmd(child, "(venv-dir) #", f"pip install -q {package} --dry-run --report report.json --progress-bar off --disable-pip-version-check")
            child.expect_exact("(venv-dir)")

            with open("report.json", "r", encoding="utf-8") as report_file:
                report = json_loads(report_file.read())

            print(f"Packages to install: {len(report['install'])}")

            for dependency in report["install"]:

                dependency_name = dependency["metadata"]["name"] + "==" + dependency["metadata"]["version"] \
                    if "vcs_info" not in dependency["download_info"] \
                    else "git+" + dependency["download_info"]["url"] + "@" + dependency["download_info"]["vcs_info"]["commit_id"]
                get_package(child, dependency_name)

            child.sendcontrol("c")

        run_cmd(child, "(venv-dir) #", "deactivate")
        child.expect_exact("#")
    except px_TIMEOUT:
        print("Timeout!")
        sys_exit(1)


def add_repos(repos: str):
    """
    Download all selected git repos to sideload it later to emulated Linux.

    Parameters
    ----------
    repos: str
        raw string from github action, syntax defined in README.md
    """

    global downloaded_repos

    for repo in repos.splitlines():

        repo = repo.split(' ')
        repo, folder = repo[0], repo[1] if len(repo) > 1 else repo[0].split('/')[-1]

        print(f'Cloning {repo}' + f'to {folder}' if folder != '' else '')
        run(['git', 'clone', repo, folder],)

        downloaded_repos += [folder]


def create_shared_directory_image():
    """
    Creates an image of the shared directory that will be mounted into the Renode machine.
    When creating the image fails, it exits from the script with the same error code as failing command.
    """
    
    if len(downloaded_packages) > 0:
        run(["mkdir", "-p", f"/mnt/user/{RENODE_PIP_PACKAGES_DIR}"])

    for package in downloaded_packages:
        run(['mv', package, f"/mnt/user/{RENODE_PIP_PACKAGES_DIR}"])

    for repo in downloaded_repos:
        run(['mv', repo, "/mnt/user"])

    try:
        run(["truncate", "drive.img", "-s", "200M"], check=True)
        run(["mkfs.ext4", "-d", "/mnt/user", "drive.img"],
            check=True,
            stdout=DEVNULL)
    except CalledProcessError as e:
        sys_exit(e.returncode)


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


def run_cmd(child_process: px_spawn,
            output_to_expect: str,
            cmd_to_run: str,
            timeout: int = -1):
    """
    Wait for expected output in process spawned using pexpect and then run specified command

    Parameters
    ----------
    child_process : pexpect.spawn
        The process spawned using pexpect
    output_to_expect : str
        The output for that pexpect should wait before sending the specified command
    cmd_to_run : str
        The commands that should be run in child process after the expected output appears
    timeout : int
        Maximum time for waiting for expected output (default: -1 - which means inheriting timeout from specified child process)

    Raises
    ------
    pexpect.TIMEOUT
        If waiting for the expected output timeouts
    """

    child_process.expect_exact(output_to_expect, timeout=timeout)
    child_process.sendline(cmd_to_run)


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


def setup_renode():
    """
    Setups Renode instance and leaves it in the directory where the shared directory is mounted.
    It exits from the script with error code 1 if any of the commands timeouts or kernel panic is detected.
    """

    child = px_spawn("telnet 127.0.0.1 1234", encoding="utf-8", timeout=10)

    try:
        child.expect_exact("'^]'.")
        child.sendcontrol("c")

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys_stdout, CR, "")

        run_cmd(child, "(monitor)", "include @action/hifive.resc")

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

        # Preparing rootfs

        run_cmd(child, "#", "mount /dev/vda /mnt")
        run_cmd(child, "#", "cd /mnt")

        run_cmd(child, "#", "mount -t proc /proc proc/")
        run_cmd(child, "#", "mount -t sysfs /sys sys/")
        run_cmd(child, "#", "mount -o bind /dev dev/")
        run_cmd(child, "#", "mount -o bind /run run/")
        run_cmd(child, "#", "chroot /mnt /bin/sh")

        run_cmd(child, "#", "mkdir -p /sys/kernel/debug")
        run_cmd(child, "#", "mount -t debugfs nodev /sys/kernel/debug")

        # Extracting user data

        run_cmd(child, "#", "mount /dev/vdb /root")
        run_cmd(child, "#", "cd /root")

        # Network configuration
        # This configuration allows simulated linux to connect to
        # the tap0 interface created in the host

        run_cmd(child, "#", "ip addr add 172.16.0.2/16 dev eth0")
        run_cmd(child, "#", "ip route add default via 172.16.0.1")
        run_cmd(child, "#", 'echo "nameserver 1.1.1.1" >> /etc/resolv.conf')  # adds dns server address

        child.expect_exact("#")
    except px_TIMEOUT:
        print("Timeout!")
        sys_exit(1)


def setup_python():
    """
    Install previously downloaded python packages in emulated linux.
    """

    child = px_spawn("telnet 127.0.0.1 1234", encoding="utf-8", timeout=None)

    try:
        child.expect_exact("'^]'.")
        child.sendcontrol("c")

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys_stdout, CR, "")

        # pip configuration
        # Disable pip version checking. Pip runs very slowly in Renode without this setting.

        run_cmd(child, "#", "mkdir -p $HOME/.config/pip")
        run_cmd(child, "#", 'echo "[global]" >> $HOME/.config/pip/pip.conf')
        run_cmd(child, "#", 'echo "disable-pip-version-check = True" >> $HOME/.config/pip/pip.conf')

        run_cmd(child, "#", f"pip install {' '.join([f'{RENODE_PIP_PACKAGES_DIR}/{package}' for package in downloaded_packages])} --no-index --no-deps --no-build-isolation")

        run_cmd(child, "#", f"rm -r {RENODE_PIP_PACKAGES_DIR}/")

        child.expect_exact("#")
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
    if len(sys_argv) <= 1:
        print("Not enough input arguments")
        sys_exit(1)

    if len(sys_argv) >= 3 and sys_argv[2] != "":
        add_devices(sys_argv[2])

    if len(sys_argv) >= 4 and sys_argv[3] != "":
        add_packages(sys_argv[3])

    if len(sys_argv) >= 5 and sys_argv[4] != "":
        add_repos(sys_argv[4])

    create_shared_directory_image()
    run_renode_in_background()
    setup_network()
    setup_renode()
    if len(downloaded_packages) > 0:
        setup_python()
    run_cmds_in_renode(sys_argv[1])
