#!/command/with-contenv /usr/bin/bash
# shellcheck shell=bash
declare -r data_dir="${PAPERLESS_DATA_DIR:-/usr/src/paperless/data}"

# Use file locking to prevent simultaneous migrations
(
	flock 200
	# shellcheck disable=SC2164
	cd "${PAPERLESS_SRC_DIR}"
	python3 manage.py migrate --skip-checks --no-input
) 200>"${data_dir}/migration_lock"
