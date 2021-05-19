#!/usr/bin/env bash

wait_for_postgres() {
	attempt_num=1
	max_attempts=5

	echo "Waiting for PostgreSQL to start..."

	host="${PAPERLESS_DBHOST}"
	port="${PAPERLESS_DBPORT}"

	if [[ -z $port ]]; then
		port="5432"
	fi

	while ! </dev/tcp/$host/$port; do

		if [ $attempt_num -eq $max_attempts ]; then
			echo "Unable to connect to database."
			exit 1
		else
			echo "Attempt $attempt_num failed! Trying again in 5 seconds..."

		fi

		attempt_num=$(expr "$attempt_num" + 1)
		sleep 5
	done
}

migrations() {
	(
		# flock is in place to prevent multiple containers from doing migrations
		# simultaneously. This also ensures that the db is ready when the command
		# of the current container starts.
		flock 200
		echo "Apply database migrations..."
		python3 manage.py migrate
	) 200>/usr/src/paperless/data/migration_lock
}

search_index() {
	index_version=1
	index_version_file=/usr/src/paperless/data/.index_version

	if [[ (! -f "$index_version_file") || $(<$index_version_file) != "$index_version" ]]; then
		echo "Search index out of date. Updating..."
		python3 manage.py document_index reindex
		echo $index_version | tee $index_version_file >/dev/null
	fi
}

superuser() {
	if [[ -n "${PAPERLESS_ADMIN_USER}" ]]; then
		python3 manage.py manage_superuser
	fi
}

do_work() {
	if [[ -n "${PAPERLESS_DBHOST}" ]]; then
		wait_for_postgres
	fi

	migrations

	search_index

	superuser

}

do_work
