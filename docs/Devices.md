# Devices

This action offers several additional devices in the default images, which are not available in the GitHub runners, but are also not enabled by default. To enable a device simply add its name to the `devices` parameter along with optional parameters.

> **Warnings**
> Adding devices may not work properly with your own kernel. If you want to use your own kernel, check that you have added the correct drivers.

## Yaml style passing devices

You can pass device configurations for inclusion with a simple Yaml file. If you don't want to pass any parameters to the device simply type its name on the next line.

### Available devices

- [`vivid`](https://www.kernel.org/doc/html/latest/admin-guide/media/vivid.html) - virtual device emulating a Video4Linux device
- [`gpio`](https://docs.kernel.org/admin-guide/gpio/gpio-mockup.html) - virtual device emulating GPIO lines. Optional parameters:
  - left-bound: GPIO line numbers will start from this number
  - right-bound: GPIO line numbers will end 1 before this number (for example, `gpio 0 64` will add 64 lines from 0 to 63)
- [`i2c`](https://www.kernel.org/doc/html/v5.10/i2c/i2c-stub.html) - virtual device emulating `I2C` bus. Optional parameter:
  - chip-addr: 7 bit address 0x03 to 0x77 of the chip that simulates the EEPROM device and provides read and write commands to it.

### Example

```yaml
- uses: antmicro/renode-linux-runner-action@v0
  with:
    renode-run: ls /dev
    devices: |
      gpio:
        left-bound: 16
        right-bound: 32
      vivid
```

## Old multilne string passing devices

Devices can also be written out simply as new lines in the multiline string. Then you have to write out all the parameters one by one (without their names).

For example:

```yaml
- uses: antmicro/renode-linux-runner-action@v0
  with:
    renode-run: ls /dev
    devices: |
      gpio 16 32
      i2c 0x1C
      vivid
```

### Old devices syntax

```yaml
- uses: antmicro/renode-linux-runner-action@v0
  with:
    devices: |
      device1 param1 param2 param3 ...
      device2 param1 param2 param3 ...
      ...
```
