#!/usr/bin/env bash

echo "Checking if we should start flower..."

if [[ -n  "${PAPERLESS_ENABLE_FLOWER}" ]]; then
	# Small delay to allow celery to be up first
	echo "Starting flower in 5s"
	sleep 5
	celery --app paperless flower --conf=/usr/src/paperless/src/paperless/flowerconfig.py
else
	echo "Not starting flower"
fi
