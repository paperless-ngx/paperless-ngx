#!/usr/bin/env bash

echo "Checking if we should start flower..."

if [[ -n  "${EDOC_ENABLE_FLOWER}" ]]; then
	# Small delay to allow celery to be up first
	echo "Starting flower in 5s"
	sleep 5
	celery --app edoc flower --conf=/usr/src/edoc/src/edoc/flowerconfig.py
else
	echo "Not starting flower"
fi
