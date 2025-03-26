#!/usr/bin/env bash

set -e

cd /usr/src/edoc/src/
# This ensures environment is setup
# shellcheck disable=SC1091
source /sbin/env-from-file.sh

if [[ $(id -u) == 0 ]] ;
then
	gosu edoc python3 manage.py management_command "$@"
elif [[ $(id -un) == "edoc" ]] ;
then
	python3 manage.py management_command "$@"
else
	echo "Unknown user."
fi
