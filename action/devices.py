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

from command import Section, Command

from typing import Protocol, Any
from dataclasses import dataclass
from string import hexdigits


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


def add_devices(devices: str) -> Section:
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

    return Section(
        "device",
        dependencies=[],
        refers="target",
        echo=True,
        commands=[Command(command=[command]) for commands in added_devices for command in commands.add_commands]
    )
