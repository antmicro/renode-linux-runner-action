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

from typing import Protocol, Any, Dict, Tuple, Iterator
from dataclasses import dataclass
from string import hexdigits

import yaml


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

        assert len(args) == 2, "not enough parameters passed"
        assert all(type(arg) is int for arg in args) or all(arg.isdecimal() for arg in args)

        l, r = int(args[0]), int(args[1])
        gpio_ranges_params = []

        while r - l > 32:
            gpio_ranges_params += [l, l + 32]
            l += 32

        if l != r:
            gpio_ranges_params += [l, r]

        return [','.join([str(i) for i in gpio_ranges_params])]

    def check_args(self, args: list[int | str]) -> bool:

        if len(args) != 2:
            return False

        if type(args[0]) is int and type(args[1]) is int:
            return args[0] < args[1]
        elif type(args[0]) is str and type(args[1]) is str:
            return args[0].isdecimal() and \
                   args[1].isdecimal() and \
                   int(args[0]) < int(args[1])
        else:
            return False


class I2C_SetDeviceAddress:
    """
    Set the simulated i2c device address that is connected
    to the i2c bus.
    """
    def __init__(self) -> None:
        self.error = "the address has to be hexadecimal number between 3 and 119"

    def __call__(self, args: list[str]) -> list[str]:

        assert len(args) >= 1, "not enough parameters passed"

        if type(args[0]) is int:
            return [format(args[0], "#x")]
        else:
            return [args[0]]

    def check_args(self, args: list[str]) -> bool:

        if len(args) != 1:
            return False

        if type(args[0]) is int:
            return 3 <= args[0] <= 119
        elif type(args[0]) is str:
            return len(args[0]) >= 3 and \
                   args[0][0:2] == '0x' and \
                   all(c in hexdigits for c in args[0][2:]) and \
                   3 <= int(args[0], 16) <= 119
        else:
            return False


@dataclass
class DevicePrototype:
    """
    Device Prototype: it stores available devices that can be added.
    Fields:
    ----------
    params_list: list[str]
    command_action: list[Tuple[Action, list[str]]]
        defines number of parameters needed and the
        Action itself and their names (for yaml style list)
    """
    params_list: list[str]
    command_action: list[Tuple[Action, list[str]]]


@dataclass
class Device:
    """
    Device with parameters selected by the user

    Fields:
    ----------
    name: name of the device
    prototype: DevicePrototype for this device
    args: dict with parameters (for yaml style)
          or list with paramaters (for old multiline string style)
    """
    name: str
    prototype: DevicePrototype
    args: Dict[str, str]


available_devices: Dict[str, DevicePrototype] = {
    "vivid": DevicePrototype(
                [],
                [(None, [])],
            ),
    "gpio": DevicePrototype(
                ["ranges"],
                [(GPIO_SplitDevice, ["left-bound", "right-bound"])],
            ),
    "i2c": DevicePrototype(
                ["chip_addr"],
                [(I2C_SetDeviceAddress, ["chip-addr"])],
    )
}


def get_device(devices: str) -> Iterator[Device]:
    """
    Returns the list of devices need to be added. It undersatds both yaml style list
    and multiline string style list.

    Parameters
    ----------
    devices: raw string from github action, syntax defined in README.md
    """

    def none_to_empty_dict(suspect: Dict[str, str] | None) -> Dict[str, str]:
        return suspect if suspect is not None else {}

    def add_colon_if_no_params(line: str) -> str:
        return line if ":" in line or len(line.split()) > 1 else f"{line}:"

    def device_available(device: str) -> bool:
        if device not in available_devices:
            print(f"WARNING: Device {device} not found")

        return device in available_devices

    devices_dict: Dict[str, Dict[str, str]] = {}

    try:
        devices_dict = {
            device: none_to_empty_dict(args) for device, args in yaml.load(
                str.join('\n', [add_colon_if_no_params(line) for line in devices.splitlines()]),
                Loader=yaml.FullLoader
            ).items() if device_available(device)
        }

        if any(type(args) is not dict for args in devices_dict.values()):
            raise yaml.YAMLError

    except (yaml.YAMLError, TypeError):

        for device in devices.splitlines():
            device = device.split()
            device_name = device[0]
            device_args = device[1:]

            if not device_available(device_name):
                continue

            device_prototype = available_devices[device_name]

            if len(device_args) != sum([len(i[1]) for i in device_prototype.command_action]):
                print(f"WARNING: for device {device_name}, wrong number "
                      "of parameters, replaced with the default ones.")

                devices_dict[device_name] = {}
                continue

            devices_dict[device_name] = {
                param: value for param, value in zip(
                    sum([args[1] for args in available_devices[device_name].command_action], start=[]),
                    device_args
                )
            }

    finally:

        for device_name, device_args in devices_dict.items():

            yield Device(
                device_name,
                available_devices[device_name],
                device_args,
            )


def add_devices(devices: str) -> Dict[str, Dict[str, str]]:
    """
    Parses arguments and commands, and adds devices to the
    `available devices` list
    Parameters
    ----------
    devices: raw string from github action, syntax defined in README.md
    """

    added_devices: Dict[str, Dict[str, str]] = {}

    for device in get_device(devices):

        new_device = {}
        vars_pointer = 0

        for params_hook in device.prototype.command_action:

            params_action = params_hook[0]
            params_list_len = len(params_hook[1])
            params = [device.args[arg] for arg in params_hook[1]]

            if params_list_len > 0 and params_action:

                params_action: Action = params_action()

                if not params_action.check_args(params):
                    error(f"ERROR: for device {device.name} {params_action.error}.")

                variable_list = params_action(params)
                variable_list_len = len(variable_list)

            else:
                variable_list = params
                variable_list_len = params_list_len

            new_device |= {device.prototype.params_list[i + vars_pointer].upper(): var for i, var in enumerate(variable_list)}
            vars_pointer += variable_list_len

        added_devices[f"device-{device.name}"] = new_device

    return added_devices
