#!/usr/bin/env bash

SUPERVISORD_WORKING_DIR="${PAPERLESS_SUPERVISORD_WORKING_DIR:-$PWD}"
rootless_args=()
if [ "$(id -u)" == "$(id -u paperless)" ]; then
	rootless_args=(
		--user
		paperless
		--logfile
		"${SUPERVISORD_WORKING_DIR}/supervisord.log"
		--pidfile
		"${SUPERVISORD_WORKING_DIR}/supervisord.pid"
	)
fi

exec /usr/local/bin/supervisord -c /etc/supervisord.conf "${rootless_args[@]}"
