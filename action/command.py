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
from enum import Enum

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
    Stores command to the Terminal with configuration options
    """

    command: list[str] = field(default_factory=list)
    waitfor: list[str] = field(default_factory=list)
    timeout: int | NoneType = -1
    echo: bool | NoneType = None
    check_exit_code: bool = True

    def apply_vars(self, vars: Dict[str, str]):
        """
        Applies variables that were provided with section or are global variables.

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
class Section:
    """
    Section are blocks of commands that refers to one terminal and has
    one basic functionality, for example mount the filesystem or install
    package. The section also stores additional parameters like "echo" to print
    terminal output on the screen, etc.

    Sections can depend on other section and together creates dependency graph.
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
        Apply provided variables to each command.

        Parameters
        ----------
        default_vars : global variables dictionary
        """
        for command in self.commands:
            command.apply_vars(dict(self.vars, **default_vars))

    def load_from_yaml(yaml_string: str, additional_settings: Dict[str, Any] = {}):
        """
        Construct the section from yaml.

        Parameters
        ----------
        yaml_string : string with yaml
        """

        obj: Dict[str, Any] = yaml.safe_load(yaml_string)
        obj.update(additional_settings)

        if "name" not in obj.keys():
            error("section description file must have at least 'name' field")

        obj["commands"] = [
            Command(command=[com])
            if type(com) is str
            else dacite.from_dict(data_class=Command, data=com)
            for com in obj.get("commands", [])
        ]

        return dacite.from_dict(data_class=Section, data=obj)

    def form_multiline_string(name: str, string: str, config: Dict[str, Any]):
        """
        Construct the section from multiline string of commands.

        Parameters
        ----------
        name: identifier of the section
        string: multiline string with commands
        config: additional parameters to Section as dictionary
        """

        config["name"] = name
        config["commands"] = [
            Command(command=[com]) for com in string.splitlines()
        ]

        return dacite.from_dict(data_class=Section, data=config)


class Terminal:
    """
    Wrapper to pexpect.spawn with additional configuration.
    The class collects TerminalCommand objects and runs it sequentialy.
    """

    class TerminalCommandType(Enum):
        EXPECT = 0
        SENDLINE = 1

    @dataclass
    class TerminalCommand:
        """
        Simpler equalivent of command class to use internaly in Terminal.run() evaluator.
        It has different types: EXPECT for string or SENDLINE to terminal.
        """
        type: 'Terminal.TerminalCommandType'
        line: list[str]
        timeout: int | NoneType = None
        check_exit_code: bool = False
        echo: bool = False

    sys.stdout

    def __init__(self, name: str, spawn_point: str, stdout: TextIO, commands: list[Command]) -> None:
        """
        Parameters
        ----------
        name: terminal name
        spawn_point: the starting command that initializes terminal
        stdout: when command is executed in the echo mode terminal output is redirected to this TextIO
        commands: adds these initial commands to buffer
        """
        self.queue: queue.Queue['Terminal.TerminalCommand'] = queue.Queue()
        self.name: str = name
        self.spawn_point: str = spawn_point
        self.child: px.spawn = None
        self.last_option = 0
        self.stdout = stdout

        for com in commands:
            self.add_command(com)

    def spawn(self) -> None:
        """
        Start terminal
        """

        try:
            self.child = px.spawn(
                self.spawn_point,
                encoding="utf-8",
                timeout=None
            )

        except px.TIMEOUT:
            error("Timeout!")

    def add_command(self, command: Command) -> None:
        """
        Add command to buffer

        Parameters
        ----------
        command: command
        """

        if command.command != []:
            self.queue.put(
                Terminal.TerminalCommand(
                    Terminal.TerminalCommandType.SENDLINE,
                    command.command,
                    echo=command.echo
                )
            )

        self.queue.put(
            Terminal.TerminalCommand(
                Terminal.TerminalCommandType.EXPECT,
                command.waitfor,
                timeout=command.timeout,
                check_exit_code=command.check_exit_code,
                echo=command.echo)
        )

    def run(self) -> Iterator[int]:
        """
        Runs single command from buffer per iteration and optionally yields it's error code
        """

        if not self.child:
            self.spawn()

        while not self.queue.empty():

            command = self.queue.get()
            return_code = 0

            self.child.logfile_read = self.stdout if command.echo else None

            try:
                match command.type:
                    case Terminal.TerminalCommandType.EXPECT:
                        self.last_option = self.child.expect(command.line, timeout=command.timeout)

                        if self.name in ["host", "target"] and command.check_exit_code:
                            self.child.logfile_read = None
                            self.child.sendline("echo RESULT:${?}")
                            self.child.expect(r"RESULT:(\d+)", timeout=10)
                            return_code = int(self.child.match.group(1))
                            self.child.expect_exact("#", timeout=10)
                            self.child.logfile_read = self.stdout if command.echo else None

                    case Terminal.TerminalCommandType.SENDLINE:
                        self.child.sendline(command.line[self.last_option])
            except IndexError:
                error("Not enough options for last expect!")
            except px.TIMEOUT:
                error("Timeout!")

            yield return_code


