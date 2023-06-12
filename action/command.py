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

from dataclasses import dataclass, field
from typing import Dict, Any
from types import NoneType

import re
import yaml
import dacite


@dataclass
class Command:
    """
    Stores a Shell command with custom configuration options
    """

    command: list[str] = field(default_factory=list)
    expect: list[str] = field(default_factory=list)
    timeout: int | NoneType = -1
    echo: bool | NoneType = None
    check_exit_code: bool | NoneType = None
    should_fail: bool | NoneType = None

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, item):
        setattr(self, key, item)

    def _apply_task_properties(self, keys: list[str], defaults: list[Any], task_values: list[Any]):

        for it, key in enumerate(keys):
            self[key] = task_values[it]       \
                if self[key] == defaults[it]  \
                else self[key]

    @staticmethod
    def load_from_dict(dict: Dict[str, Any] | str):

        if type(dict) == str:
            dict = {"command": [dict]}
        elif type(dict.get("command", None)) == str:
            dict["command"] = [dict["command"]]

        name_map = {name: name for name in dict.keys()} | {
            "check-exit-code": "check_exit_code",
            "should-fail": "should_fail",
        }

        return dacite.from_dict(data_class=Command, data={name_map[name]: value for name, value in dict.items()})

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
    shell: str
    requires: list[str] = field(default_factory=list)
    required_by: list[str] = field(default_factory=list)
    echo: bool = False
    timeout: int | NoneType = None
    fail_fast: bool = True
    check_exit_code: bool = True
    should_fail: bool = False
    sleep: int = 0
    disabled: bool = False
    commands: list[Command] = field(default_factory=list)
    vars: Dict[str, str] = field(default_factory=dict)

    def apply_vars(self, default_vars: Dict[str, str], override_variables: Dict[str, str]) -> None:
        """
        Resolve provided and global variables for each command.

        Parameters
        ----------
        default_vars : global variables dictionary
        """
        for command in self.commands:
            command.apply_vars(default_vars | self.vars | override_variables)

    @staticmethod
    def load_from_dict(dict: Dict[str, Any]) -> 'Task':

        name_map = {name: name for name in dict.keys()} | {
            "required-by": "required_by",
            "fail-fast": "fail_fast",
            "check-exit-code": "check_exit_code",
            "should-fail": "should_fail",
        }

        return dacite.from_dict(data_class=Task, data={name_map[name]: value for name, value in dict.items()})

    @staticmethod
    def load_from_yaml(yaml_string: str, config: Dict[str, Any] = {}) -> 'Task':
        """
        Construct the task from yaml.

        Parameters
        ----------
        yaml_string : string with yaml
        """

        obj: Dict[str, Any] = yaml.safe_load(yaml_string)
        if type(obj) is not dict:
            raise yaml.YAMLError

        obj.update(config)

        if "name" not in obj.keys():
            error("task description file must have at least 'name' field")

        obj["commands"] = [
            Command.load_from_dict(com)
            for com in obj.get("commands", [])
        ]

        return Task.load_from_dict(obj)

    @staticmethod
    def form_multiline_string(name: str, string: str, config: Dict[str, Any]) -> 'Task':
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

        return Task.load_from_dict(config)

    def enable(self, value: bool) -> None:
        self.disabled = not value
