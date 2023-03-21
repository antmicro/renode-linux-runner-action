#!/bin/bash

IMAGE_PATH=renode-linux-runner-docker
DOCKERFILE_PATH=$IMAGE_PATH/Dockerfile

mkdir $IMAGE_PATH/tests
cp -r -f tests/* $IMAGE_PATH/tests/

git clone https://github.com/antmicro/pyrav4l2.git $IMAGE_PATH/tests/pyrav4l2

docker build -t $IMAGE_PATH      \
             -f $DOCKERFILE_PATH \
              $IMAGE_PATH &&     \
docker run -v "$(pwd)"/$IMAGE_PATH/tests:/mnt/user         \
           $IMAGE_PATH                                     \
           "$(python3 extract_arguments.py renode-run)"    \
           "$(python3 extract_arguments.py devices)"

yes | rm -r -f $IMAGE_PATH/tests
