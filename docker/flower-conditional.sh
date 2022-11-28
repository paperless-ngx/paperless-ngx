#!/usr/bin/env bash

echo "Checking if we should start flower..."

if [[ -n  "${PAPERLESS_ENABLE_FLOWER}" ]]; then
	celery --app paperless flower
fi
