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

from typing import Protocol, Any, Dict
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

    def __call__(self, args: Any) -> str:
        raise NotImplementedError

    def check_args(self, args: Any) -> bool:
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

    def __call__(self, args: list[str]) -> list[str]:

        assert len(args) >= 2, "not enough parameters passed"
        assert args[0].isdecimal() and args[1].isdecimal()

        l, r = int(args[0]), int(args[1])
        gpio_ranges_params = []

        while r - l > 32:
            gpio_ranges_params += [l, l + 32]
            l += 32

        if l != r:
            gpio_ranges_params += [l, r]

        return [','.join([str(i) for i in gpio_ranges_params])]

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

    def __call__(self, args: list[str]) -> list[str]:

        assert len(args) >= 1, "not enough parameters passed"

        return [args[0]]

    def check_args(self, args: list[str]) -> bool:
        return len(args) == 1 and \
               len(args[0]) >= 3 and \
               args[0][0:2] == '0x' and \
               all(c in hexdigits for c in args[0][2:]) and \
               3 <= int(args[0], 16) <= 119


@dataclass
class Device:
    """
    Device Prototype: it stores available devices that can be added.
    Fields:
    ----------
    params_list: list[str]
    command_action: list[tuple[Action, int]]
        defines number of parameters needed and the
        Action itself
    """
    params_list: list[str]
    command_action: list[tuple[Action, int]]


available_devices = {
    "vivid": Device(
                [],
                [(None, 0)],
            ),
    "gpio": Device(
                ["RANGES"],
                [(GPIO_SplitDevice, 2)],
            ),
    "i2c": Device(
                ["chip_addr"],
                [(I2C_SetDeviceAddress, 1)],
    )
}


def add_devices(devices: str) -> Dict[str, Dict[str, str]]:
    """
    Parses arguments and commands, and adds devices to the
    `available devices` list
    Parameters
    ----------
    devices: raw string from github action, syntax defined in README.md
    """

    added_devices: Dict[str, Dict[str, str]] = {}

    for device in devices.splitlines():
        device = device.split()
        device_name = device[0]

        if device_name not in available_devices:
            print(f"WARNING: Device {device_name} not found")
            continue

        device_proto = available_devices[device_name]

        new_device = {}

        args = device[1:]
        args_pointer = 0
        vars_pointer = 0

        if len(device[1:]) != sum([i[1] for i in device_proto.command_action]):
            print(f"WARNING: for device {device_name}, wrong number "
                  "of parameters, replaced with the default ones.")

            added_devices[f"device-{device_name}"] = new_device
            continue

        for params_hook in device_proto.command_action:

            params_action = params_hook[0]
            params_list_len = params_hook[1]
            params = args[args_pointer:args_pointer + params_list_len]

            if params_list_len > 0 and params_action:

                params_action: Action = params_action()

                if not params_action.check_args(params):
                    error(f"ERROR: for device {device_name} {params_action.error}.")

                variable_list = params_action(params)
                variable_list_len = len(variable_list)

            else:
                variable_list = params
                variable_list_len = params_list_len

            new_device |= {device_proto.params_list[i + vars_pointer]: var for i, var in enumerate(variable_list)}
            vars_pointer += variable_list_len
            args_pointer += params_list_len

        added_devices[f"device-{device_name}"] = new_device

    return added_devices
