#!/usr/bin/bash

RUNNER="$1"

if [ -z "$1" ]; then
    RUNNER="run-locally"
fi

if ! command -v act &> /dev/null; then
    echo "You need nektos/act to run this action: https://github.com/nektos/act"
    exit
fi

act -j $RUNNER -e scripts/act-env.json --container-options "--privileged"
