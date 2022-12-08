#!/bin/bash

# !!! Copyright is missing here

set -e

# TODO: Can this be included in run-in-renode's main so that the entrypoint is run-in-renode itself?

cd /github/workspace
truncate drive.img -s 100M
mkfs.ext4 -d "$1" drive.img > /dev/null

screen -d -m renode --disable-xwt
sleep 5
/run-in-renode.py "$2"
