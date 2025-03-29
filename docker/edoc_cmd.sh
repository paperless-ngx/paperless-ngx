#!/usr/bin/env bash

SUPERVISORD_WORKING_DIR="${EDOC_SUPERVISORD_WORKING_DIR:-$PWD}"
rootless_args=()
if [ "$(id -u)" == "$(id -u edoc)" ]; then
	rootless_args=(
		--user
		edoc
		--logfile
		"${SUPERVISORD_WORKING_DIR}/supervisord.log"
		--pidfile
		"${SUPERVISORD_WORKING_DIR}/supervisord.pid"
	)
fi

exec /usr/local/bin/supervisord -c /etc/supervisord.conf "${rootless_args[@]}"
