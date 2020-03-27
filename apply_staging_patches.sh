#!/bin/bash

set -ex

SCRIPTPATH=$(readlink -f "$0")
BASEDIR=$(dirname "$SCRIPTPATH")

pushd "$BASEDIR/wine-staging/patches"
./patchinstall.sh DESTDIR="$BASEDIR/wine" --all \
    -W user32-rawinput-mouse \
    -W user32-rawinput-mouse-experimental \
    -W user32-rawinput-nolegacy \
    -W user32-rawinput-hid
