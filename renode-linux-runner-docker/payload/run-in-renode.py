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


def create_shared_directory_image(shared_directory: str):
    """
    Creates an image of the shared directory that will be mounted into the Renode machine.
    When creating the image fails, it exits from the script with the same error code as failing command.

    Parameters
    ----------
    shared_directory : str
        Path to the shared directory
    """

    try:
        run(["truncate", "drive.img", "-s", "100M"], check=True)
        run(["mkfs.ext4", "-d", shared_directory, "drive.img"],
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
        run_cmd(
            child, "(hifive-unleashed)",
            "machine LoadPlatformDescriptionFromString 'virtio: Storage.VirtIOBlockDevice @ sysbus 0x100d0000 { IRQ -> plic@50 }'"
        )
        run_cmd(child, "(hifive-unleashed)", "virtio LoadImage @drive.img")
        run_cmd(child, "(hifive-unleashed)", "start")
        run_cmd(child, "(hifive-unleashed)", "uart_connect sysbus.uart0")

        index = child.expect_exact(["buildroot login:", "Kernel panic"],
                                   timeout=120)
        if index == 0:
            child.sendline("root")
        elif index == 1:
            sys_exit(1)

        run_cmd(child, "#", "dmesg -n 1")
        run_cmd(child, "#", "modprobe vivid")
        run_cmd(child, "#", "mkdir /mnt/drive")
        run_cmd(child, "#", "mount /dev/vda /mnt/drive")
        run_cmd(child, "#", "cd /mnt/drive")

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

            sleep(5)
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
    if len(sys_argv) <= 2:
        print("Not enough input arguments")
        sys_exit(1)

    create_shared_directory_image(sys_argv[1])
    run_renode_in_background()
    setup_renode()
    run_cmds_in_renode(sys_argv[2])
