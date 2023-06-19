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

from common import error
from command import Command, Task

from typing import Iterator, TextIO
from time import sleep

import queue
import pexpect as px


class Shell:
    """
    pexpect.spawn wrapper with additional configuration.
    Collects Command objects and runs them sequentially.
    """

    def __init__(self, name: str, spawn_cmd: str, stdout: TextIO, commands: list[Command], default_expect: str) -> None:

        """
        Parameters
        ----------
        name: arbitrary Shell name
        spawn_cmd: the command that spawns the Shell process
        stdout: if the command is executed in echo mode, the output is redirected to this TextIO
        commands: adds these initial commands to queue
        """
        self.queue: queue.Queue[Command] = queue.Queue()
        self.name: str = name
        self.spawn_cmd: str = spawn_cmd
        self.child: px.spawn = None
        self.default_expect: str = default_expect
        self.last_option = 0
        self.stdout = stdout

        for com in commands:
            self._add_command(com)

    def _spawn(self) -> None:
        """
        Start the Shell
        """
        retries = 7

        while retries > 0:
            try:
                self.child = px.spawn(
                    self.spawn_cmd,
                    encoding="utf-8",
                    timeout=None
                )

            except px.EOF:
                retries -= 1
                sleep(1)
                continue
            except px.TIMEOUT:
                error("Timeout!")
            else:
                return

        error(f"Shell {self.name} is not responding")

    def _expect(self, command: Command) -> None:
        self.last_option = self.child.expect(command.expect, timeout=command.timeout)

    def _sendline(self, command: Command) -> None:
        if command.command == []:
            return

        self.child.sendline(command.command[self.last_option])

    def _add_command(self, command: Command) -> None:
        """
        Add command to queue

        Parameters
        ----------
        command: command
        """

        self.queue.put(command)

    def add_task(self, task: Task) -> None:

        for command in task.commands:

            command._apply_task_properties(
                ["timeout", "expect", "echo", "check_exit_code", "should_fail"],
                [-1, [], None, None, None],
                [task.timeout, [self.default_expect], task.echo, task.check_exit_code, task.should_fail]
            )

            self._add_command(command)

    def run_step(self) -> Iterator[int]:
        """
        Runs single command from queue per iteration and yields its error code
        """

        def return_code(command: Command):

            if self.name in ["renode"] or not command.check_exit_code:
                return 0

            self.child.logfile_read = None
            self.child.sendline("echo RESULT:${?}")
            self.child.expect(r"RESULT:(\d+)", timeout=10)
            ret = int(self.child.match.group(1))
            self.child.expect_exact(self.default_expect, timeout=10)
            self.child.logfile_read = self.stdout if command.echo else None

            if command.should_fail:
                ret = int(ret == 0)

            return ret

        if not self.child:
            self._spawn()

        while not self.queue.empty():

            command = self.queue.get()
            self.child.logfile_read = self.stdout if command.echo else None

            try:
                self._sendline(command)
                self._expect(command)

                yield return_code(command)

            except IndexError:
                error("Not enough options for last expect!")
            except px.EOF:
                error(f"Shell {self.name} is not responding")
            except px.TIMEOUT:
                error(f"Timeout! (shell={self.name}, cmd={''.join(command.command)})")
