# Devices

The action's default images contain several devices not available in GitHub runners. These devices are not enabled by default. To enable a device simply add its name to the `devices` parameter along with optional parameters.

> **Warnings**
> Adding devices may not work properly with your own kernel. If you want to use your own kernel, make sure you have added the correct drivers.

## Adding device configs using YAML 

You can add device configurations with YAML. If you do not want to pass any parameters to the device, just add its name.

### Available devices

- [`vivid`](https://www.kernel.org/doc/html/latest/admin-guide/media/vivid.html) - a virtual device emulating a Video4Linux device
- [`gpio`](https://docs.kernel.org/admin-guide/gpio/gpio-mockup.html) - a virtual device emulating GPIO lines. Optional parameters:
  - `left-bound`: GPIO line numbers will start with this number
  - `right-bound`: GPIO line numbers will end one number before this number (for example, `gpio 0 64` will add 64 lines from 0 to 63)
- [`i2c`](https://www.kernel.org/doc/html/v5.10/i2c/i2c-stub.html) - a virtual device emulating an `I2C` bus. Optional parameter:
  - `chip-addr`: SMBus address between 0x03 and 0x77 to emulate a chip at.

### Example

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    renode-run: ls /dev
    devices: |
      gpio:
        left-bound: 16
        right-bound: 32
      vivid
```

## Adding devices using multiline strings

You can also add devices as individual lines in a multiline string. Then you need to list all parameters one by one (without parameter names).

For example:

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    renode-run: ls /dev
    devices: |
      gpio 16 32
      i2c 0x1C
      vivid
```