#!/bin/bash

IMAGE_PATH=renode-linux-runner-docker
DOCKERFILE_PATH=$IMAGE_PATH/Dockerfile

git clone https://github.com/antmicro/pyrav4l2.git $IMAGE_PATH/pyrav4l2

mkdir $IMAGE_PATH/tests
cp -r -f tests/* $IMAGE_PATH/tests/

cp $DOCKERFILE_PATH "${DOCKERFILE_PATH}.old"

printf "\nRUN mkdir tests pyrav4l2      \
        \nCOPY tests/* ./tests/         \
        \nCOPY pyrav4l2/* ./pyrav4l2/   \
        \nRUN mv ./pyrav4l2/ ./tests/   \
        \n" >> $DOCKERFILE_PATH

docker build -t $IMAGE_PATH      \
             -f $DOCKERFILE_PATH \
              $IMAGE_PATH

docker run $IMAGE_PATH                 \
           "$(python3 extract_arguments.py shared-dir)" \
           "$(python3 extract_arguments.py renode-run)" \
           "$(python3 extract_arguments.py devices)"

mv "${DOCKERFILE_PATH}.old" $DOCKERFILE_PATH
yes | rm -r -f $IMAGE_PATH/tests $IMAGE_PATH/pyrav4l2
