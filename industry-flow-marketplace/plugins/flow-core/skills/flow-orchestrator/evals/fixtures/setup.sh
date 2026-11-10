#!/bin/sh
# Створює git-мінірепо з фікстури в теці $1 і друкує SHA HEAD. Використання: sh setup.sh /tmp/minirepo
set -e
d="${1:?тека}"; mkdir -p "$d"; cp -r "$(dirname "$0")/minirepo/." "$d/"
cd "$d" && git init -q -b main && git add -A && git -c user.email=f@x -c user.name=fixture commit -qm fixture && git rev-parse HEAD
