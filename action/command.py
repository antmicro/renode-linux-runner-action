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

from common import FilteredStdout, error

from dataclasses import dataclass, field
from typing import Dict, Iterator, Any, TextIO
from types import NoneType
from time import sleep

import os
import re
import sys
import queue
import yaml
import dacite
import pexpect as px
import igraph as ig


CR = r'\r'


@dataclass
class Command:
    """
    Stores a Shell command with custom configuration options
    """

    command: list[str] = field(default_factory=list)
    waitfor: list[str] = field(default_factory=list)
    timeout: int | NoneType = -1
    echo: bool | NoneType = None
    check_exit_code: bool = True

    def apply_vars(self, vars: Dict[str, str]):
        """
        Resolves variables that were provided with task or are global variables.

        Parameters
        ----------
        vars : dictionary with pairs: name, value
        """

        variable_group = r"\$\{\{([\sa-zA-Z0-9_\-]*)\}\}"

        for it, command in enumerate(self.command):
            for match in re.finditer(variable_group, command):
                pattern = match[0]
                var_name = match[1]

                if var_name in vars:
                    self.command[it] = self.command[it].replace(pattern, vars[var_name])
                else:
                    error(f"Variable {var_name} not found!")


@dataclass
class Task:
    """
    A task is a block of commands that are performed on one shell and have
    one basic goal, for example mount the filesystem or install a
    package. It also stores additional parameters like "echo" to print
    shell output on the screen, etc.

    Tasks can depend on other tasks and together form a dependency graph.
    """

    name: str
    dependencies: list[str] = field(default_factory=list)
    refers: str = "virtual"
    echo: bool = False
    timeout: int | NoneType = None
    fail_fast: bool = True
    sleep: int = 0
    commands: list[Command] = field(default_factory=list)
    vars: Dict[str, str] = field(default_factory=dict)

    def apply_vars(self, default_vars: Dict[str, str]):
        """
        Resolve provided and global variables for each command.

        Parameters
        ----------
        default_vars : global variables dictionary
        """
        for command in self.commands:
            command.apply_vars(dict(self.vars, **default_vars))

    @staticmethod
    def load_from_yaml(yaml_string: str, additional_settings: Dict[str, Any] = {}):
        """
        Construct the task from yaml.

        Parameters
        ----------
        yaml_string : string with yaml
        """

        obj: Dict[str, Any] = yaml.safe_load(yaml_string)
        obj.update(additional_settings)

        if "name" not in obj.keys():
            error("task description file must have at least 'name' field")

        obj["commands"] = [
            Command(command=[com])
            if type(com) is str
            else dacite.from_dict(data_class=Command, data=com)
            for com in obj.get("commands", [])
        ]

        return dacite.from_dict(data_class=Task, data=obj)

    @staticmethod
    def form_multiline_string(name: str, string: str, config: Dict[str, Any]):
        """
        Construct the task from multiline string of commands.

        Parameters
        ----------
        name: identifier of the task
        string: multiline string with commands
        config: additional parameters to Task as dictionary
        """

        config["name"] = name
        config["commands"] = [
            Command(command=[com]) for com in string.splitlines()
        ]

        return dacite.from_dict(data_class=Task, data=config)


class Shell:
    """
    pexpect.spawn wrapper with additional configuration.
    Collects Command objects and runs them sequentially.
    """

    def __init__(self, name: str, spawn_cmd: str, stdout: TextIO, commands: list[Command]) -> None:
        """
        Parameters
        ----------
        name: shell name
        spawn_cmd: the starting command that initializes shell
        stdout: if the command is executed in echo mode, the output is redirected to this TextIO
        commands: adds these initial commands to buffer
        """
        self.queue: queue.Queue[Command] = queue.Queue()
        self.name: str = name
        self.spawn_cmd: str = spawn_cmd
        self.child: px.spawn = None
        self.last_option = 0
        self.stdout = stdout

        for com in commands:
            self.add_command(com)

    def spawn(self) -> None:
        """
        Start shell
        """

        try:
            self.child = px.spawn(
                self.spawn_cmd,
                encoding="utf-8",
                timeout=None
            )

        except px.TIMEOUT:
            error("Timeout!")

    def expect(self, command: Command) -> None:
        self.last_option = self.child.expect(command.waitfor, timeout=command.timeout)

    def sendline(self, command: Command) -> None:
        if command.command == []:
            return

        self.child.sendline(command.command[self.last_option])

    def add_command(self, command: Command) -> None:
        """
        Add command to buffer

        Parameters
        ----------
        command: command
        """

        self.queue.put(command)

    def run_step(self) -> Iterator[int]:
        """
        Runs single command from buffer per iteration and optionally yields it's error code
        """

        def return_code(command: Command):

            if self.name in ["renode"] or not command.check_exit_code:
                return 0

            self.child.logfile_read = None
            self.child.sendline("echo RESULT:${?}")
            self.child.expect(r"RESULT:(\d+)", timeout=10)
            ret = int(self.child.match.group(1))
            self.child.expect_exact("#", timeout=10)
            self.child.logfile_read = self.stdout if command.echo else None

            return ret

        if not self.child:
            self.spawn()

        while not self.queue.empty():

            command = self.queue.get()
            self.child.logfile_read = self.stdout if command.echo else None

            try:
                self.sendline(command)
                self.expect(command)

                yield return_code(command)

            except IndexError:
                error("Not enough options for last expect!")
            except px.TIMEOUT:
                error("Timeout!")


