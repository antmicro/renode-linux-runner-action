# Network

The emulated Linux system can access the Internet. This allows testing applications that require an Internet connection in addition to access to specific drivers. If an Internet connection is not needed it can also be disabled.

## How it works

The Renode emulator creates a [TAP](https://www.kernel.org/doc/html/latest/networking/tuntap.html) device on the host OS. Then, both the tap device and the emulated Ethernet module are connected to the virtual switch.

Network configuration:

* Local network: 172.16.0.0/16
* Host IP (offers packet forwarding): 172.16.0.1
* Emulated Linux IP: 172.16.0.2

## Disable network

If you don't need the Internet or don't have the proper permissions, you can disable the entire configuration with the `network: false` flag. You can continue to use options such as installing external Python packages, sharing directories or sideloading Git repositories.

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    shared-dirs: shared-dir
    renode-run: python --version
    network: false
```

## Known issues

Sometimes when cloning Git repositories the emulated system using an HTTPS connection, the download fails due to certificate errors or buffer overflows. If you have an idea how we can solve this problem, feel free to suggest it to us.
