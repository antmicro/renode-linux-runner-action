#!/usr/bin/env python3

# !!! Copyright is missing here

from sys import stdout as sys_stdout, exit as sys_exit, argv as sys_argv
from pexpect import spawn as px_spawn, TIMEOUT as px_TIMEOUT
from time import sleep


def run_cmd(child_process, output_to_expect, cmd_to_run, timeout=-1):
    """
    !!! Missing docstring
    """
    child_process.expect_exact(output_to_expect, timeout=timeout)
    child_process.sendline(cmd_to_run)


def setup_renode():
    """
    !!! Missing docstring
    """
    child = px_spawn(
        "telnet 127.0.0.1 1234",
        encoding="utf-8",
        timeout=10
    )

    try:
        child.expect_exact("'^]'.")
        child.logfile_read = sys_stdout

        run_cmd(child, """\
(monitor)
(hifive-unleashed)
(hifive-unleashed)
(hifive-unleashed)
(hifive-unleashed)
""", """\
include @/hifive.resc
machine LoadPlatformDescriptionFromString 'virtio: Storage.VirtIOBlockDevice @ sysbus 0x100d0000 { IRQ -> plic@50 }'
virtio LoadImage @drive.img
start
uart_connect sysbus.uart0
""")

        index = child.expect_exact(
            ["buildroot login:", "Kernel panic"],
            timeout=120
        )
        if index == 0:
            child.sendline("root")
        elif index == 1:
            sys_exit(1)

        run_cmd(child, """\
#
#
#
#
#
""", """\
dmesg -n 1
modprobe vivid
mkdir /mnt/drive
mount /dev/vda /mnt/drive
cd /mnt/drive
""")

        child.expect_exact("#")

    except px_TIMEOUT:
        print("Timeout!")
        sys_exit(1)


def run_cmds_in_renode(commands_to_run):
    """
    !!! Missing docstring
    """
    for cmd in commands_to_run.splitlines():
        print()
        print(f"Run in Renode: {cmd}")

        try:
            child = px_spawn("telnet 127.0.0.1 1234", encoding="utf-8")

            child.expect_exact("'^]'.", timeout=60)

            child.logfile_read = sys_stdout
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
    if len(sys_argv) <= 1:
        print("Not enough input arguments")
        sys_exit(1)

    setup_renode()
    run_cmds_in_renode(sys_argv[1])
