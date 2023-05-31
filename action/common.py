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

from urllib.parse import urlparse

import os
import re
import sys
import shutil
import requests
import pexpect as px


class FilteredStdout(object):
    """
    Stdout wrapper which replaces found pattern with 'replace' string.
    """
    def __init__(self, stream, pattern: str, replace: str):
        """
        Parameters
        ----------
        stream : stdout
        pattern : regex pattern to match and replace with 'replace'
        replace : string to replace found patterns
        """
        self.stream = stream
        self.pattern = re.compile(pattern)
        self.replace = replace

    def _write(self, string):
        self.stream.write(re.sub(self.pattern, self.replace, string))

    def __getattr__(self, attr):
        if attr == 'write':
            return self._write
        return getattr(self.stream, attr)


def error(msg: str):
    """
    Print message and exit with error code 1

    Parameters
    ----------
    msg : message to print
    """
    print(msg)
    sys.exit(1)


def run_cmd(child_process: px.spawn,
            output_to_expect: str,
            cmd_to_run: str,
            timeout: int = -1):
    """
    Wait for expected output in process spawned using pexpect and then run specified command

    Parameters
    ----------
    child_process : pexpect.spawn
        The process spawned using pexpect
    output_to_expect : str
        The output for that pexpect should wait before sending the specified command
    cmd_to_run : str
        The commands that should be run in child process after the expected output appears
    timeout : int
        Maximum time for waiting for expected output (default: -1 - which means inheriting timeout from specified child process)

    Raises
    ------
    pexpect.TIMEOUT
        If waiting for the expected output timeouts
    """

    child_process.expect_exact(output_to_expect, timeout=timeout)
    child_process.sendline(cmd_to_run)


def is_url(url):
    """
    Check if provided parameter is valid URL
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def get_file(path_or_url: str, target_path: str):
    """
    File downloader. Download the file from provide URL as filename
    or copy the file from path to filename.

    path_or_url: str
        URL or path to the file
    target_path: str
        target path where you want to copy the file
    """

    if target_path.find('/') != -1:
        os.makedirs("/".join(target_path.split("/")[:-1]), exist_ok=True)

    if os.path.isfile(path_or_url):
        shutil.move(path_or_url, target_path)
    elif is_url(path_or_url):
        try:
            r = requests.get(path_or_url)
            r.raise_for_status()
        except (requests.exceptions.MissingSchema, requests.RequestException) as error:
            error(f"Error while downloading {path_or_url} {error.response}")
        finally:
            with open(target_path, "wb") as fd:
                fd.write(r.content)
    else:
        error(f"Invalid path or URL: {path_or_url}")
