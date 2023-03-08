# renode-linux-runner-action
Copyright (c) 2022 [Antmicro](https://www.antmicro.com)

renode-linux-runner-action is a GitHub Action that can run scripts on Linux inside the Renode emulation.

## Emulated system
The emulated system is based on the [Buildroot 2022.08.1](https://github.com/buildroot/buildroot/tree/2022.08.1) and it runs on the RISC-V/HiFive Unleashed platform in [Renode 1.13](https://github.com/renode/renode).
It contains the Linux kernel configured with the [`vivid` module](https://www.kernel.org/doc/html/latest/admin-guide/media/vivid.html) enabled and it has the following packages installed:
- Python 3.10.7
- pip 21.2.4
- v4l2-utils 1.22.1

## Parameters
- `shared-dir` - Path to the shared directory. Contents of this directory will be mounted in Renode. This is also the default path in which specified commands are run
- `renode-run` - A command or a list of commands to run in Renode

## Usage
Running a single command using the `renode-run` parameter:

```yaml
- uses: antmicro/renode-linux-runner-action@main
  with:
    shared-dir: ./shared-dir
    renode-run: command_to_run
```

Running multiple commands works the same way as the standard `run` command:

```yaml
- uses: antmicro/renode-linux-runner-action@main
  with:
    shared-dir: ./shared-dir
    renode-run: |
      command_to_run_1
      command_to_run_2
```

The [renode-linux-runner-test](.github/workflows/run_action.yml) workflow contains an example usage of this action.
