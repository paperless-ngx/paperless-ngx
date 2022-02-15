#!/bin/bash

set -e

cd /usr/src/paperless/src/

if [[ $(id -u) == 0 ]] ;
then
  gosu paperless python3 manage.py management_command "$@"
elif [[ $(id -un) == "paperless" ]] ;
then
  python3 manage.py management_command "$@"
else
  echo "Unknown user."
fi
