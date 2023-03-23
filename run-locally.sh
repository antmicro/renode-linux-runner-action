#!/bin/bash

IMAGE_PATH=renode-linux-runner-docker
DOCKERFILE_PATH=$IMAGE_PATH/Dockerfile
SHARED_DIR="$(python3 extract_arguments.py shared-dir)"

mkdir $IMAGE_PATH/tests
cp -r -f tests/* $IMAGE_PATH/tests/

git clone https://github.com/antmicro/pyrav4l2.git $IMAGE_PATH/tests/pyrav4l2

docker build -t $IMAGE_PATH      \
             -f $DOCKERFILE_PATH \
              $IMAGE_PATH &&     \
docker run --cap-add=NET_ADMIN                             \
           --device /dev/net/tun:/dev/net/tun              \
           -v "$(pwd)"/$IMAGE_PATH/$SHARED_DIR:/mnt/user   \
           $IMAGE_PATH                                     \
           "$(python3 extract_arguments.py renode-run)"    \
           "$(python3 extract_arguments.py devices)"

yes | rm -r -f $IMAGE_PATH/tests
