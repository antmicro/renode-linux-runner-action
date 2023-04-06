#!/usr/bin/bash

RUNNER="$1"

if [ -z "$1" ]; then
    RUNNER="default-configuration-test"
fi

if ! command -v act &> /dev/null; then
    echo "You need nektos/act to run this action: https://github.com/nektos/act"
    exit
fi

echo -e "{\n  \"act\": true\n}" > env.json

act -j $RUNNER -e env.json --container-options "--privileged"
rm env.json