class Interpreter:
    """
    Stores Tasks and Shells, and provides functionalities to manage them
    """

    tasks: Dict[str, Task] = {}
    default_vars: Dict[str, str] = {}

    def __init__(self, vars: Dict[str, str]) -> None:
        """
        Parameters
        ----------
        vars: global variables
        """

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        self.default_stdout = FilteredStdout(sys.stdout, CR, "")

        init_shells = {
            "host": ["sh", self.default_stdout, [
                Command(command=[], waitfor=["#"], timeout=5),
                Command(command=["screen -d -m renode --disable-xwt"], waitfor=["#"], timeout=5),
            ], 7],
            "renode": ["telnet 127.0.0.1 1234", self.default_stdout, [
                Command(command=[], waitfor=["(monitor)"], timeout=5),
                Command(command=["emulation CreateServerSocketTerminal 3456 \"term\""], waitfor=["(monitor)"], timeout=5),
            ], 5],
            "target": ["telnet 127.0.0.1 3456", self.default_stdout, [], 0],
        }

        self.shells = {name: self.add_shell(name, *term) for (name, term) in init_shells.items()}

        self._add_default_vars(vars)
        self._load_tasks()

    def _add_default_vars(self, vars: Dict[str, str]) -> None:
        self.default_vars.update(vars)

    def _load_tasks(self) -> None:
        """
        Loads Tasks from YAML files stored in 'action/tasks' and 'action/user_tasks' directories and adds them to the `tasks` dict

        Parameters
        ----------
        vars: global variables
        """

        for directory in ["tasks", "user_tasks"]:
            for path, _, files in os.walk(f"action/{directory}"):
                for f in files:
                    fp = os.path.join(path, f)
                    if fp.endswith((".yml", ".yaml")):
                        print(f"Loading {fp}")
                        with open(fp) as task_file:
                            sec = Task.load_from_yaml(task_file.read())
                            sec.apply_vars(self.default_vars)
                            self.add_task(sec)

    def _sort_tasks(self) -> None:
        """
        Prepares the order of execution of the Tasks by sorting them based on their dependencies.
        It takes into account deleted tasks and detects cyclic dependencies.
        """

        task_graph = ig.Graph(directed=True)

        for name in self.tasks:
            task_graph.add_vertex(name)

        for name, task in self.tasks.items():
            for dependency in task.dependencies:
                if dependency not in self.tasks.keys():
                    continue
                task_graph.add_edge(dependency, name)

        try:
            results = task_graph.topological_sorting(mode='out')
            sorted_tasks = [task_graph.vs[i]["name"] for i in results]
        except ig.InternalError:
            error("Cyclic dependencies detected. Aborting.")

        self.sorted_tasks = sorted_tasks

    def add_shell(self, name: str, spawn_cmd: str, stdout: TextIO, init_commands: list[Command], init_sleep: int) -> Shell:
        """
        Adds a new Shell. It also creates a new Task with the same name as the Shell. All Tasks that refers to that Shell
        have a strict dependency on this Task.

        Parameters
        ----------
        name: name of the Shell
        spawn_cmd: the Linux command that spawns the Shell
        stdout: where to redirect the output from the Shell
        init_commands: commands that initialize the Shell environment
        init_sleep: how much time should pass between initializing the Shell and executing its commands
        """
        self.add_task(Task(
            name=name, refers=name, sleep=init_sleep, commands=init_commands
        ))

        return Shell(name, spawn_cmd=spawn_cmd, stdout=stdout, commands=[])

    def add_task(self, task: Task) -> None:
        """
        Adds a Task

        Parameters
        ----------
        task: The Task to add
        """

        if not task:
            return

        if task.refers != task.name:
            task.dependencies.append(task.refers)

        self.tasks[task.name] = task

    def delete_task(self, name: str) -> None:
        """
        Deletes task

        Parameters
        ----------
        name: name of the Task to delete
        """

        self.tasks.pop(name)

    def evaluate(self) -> None:
        """
        Evaluates all added Tasks
        """

        self._sort_tasks()
        print("Tasks: ", self.sorted_tasks)

        default_expect: Dict[str, list[str]] = {
            "host": ["#"],
            "target": ["#"],
            "renode": [r"\([\-a-zA-Z\d\s]+\)"],
        }

        for task in [self.tasks[i] for i in self.sorted_tasks]:

            exit_code = 0
            for command in task.commands:

                command.timeout = task.timeout  \
                    if command.timeout == -1    \
                    else command.timeout

                command.waitfor = default_expect[task.refers]  \
                    if command.waitfor == []                   \
                    else command.waitfor

                command.echo = task.echo  \
                    if not command.echo   \
                    else command.echo

                self.shells[task.refers].add_command(command)

            for return_code in self.shells[task.refers].run_step():
                if return_code != 0:
                    exit_code = return_code
                if exit_code != 0 and task.fail_fast:
                    sys.exit(exit_code)

            if exit_code != 0:
                error(f"Failed! Last exit code: {exit_code}")

            sleep(task.sleep)
