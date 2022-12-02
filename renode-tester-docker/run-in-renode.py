import sys
import pexpect
import time


def run_cmd(child_process, output_to_expect, cmd_to_run, timeout=-1):
    child_process.expect_exact(output_to_expect, timeout=timeout)
    child_process.sendline(cmd_to_run)


def setup_renode():
    child = pexpect.spawn("telnet 127.0.0.1 1234",
                          encoding="utf-8",
                          timeout=10)

    try:
        child.expect_exact("'^]'.")
        child.logfile_read = sys.stdout

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
            sys.exit(1)

        run_cmd(child, "#", "dmesg -n 1")
        run_cmd(child, "#", "modprobe vivid")
        run_cmd(child, "#", "mkdir /mnt/drive")
        run_cmd(child, "#", "mount /dev/vda /mnt/drive")
        run_cmd(child, "#", "cd /mnt/drive")

        child.expect_exact("#")
    except pexpect.TIMEOUT:
        print("Timeout!")
        sys.exit(1)


def run_cmds_in_renode(commands_to_run):
    for cmd in commands_to_run.splitlines():
        print()
        print(f"Run in Renode: {cmd}")

        try:
            child = pexpect.spawn("telnet 127.0.0.1 1234", encoding="utf-8")

            child.expect_exact("'^]'.", timeout=60)

            child.logfile_read = sys.stdout
            time.sleep(5)
            child.sendline(cmd)
            child.expect_exact("#", timeout=None)

            child.logfile_read = None
            child.sendline("echo $?")
            child.expect(r'\d+', timeout=10)
            exit_code = int(child.match.group(0))

            if exit_code != 0:
                sys.exit(exit_code)

        except pexpect.TIMEOUT:
            print("Timeout!")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("Not enough input arguments")
        sys.exit(1)

    setup_renode()
    run_cmds_in_renode(sys.argv[1])