class Interpreter:
    """
    Interpreter stores sctions and terminals and provides functionalities to manage them
    """

    sections: Dict[str, Section] = {}
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

        init_terminals = {
            "host": ["sh", self.default_stdout, [
                Command(command=[], waitfor=["#"], timeout=5),
                Command(command=["screen -d -m renode --disable-xwt"], waitfor=["#"], timeout=5),
            ], 5],
            "renode": ["telnet 127.0.0.1 1234", self.default_stdout, [
                Command(command=[], waitfor=["(monitor)"], timeout=5),
                Command(command=["emulation CreateServerSocketTerminal 3456 \"term\""], waitfor=["(monitor)"], timeout=5),
            ], 3],
            "target": ["telnet 127.0.0.1 3456", self.default_stdout, [], 0],
        }

        self.terminals = {name: self.add_terminal(name, *term) for (name, term) in init_terminals.items()}

        self._add_default_vars(vars)
        self._load_sections()

    def _add_default_vars(self, vars: Dict[str, str]) -> None:
        self.default_vars.update(vars)

    def _load_sections(self) -> None:
        """
        Loads sections from yaml files stored in action/sections and action/user_section catalog and add them to `sections` dict

        Parameters
        ----------
        vars: global variables
        """

        for catalog in ["sections", "user_sections"]:
            for path, _, files in os.walk(f"action/{catalog}"):
                for f in files:
                    fp = os.path.join(path, f)
                    if fp.endswith((".yml", ".yaml")):
                        print(f"Loading {fp}")
                        with open(fp) as section_file:
                            sec = Section.load_from_yaml(section_file.read())
                            sec.apply_vars(self.default_vars)
                            self.add_section(sec)

    def _sort_sections(self) -> None:
        """
        Prepares order of execution the sections.
        It takes into account deleted sections and detects cyclic dependencies.
        """

        section_graph = ig.Graph(directed=True)

        for name in self.sections:
            section_graph.add_vertex(name)

        for name, section in self.sections.items():
            for dependency in section.dependencies:
                if dependency not in self.sections.keys():
                    continue
                section_graph.add_edge(dependency, name)

        try:
            results = section_graph.topological_sorting(mode='out')
            sorted_sections = [section_graph.vs[i]["name"] for i in results]
        except ig.InternalError:
            error("Cyclic dependencies detected. Aborting.")

        self.sorted_sections = sorted_sections

    def add_terminal(self, name: str, spawn_point: str, stdout: TextIO, init_commands: list[Command], init_sleep: int) -> Terminal:
        """
        Adds new terminal. It also creates new section with the same name as Terminal. All sections that refers to that terminal
        has strict dependency to this section.

        Parameters
        ----------
        name: name of the terminal
        spawn_point: the linux command that spawns the terminal
        stdout: where output from the Terminal shoud be redirect
        init_commands: commands that initialize termial environment
        init_sleep: how much time the action should wait after initialize the terminal with it's commands
        """
        self.add_section(Section(
            name=name, refers=name, sleep=init_sleep, commands=init_commands
        ))

        return Terminal(name, spawn_point=spawn_point, stdout=stdout, commands=[])

    def add_section(self, section: Section) -> None:
        """
        Adds section

        Parameters
        ----------
        section: The Section to add
        """

        if not section:
            return

        if section.refers != section.name:
            section.dependencies.append(section.refers)

        self.sections[section.name] = section

    def delete_section(self, name: str) -> None:
        """
        Deletes section

        Parameters
        ----------
        name: name of the Section to delete
        """

        self.sections.pop(name)

    def evaluate(self) -> None:
        """
        Evaluate all loaded sections
        """

        self._sort_sections()
        print("Sections: ", self.sorted_sections)

        default_expect: Dict[str, list[str]] = {
            "host": ["#"],
            "target": ["#"],
            "renode": [r"\([\-a-zA-Z\d\s]+\)"],
        }

        for section in [self.sections[i] for i in self.sorted_sections]:

            exit_code = 0
            for command in section.commands:

                command.timeout = section.timeout  \
                    if command.timeout == -1       \
                    else command.timeout

                command.waitfor = default_expect[section.refers]  \
                    if command.waitfor == []                      \
                    else command.waitfor

                command.echo = section.echo  \
                    if not command.echo      \
                    else command.echo

                self.terminals[section.refers].add_command(command)

            for return_code in self.terminals[section.refers].run():
                if return_code != 0:
                    exit_code = return_code
                if exit_code != 0 and section.fail_fast:
                    sys.exit(exit_code)

            if exit_code != 0:
                error(f"Failed! Last exit code: {exit_code}")

            sleep(section.sleep)
