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

from common import run_cmd, error
from images import shared_directories_action, shared_directories_actions

from typing import Dict

import os
import re
import json
import pexpect as px


# names of python packages that is used to install other packages
# they are insalled before regular packages and only if user
# choose at least one regular package
installation_dependencies = ["wheel"]


def get_package(child: px.spawn, arch: str, package_name: str) -> list[str]:
    """
    Download selected python package for specified platform.

    Parameters
    ----------
    child: px_spawn
        pexpect spawn with shell and python virtual environment enabled
    arch: str
        binaries architecture
    package_name: str
        package to download
    """

    child.sendline('')
    run_cmd(child, "(venv-dir) #", f"pip download {package_name} --platform=linux_{arch} --no-deps --progress-bar off --disable-pip-version-check")
    child.expect_exact('(venv-dir) #')

    # Removes strange ASCII control codes that appear during some 'pip download' runs.
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    output_str: str = ansi_escape.sub('', child.before)

    return [file.split(' ')[1].split('/')[1] for file in output_str.splitlines() if file.startswith('Saved')]


def get_packages(arch: str, packages: str) -> tuple[list[str], list[str]]:
    """
    Download all selected python packages and their dependencies
    for the specified architecture to sideload it later to emulated Linux.
    Parameters
    ----------
    arch: str
        binaries architecture
    packages: str
        raw string from github action, syntax defined in README.md
    """

    if packages.strip() == '':
        return [], []

    # python installation dependencies files ready to sideload
    downloaded_installation_dependencies = []

    # python packages files ready to sideload
    downloaded_packages = []

    child = px.spawn(f'sh -c "cd {os.getcwd()};exec /bin/sh"', encoding="utf-8", timeout=60)

    try:
        child.expect_exact('#')
        child.sendline('')

        run_cmd(child, "#", "mkdir -p pip")
        shared_directories_actions.append(
            shared_directories_action(
                f"{os.getcwd()}/pip",
                "/var/packages",
            )
        )

        run_cmd(child, "#", ". ./venv-dir/bin/activate")

        # Since the pip version in Ubuntu 22.04 is 22.0.2 and the first stable pip that supporting the --report flag is 23.0,
        # pip needs to be updated in venv. This workaround may be removed later.
        run_cmd(child, "(venv-dir) #", "pip -q install pip==23.0.1 --progress-bar off --disable-pip-version-check")

        for it, package in enumerate(installation_dependencies + packages.splitlines()):

            print(f"processing: {package}")

            # prepare report
            run_cmd(child, "(venv-dir) #", f"pip install -q {package} --dry-run --report report.json --progress-bar off --disable-pip-version-check")
            child.expect_exact("(venv-dir)")

            try:
                with open("report.json", "r", encoding="utf-8") as report_file:
                    report = json.loads(report_file.read())
            except FileNotFoundError:
                error("Could not load the report.json file, the error is most likely caused by a service outage")

            print(f"Packages to install: {len(report['install'])}")

            for dependency in report["install"]:

                dependency_name = dependency["metadata"]["name"] + "==" + dependency["metadata"]["version"] \
                    if "vcs_info" not in dependency["download_info"] \
                    else "git+" + dependency["download_info"]["url"] + "@" + dependency["download_info"]["vcs_info"]["commit_id"]
                if it < len(installation_dependencies):
                    downloaded_installation_dependencies += get_package(child, arch, dependency_name)
                else:
                    downloaded_packages += get_package(child, arch, dependency_name)

            child.sendline('')

        run_cmd(child, "(venv-dir) #", "deactivate")

        for package in downloaded_installation_dependencies + downloaded_packages:
            run_cmd(child, "#", f"mv {package} pip")

        child.expect_exact("#")
    except px.TIMEOUT:
        error("Timeout!")

    return downloaded_installation_dependencies, downloaded_packages


def add_repos(repos: str):
    """
    Download all selected git repos to sideload it later to emulated Linux.

    Parameters
    ----------
    repos: str
        raw string from github action, syntax defined in README.md
    """

    os.mkdir("repos")

    for repo in repos.splitlines():

        repo = repo.split(' ')
        repo, folder = repo[0], repo[1] if len(repo) > 1 else repo[0].split('/')[-1]

        print(f'Cloning {repo}' + f' to {folder}' if folder != '' else '')

        child = px.spawn(f'sh -c "cd {os.getcwd()};exec /bin/sh"', encoding="utf-8", timeout=10)

        try:
            child.expect_exact('#')
            child.sendline('')

            run_cmd(child, "#", f"git clone {repo} repos/{folder}")

            child.expect_exact('#', timeout=3600)
        except px.TIMEOUT:
            error("Timeout!")

        shared_directories_actions.append(
            shared_directories_action(
                f"{os.getcwd()}/repos",
                "/home",
            )
        )


def add_packages(arch: str, packages: str) -> Dict[str, str]:

    downloaded_installation_dependencies, downloaded_packages = get_packages(arch, packages)

    if downloaded_packages == []:
        return {}

    return {
        "python": {
            "PYTHON_INSTALL_DEPS": " ".join([f'/var/packages/{package}' for package in downloaded_installation_dependencies]),
            "PYTHON_PACKAGES": " ".join([f'/var/packages/{package}' for package in downloaded_packages]),
        }
    }
