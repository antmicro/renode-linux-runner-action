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

CR = r'\r'


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
    command_action: list[tuple[str, int]]
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


def create_shared_directory_image():
    """
    Creates an image of the shared directory that will be mounted into the Renode machine.
    When creating the image fails, it exits from the script with the same error code as failing command.
    """

    try:
        run(["truncate", "drive.img", "-s", "100M"], check=True)
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


def setup_renode():
    """
    Setups Renode instance and leaves it in the directory where the shared directory is mounted.
    It exits from the script with error code 1 if any of the commands timeouts or kernel panic is detected.
    """

    child = px_spawn("telnet 127.0.0.1 1234", encoding="utf-8", timeout=10)

    try:
        child.expect_exact("'^]'.")

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        child.logfile_read = FilteredStdout(sys_stdout, CR, "")

        run_cmd(child, "(monitor)", "include @/hifive.resc")

        run_cmd(child, "(hifive-unleashed)", "start")
        run_cmd(child, "(hifive-unleashed)", "uart_connect sysbus.uart0")

        index = child.expect_exact(["buildroot login:", "Kernel panic"],
                                   timeout=120)
        if index == 0:
            child.sendline("root")
        elif index == 1:
            sys_exit(1)

        # Adding devices

        run_cmd(child, "#", "dmesg -n 1")
        for device in added_devices:
            for command in device.add_commands:
                run_cmd(child, "#", command)

        # Extracting files from Virtio

        run_cmd(child, "#", "mkdir /mnt/drive")
        run_cmd(child, "#", "mount /dev/vda /mnt/drive")
        run_cmd(child, "#", "cd /mnt/drive")
        run_cmd(child, "#", "mkdir -p /sys/kernel/debug")
        run_cmd(child, "#", "mount -t debugfs nodev /sys/kernel/debug")

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

    if len(sys_argv) == 3 and sys_argv[2] != "":
        add_devices(sys_argv[2])

    create_shared_directory_image()
    run_renode_in_background()
    setup_renode()
    run_cmds_in_renode(sys_argv[1])
