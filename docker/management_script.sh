#!/command/with-contenv /usr/bin/bash
# shellcheck shell=bash

set -e

cd "${PAPERLESS_SRC_DIR}"

if [[ -n "${USER_IS_NON_ROOT}" ]]; then
	python3 manage.py management_command "$@"
elif [[ $(id -u) == 0 ]]; then
	s6-setuidgid paperless python3 manage.py management_command "$@"
elif [[ $(id -un) == "paperless" ]]; then
	python3 manage.py management_command "$@"
else
	echo "Unknown user."
	exit 1
fi
