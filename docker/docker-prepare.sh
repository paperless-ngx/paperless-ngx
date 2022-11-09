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
	while [ ! "$(pg_isready -h ${host} -p ${port})" ]; do

		if [ $attempt_num -eq $max_attempts ]; then
			echo "Unable to connect to database."
			exit 1
		else
			echo "Attempt $attempt_num failed! Trying again in 5 seconds..."

		fi

		attempt_num=$(("$attempt_num" + 1))
		sleep 5
	done
}

wait_for_mariadb() {
	echo "Waiting for MariaDB to start..."

	local -r host="${PAPERLESS_DBHOST:=localhost}"
	local -r port="${PAPERLESS_DBPORT:=3306}"

	local attempt_num=1
	local -r max_attempts=5

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
		python3 manage.py migrate
	) 200>"${DATA_DIR}/migration_lock"
}

search_index() {

	local -r index_version=1
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

custom_container_init() {
	# Mostly borrowed from the LinuxServer.io base image
	# https://github.com/linuxserver/docker-baseimage-ubuntu/tree/bionic/root/etc/cont-init.d
	local -r custom_script_dir="/custom-cont-init.d"
	# Tamper checking.
	# Don't run files which are owned by anyone except root
	# Don't run files which are writeable by others
	if [ -d "${custom_script_dir}" ]; then
		if [ -n "$(/usr/bin/find "${custom_script_dir}" -maxdepth 1 ! -user root)" ]; then
			echo "**** Potential tampering with custom scripts detected ****"
			echo "**** The folder '${custom_script_dir}' must be owned by root ****"
			return 0
		fi
		if [ -n "$(/usr/bin/find "${custom_script_dir}" -maxdepth 1 -perm -o+w)" ]; then
			echo "**** The folder '${custom_script_dir}' or some of contents have write permissions for others, which is a security risk. ****"
			echo "**** Please review the permissions and their contents to make sure they are owned by root, and can only be modified by root. ****"
			return 0
		fi

		# Make sure custom init directory has files in it
		if [ -n "$(/bin/ls -A "${custom_script_dir}" 2>/dev/null)" ]; then
			echo "[custom-init] files found in ${custom_script_dir} executing"
			# Loop over files in the directory
			for SCRIPT in "${custom_script_dir}"/*; do
				NAME="$(basename "${SCRIPT}")"
				if [ -f "${SCRIPT}" ]; then
					echo "[custom-init] ${NAME}: executing..."
					/bin/bash "${SCRIPT}"
					echo "[custom-init] ${NAME}: exited $?"
				elif [ ! -f "${SCRIPT}" ]; then
					echo "[custom-init] ${NAME}: is not a file"
				fi
			done
		else
			echo "[custom-init] no custom files found exiting..."
		fi

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

	search_index

	superuser

	# Leave this last thing
	custom_container_init

}

do_work
