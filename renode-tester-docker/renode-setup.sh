#!/bin/bash

truncate drive.img -s 100M
mkfs.ext4 -d "$1" drive.img > /dev/null

screen -d -m renode --disable-xwt
sleep 5
/renode-setup.expect
