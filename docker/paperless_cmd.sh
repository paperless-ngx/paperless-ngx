#!/usr/bin/env bash

rootless_args=()
if [ $(id -u) == $(id -u paperless) ]; then
	rootless_args=(
		--user
		paperless
		--logfile
		supervisord.log
		--pidfile
		supervisord.pid
	)
fi

/usr/local/bin/supervisord -c /etc/supervisord.conf ${rootless_args[@]}
