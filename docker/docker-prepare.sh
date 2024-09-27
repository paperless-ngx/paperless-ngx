#!/usr/bin/env bash

set -e

wait_for_postgres() {
	local attempt_num=1
	local -r max_attempts=5

	echo "Waiting for PostgreSQL to start..."

	local -r host="${PAPERLESS_DBHOST:-localhost}"
	local -r port="${PAPERLESS_DBPORT:-5432}"

	# Disable warning, host and port can't have spaces
	# shellcheck disable=SC2086
	while [ ! "$(pg_isready --host ${host} --port ${port})" ]; do

		if [ $attempt_num -eq $max_attempts ]; then
			echo "Unable to connect to database."
			exit 1
		else
			echo "Attempt $attempt_num failed! Trying again in 5 seconds..."
		fi

		attempt_num=$(("$attempt_num" + 1))
		sleep 5
	done
	echo "Connected to PostgreSQL"
}

wait_for_mariadb() {
	echo "Waiting for MariaDB to start..."

	local -r host="${PAPERLESS_DBHOST:=localhost}"
	local -r port="${PAPERLESS_DBPORT:=3306}"

	local attempt_num=1
	local -r max_attempts=5

	# Disable warning, host and port can't have spaces
	# shellcheck disable=SC2086
	while ! true > /dev/tcp/$host/$port; do

		if [ $attempt_num -eq $max_attempts ]; then
			echo "Unable to connect to database."
			exit 1
		else
			echo "Attempt $attempt_num failed! Trying again in 5 seconds..."

		fi

		attempt_num=$(("$attempt_num" + 1))
		sleep 5
	done
	echo "Connected to MariaDB"
}

wait_for_redis() {
	# We use a Python script to send the Redis ping
	# instead of installing redis-tools just for 1 thing
	if ! python3 /sbin/wait-for-redis.py; then
		exit 1
	fi
}

migrations() {
	(
		# flock is in place to prevent multiple containers from doing migrations
		# simultaneously. This also ensures that the db is ready when the command
		# of the current container starts.
		flock 200
		echo "Apply database migrations..."
		python3 manage.py migrate --skip-checks --no-input
	) 200>"${DATA_DIR}/migration_lock"
}

django_checks() {
	# Explicitly run the Django system checks
	echo "Running Django checks"
	python3 manage.py check
}

search_index() {

	local -r index_version=9
	local -r index_version_file=${DATA_DIR}/.index_version

	if [[ (! -f "${index_version_file}") || $(<"${index_version_file}") != "$index_version" ]]; then
		echo "Search index out of date. Updating..."
		python3 manage.py document_index reindex --no-progress-bar
		echo ${index_version} | tee "${index_version_file}" >/dev/null
	fi
}

superuser() {
	if [[ -n "${PAPERLESS_ADMIN_USER}" ]]; then
		python3 manage.py manage_superuser
	fi
}

do_work() {
	if [[ "${PAPERLESS_DBENGINE}" == "mariadb" ]]; then
		wait_for_mariadb
	elif [[ -n "${PAPERLESS_DBHOST}" ]]; then
		wait_for_postgres
	fi

	wait_for_redis

	migrations

	django_checks

	search_index

	superuser

}

do_work
