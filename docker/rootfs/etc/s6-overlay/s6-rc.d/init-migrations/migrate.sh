#!/command/with-contenv /usr/bin/bash
# shellcheck shell=bash
declare -r data_dir="${PAPERLESS_DATA_DIR:-/usr/src/paperless/data}"

# shellcheck disable=SC2164
cd "${PAPERLESS_SRC_DIR}"
exec s6-setlock -n "${data_dir}/migration_lock" python3 manage.py migrate --skip-checks --no-input
