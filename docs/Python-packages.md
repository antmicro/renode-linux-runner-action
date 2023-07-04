# Sideloading python packages

You can use the `python-packages` parameter to add the Python packages you require to test your software. This is the recommended option, as downloading packages manually in the emulated system is possible but can sometimes fail.

## Available options

The `python-packages` parameter accepts any packages from the PyPI repository and from public Git repositories. For packages from PyPI you can select additional requirements like minimum or exact version (see examples below), and for packages from Git repositories you can select a specific commit, branch or tag.

There is no need to manually add dependencies. The action will resolve them and install all required packages.

Examples:

```yaml
- uses: antmicro/renode-linux-runner-action@v1
  with:
    shared-dir: ./shared-dir
    renode-run: python --version
    python-packages: |
      git+https://github.com/antmicro/pyrav4l2.git@3c071a7
      pytest==5.3.0
      pyyaml>=5.3.1
```

## Collecting requirements

All dependencies for a respective architecture (e.g. riscv64) are resolved and downloaded automatically. If packages contain non-precompiled binaries, their sources will be downloaded.

The action creates an empty virtual environment where it tries to install packages in [`--dry-run`](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-dry-run) mode, and collects information about required dependencies. This feature is based on the [`--report`](https://pip.pypa.io/en/stable/reference/installation-report/) functionality added in `pip 23.0` (stable). The report details what packages and versions are needed.

The action then downloads all the necessary packages from their repositories, preferring binary versions, and adds the saved files to the registry, for later use when sideloading.

## Sideloading

After booting the emulated Linux and mounting the disks, you can install the Python packages. The action specifies all the downloaded files as argument. Dependency downloading is disabled and must remain so, otherwise `pip` will try to download them from the Internet, even though the required packages are provided as arguments.
