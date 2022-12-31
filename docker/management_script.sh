#!/usr/bin/env bash

set -e

cd /usr/src/paperless/src/
# This ensures environment is setup
# shellcheck disable=SC1091
source /sbin/env-from-file.sh

if [[ $(id -u) == 0 ]] ;
then
	gosu paperless python3 manage.py management_command "$@"
elif [[ $(id -un) == "paperless" ]] ;
then
	python3 manage.py management_command "$@"
else
	echo "Unknown user."
fi
