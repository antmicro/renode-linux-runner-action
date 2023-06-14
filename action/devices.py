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
from enum import Enum

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
        assert (type(args[0]) is int and type(args[1]) is int) or (args[0].isdecimal() and args[1].isdecimal())

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


class DeviceType(Enum):
    """
    Style of the selected device list
    """
    STRING = 1
    YAML = 2


@dataclass
class DevicePrototype:
    """
    Device Prototype: it stores available devices that can be added.
    Fields:
    ----------
    params_list: list[str]
    command_action: list[Tuple[Action, int, list[str]]]
        defines number of parameters needed and the
        Action itself and their names (for yaml style list)
    """
    params_list: list[str]
    command_action: list[Tuple[Action, int, list[str]]]


@dataclass
class Device:
    """
    Device with parameters selected by the user

    Fields:
    ----------
    type: yaml or old multiline string parametes style
    name: name of the device
    prototype: DevicePrototype for this device
    args: dict with parameters (for yaml style)
          or list with paramaters (for old multiline string style)
    """
    type: DeviceType
    name: str
    prototype: DevicePrototype
    args: list[str] | Dict[str, str]


available_devices: Dict[str, DevicePrototype] = {
    "vivid": DevicePrototype(
                [],
                [(None, 0, [])],
            ),
    "gpio": DevicePrototype(
                ["ranges"],
                [(GPIO_SplitDevice, 2, ["left-bound", "right-bound"])],
            ),
    "i2c": DevicePrototype(
                ["chip_addr"],
                [(I2C_SetDeviceAddress, 1, ["chip-addr"])],
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

    try:

        devices_lines = []

        for line in devices.splitlines():
            if not line.startswith(" ") and ":" not in line and len(line.split()) == 1:
                devices_lines.append(f"{line}:")
            else:
                devices_lines.append(line)

        devices_dict: Dict[str, Dict[str, str] | None] = yaml.safe_load('\n'.join(devices_lines))

        if type(devices_dict) is not dict:
            raise yaml.YAMLError

        for device_name, device_args in devices_dict.items():
            if device_args is None:
                devices_dict[device_name] = {}

        for device_args in devices_dict.values():
            if type(device_args) is not dict:
                raise yaml.YAMLError

        device_type = DeviceType.YAML

    except yaml.YAMLError:

        devices_string = devices.splitlines()
        devices_dict: Dict[str, list[str]] = {}

        for device in devices_string:

            device = device.split()
            device_name = device[0]
            device_args = device[1:]

            devices_dict[device_name] = device_args

        device_type = DeviceType.STRING

    finally:

        for device_name, device_args in devices_dict.items():

            if device_name not in available_devices:
                print(f"WARNING: Device {device_name} not found")
                continue

            yield Device(
                device_type,
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
        args_pointer = 0
        vars_pointer = 0

        if device.type == DeviceType.STRING and len(device.args) != sum([i[1] for i in device.prototype.command_action]):
            print(f"WARNING: for device {device.name}, wrong number "
                  "of parameters, replaced with the default ones.")

            added_devices[f"device-{device.name}"] = new_device
            continue

        for params_hook in device.prototype.command_action:

            params_action = params_hook[0]
            params_list_len = params_hook[1]
            params_yaml_args = params_hook[2]

            if device.type == DeviceType.YAML and not all([arg in device.args.keys() for arg in params_yaml_args]):
                print(f"WARNING: for device {device.name}, wrong number "
                      "of parameters. Some parameters replaced with the default ones.")

                continue

            match device.type:
                case DeviceType.YAML:
                    params = [device.args[arg] for arg in params_yaml_args]
                case DeviceType.STRING:
                    params = device.args[args_pointer:args_pointer + params_list_len]

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
            args_pointer += params_list_len

        added_devices[f"device-{device.name}"] = new_device

    return added_devices
