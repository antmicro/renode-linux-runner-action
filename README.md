# renode-linux-runner-action

Copyright (c) 2022 [Antmicro](https://www.antmicro.com)

renode-linux-runner-action is a GitHub Action that can run scripts on Linux inside the Renode emulation.

## Emulated system

The emulated system is based on the [Buildroot 2022.11.3](https://github.com/buildroot/buildroot/tree/2022.11.3) and it runs on the RISC-V/HiFive Unleashed platform in [Renode 1.13.3](https://github.com/renode/renode).
It contains the Linux kernel configured with some emulated devices enabled and it has the following packages installed:

- Python 3.10.8
- pip 21.2.4
- v4l2-utils 1.22.1
- libgpiod tools 1.6.3
- git 2.31.7

## Parameters

- `shared-dir` - Path to the shared directory. Contents of this directory will be mounted in Renode. The embedded Linux in Renode will start in this directory.
- `renode-run` - A command or a list of commands to run in Renode.
- `devices` - List of devices to add to the workflow. If not specified, the action will not install any devices.
- `image` - url of path to tar.xz archive with compiled embedded Linux image. If not specified, the action will use the default one. See releases for examples.
- `python-packages` - python packages from pypi library or git repository that will be sideloaded into emulated Linux.
- `repos` - git repositories that will be sideloaded into emulated Linux.

### Devices syntax

```yaml
- uses: antmicro/renode-linux-runner-action@main
  with:
    devices: |
      device1 param1 param2 param3 ...
      device2 param1 param2 param3 ...
      ...
```

### Available devices

- [`vivid`](https://www.kernel.org/doc/html/latest/admin-guide/media/vivid.html) - virtual device emulating a Video4Linux device
- [`gpio`](https://docs.kernel.org/admin-guide/gpio/gpio-mockup.html) - virtual device emulating GPIO lines. Optional parameters:
  - left bound: GPIO line numbers will start from this number
  - right bound: GPIO line numbers will end 1 before this number (for example, `gpio 0 64` will add 64 lines from 0 to 63)
- [`i2c`](https://www.kernel.org/doc/html/v5.10/i2c/i2c-stub.html) - virtual device emulating `I2C` bus. Optional parameter:
  - chip_addr: 7 bit address 0x03 to 0x77 of the chip that simulates the EEPROM device and provides read and write commands to it.

## Usage

Running a single command using the `renode-run` parameter:

```yaml
- uses: antmicro/renode-linux-runner-action@main
  with:
    shared-dir: ./shared-dir
    renode-run: command_to_run
    devices: vivid
```

Running multiple commands works the same way as the standard `run` command:

```yaml
- uses: antmicro/renode-linux-runner-action@main
  with:
    shared-dir: ./shared-dir
    renode-run: |
      command_to_run_1
      command_to_run_2
    devices: |
      vivid
      gpio
```

Multiple devices can also be specified this way.

The [renode-linux-runner-test](.github/workflows/build_and_test.yml) workflow contains an example usage of this action.
