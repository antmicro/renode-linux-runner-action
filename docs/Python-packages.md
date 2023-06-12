# Python packages sideloading

You can use the `python-packages` parameter to add the Python packages you require to test your software. This is the recommended option, as downloading packages manually in the emulated system is possible, but can sometimes fail.

## Available options

The `python-packages` parameter accepts any packages from the PyPI repository and from public Git repositories. For packages from PyPI you can select additional requirements like minimum or exact version (see examples below), and for packages from Git repositories you can select a specific commit, branch or tag.

There is no need to manually add dependencies. The action will resolve them and install all required packages by itself.

Examples:

```yaml
- uses: antmicro/renode-linux-runner-action@v0
  with:
    shared-dir: ./shared-dir
    renode-run: python --version
    python-packages: |
      git+https://github.com/antmicro/pyrav4l2.git@3c071a7
      pytest==5.3.0
      pyyaml>=5.3.1
```

## Collecting requirements

All dependencies for the appropriate architecture (e.g. riscv64) are resolved and downloaded automatically. If the packages contain binaries which are not precompiled, their sources will be downloaded.

The action creates an empty virtual environment where it tries to install packages in [`--dry-run`](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-dry-run) mode, and then collects the requirements of what additional dependencies were needed. The whole thing is based on the [`--report`](https://pip.pypa.io/en/stable/reference/installation-report/) functionality, which in the stable version was added in `pip 23.0`. From the report you can read exactly what packages were needed and in what versions.

The action then downloads all the needed packages from the repositories, preferring the binary versions, and adds the saved files to the registry, which it will use later when sideloading.

## Sideloading

After booting the emulated Linux and mounting the disks, it's time to install the Python packages. The only thing the action does is specify all the downloaded files as argument. Dependency downloading is disabled and must remain so, otherwise `pip` will try to download them from the Internet, even though the required package is provided as one of the arguments.
