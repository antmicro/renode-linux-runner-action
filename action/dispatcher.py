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
from command import Command, Task
from shell import Shell

from typing import Dict, TextIO
from time import sleep

import os
import sys
import igraph as ig


CR = r'\r'


class CommandDispatcher:
    """
    Stores Tasks and Shells, and provides functionalities to manage them
    """

    tasks: Dict[str, Task] = {}
    default_vars: Dict[str, str] = {}

    def __init__(self, board: str, global_vars: Dict[str, str], override_vars: Dict[str, Dict[str, str]]) -> None:
        """
        Parameters
        ----------
        global_vars: global variables
        override_vars: dictionary that stores different dictionaries for each task to override existing variables there
        """

        # FilteredStdout is used to remove \r characters from telnet output.
        # GitHub workflow log GUI interprets this sequence as newline.
        self.default_stdout = FilteredStdout(sys.stdout, CR, "")

        init_shells = {
            "host": ["sh", self.default_stdout, [
                Command(command=[], expect=["#"], timeout=5),
                Command(command=["screen -d -m renode --disable-xwt"], expect=["#"], timeout=5),
            ], 5, "#"],
            "renode": ["telnet 127.0.0.1 1234", self.default_stdout, [
                Command(command=[], expect=["(monitor)"], timeout=5),
                Command(command=["emulation CreateServerSocketTerminal 3456 \"term\""], expect=["(monitor)"], timeout=5),
            ], 3, r"\([\-a-zA-Z\d\s]+\)"],
            "target": ["telnet 127.0.0.1 3456", self.default_stdout, [], 0, "#"],
        }

        self.shells = {name: self.add_shell(name, *term) for (name, term) in init_shells.items()}

        self._add_default_vars(global_vars)
        self._load_tasks(board, override_vars)

    def _add_default_vars(self, vars: Dict[str, str]) -> None:
        self.default_vars.update(vars)

    def _load_tasks(self, board: str, override_vars: Dict[str, Dict[str, str]]) -> None:
        """
        Loads Tasks from YAML files stored in 'action/tasks' and 'action/user_tasks' directories and adds them to the `tasks` dict

        Parameters
        ----------
        override_vars: dictionary that stores different dictionaries for each task to override existing variables there
        """

        for directory in ["action/tasks", f"action/device/{board}/tasks", "action/user_tasks"]:
            if os.path.exists(directory):
                for path, _, files in os.walk(directory):
                    for f in files:
                        fp = os.path.join(path, f)
                        if fp.endswith((".yml", ".yaml")):
                            with open(fp) as task_file:
                                task = Task.load_from_yaml(task_file.read())
                                task.apply_vars(self.default_vars, override_vars.get(task.name, {}))
                                self.add_task(task)

    def _sort_tasks(self) -> None:
        """
        Prepares the order of execution of the Tasks by sorting them based on their dependencies.
        It takes into account deleted tasks and detects cyclic dependencies.
        """

        task_graph = ig.Graph(directed=True)

        for name in self.tasks:
            task_graph.add_vertex(name)

        for name, task in self.tasks.items():
            for dependency in task.requires:
                if dependency not in self.tasks.keys():
                    error(f"Dependency {dependency} for {name} not satisfied. No such task.")
                task_graph.add_edge(dependency, name)

            for dependency in task.before:
                if dependency in self.tasks.keys():
                    task_graph.add_edge(name, dependency)

        try:
            results = task_graph.topological_sorting(mode='out')
            sorted_tasks = [task_graph.vs[i]["name"] for i in results]
        except ig.InternalError:
            error("Cyclic dependencies detected. Aborting.")

        self.sorted_tasks = sorted_tasks

    def add_shell(self, name: str, spawn_cmd: str, stdout: TextIO, init_commands: list[Command], init_sleep: int, default_expect: str) -> Shell:
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
            name=name, shell=name, sleep=init_sleep, commands=init_commands
        ))

        return Shell(name, spawn_cmd=spawn_cmd, stdout=stdout, commands=[], default_expect=default_expect)

    def add_task(self, task: Task) -> None:
        """
        Adds a Task

        Parameters
        ----------
        task: The Task to add
        """

        if not task:
            return

        if task.shell != task.name:
            task.requires.append(task.shell)

        self.tasks[task.name] = task

    def enable_task(self, name: str, value: bool) -> None:
        self.tasks[name].enable(value)

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

        for task in [self.tasks[i] for i in self.sorted_tasks]:

            if task.disabled:
                continue

            exit_code = 0
            self.shells[task.shell].add_task(task)

            for return_code in self.shells[task.shell].run_step():
                if return_code != 0:
                    exit_code = return_code
                if exit_code != 0 and task.fail_fast:
                    sys.exit(exit_code)

            if exit_code != 0:
                error(f"Failed! Last exit code: {exit_code}")

            sleep(task.sleep)
