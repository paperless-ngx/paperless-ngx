#!/usr/bin/env bash

set -e

# Adapted from:
# https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh
# usage: file_env VAR
#    ie: file_env 'XYZ_DB_PASSWORD' will allow for "$XYZ_DB_PASSWORD_FILE" to
# fill in the value of "$XYZ_DB_PASSWORD" from a file, especially for Docker's
# secrets feature
file_env() {
	local var="$1"
	local fileVar="${var}_FILE"

	# Basic validation
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		echo >&2 "error: both $var and $fileVar are set (but are exclusive)"
		exit 1
	fi

	# Only export var if the _FILE exists
	if [ "${!fileVar:-}" ]; then
		# And the file exists
		if [[ -f ${!fileVar} ]]; then
			echo "Setting ${var} from file"
			val="$(< "${!fileVar}")"
			export "$var"="$val"
		else
			echo "File ${!fileVar} doesn't exist"
			exit 1
		fi
	fi

}

# Source: https://github.com/sameersbn/docker-gitlab/
map_uidgid() {
	USERMAP_ORIG_UID=$(id -u paperless)
	USERMAP_ORIG_GID=$(id -g paperless)
	USERMAP_NEW_UID=${USERMAP_UID:-$USERMAP_ORIG_UID}
	USERMAP_NEW_GID=${USERMAP_GID:-${USERMAP_ORIG_GID:-$USERMAP_NEW_UID}}
	if [[ ${USERMAP_NEW_UID} != "${USERMAP_ORIG_UID}" || ${USERMAP_NEW_GID} != "${USERMAP_ORIG_GID}" ]]; then
		echo "Mapping UID and GID for paperless:paperless to $USERMAP_NEW_UID:$USERMAP_NEW_GID"
		usermod -o -u "${USERMAP_NEW_UID}" paperless
		groupmod -o -g "${USERMAP_NEW_GID}" paperless
	fi
}

map_folders() {
	# Export these so they can be used in docker-prepare.sh
	export DATA_DIR="${PAPERLESS_DATA_DIR:-/usr/src/paperless/data}"
	export MEDIA_ROOT_DIR="${PAPERLESS_MEDIA_ROOT:-/usr/src/paperless/media}"
	export CONSUME_DIR="${PAPERLESS_CONSUMPTION_DIR:-/usr/src/paperless/consume}"
}

nltk_data () {
	# Store the NLTK data outside the Docker container
	local nltk_data_dir="${DATA_DIR}/nltk"

	# Download or update the snowball stemmer data
	python3 -W ignore::RuntimeWarning -m nltk.downloader -d "${nltk_data_dir}" snowball_data

	# Download or update the stopwords corpus
	python3 -W ignore::RuntimeWarning -m nltk.downloader -d "${nltk_data_dir}" stopwords

	# Download or update the punkt tokenizer data
	python3 -W ignore::RuntimeWarning -m nltk.downloader -d "${nltk_data_dir}" punkt

}

initialize() {

	# Setup environment from secrets before anything else
	for env_var in \
		PAPERLESS_DBUSER \
		PAPERLESS_DBPASS \
		PAPERLESS_SECRET_KEY \
		PAPERLESS_AUTO_LOGIN_USERNAME \
		PAPERLESS_ADMIN_USER \
		PAPERLESS_ADMIN_MAIL \
		PAPERLESS_ADMIN_PASSWORD \
		PAPERLESS_REDIS; do
		# Check for a version of this var with _FILE appended
		# and convert the contents to the env var value
		file_env ${env_var}
	done

	# Change the user and group IDs if needed
	map_uidgid

	# Check for overrides of certain folders
	map_folders

	local export_dir="/usr/src/paperless/export"

	for dir in \
		"${export_dir}" \
		"${DATA_DIR}" "${DATA_DIR}/index" \
		"${MEDIA_ROOT_DIR}" "${MEDIA_ROOT_DIR}/documents" "${MEDIA_ROOT_DIR}/documents/originals" "${MEDIA_ROOT_DIR}/documents/thumbnails" \
		"${CONSUME_DIR}"; do
		if [[ ! -d "${dir}" ]]; then
			echo "Creating directory ${dir}"
			mkdir "${dir}"
		fi
	done

	local tmp_dir="/tmp/paperless"
	echo "Creating directory ${tmp_dir}"
	mkdir -p "${tmp_dir}"

	nltk_data

	set +e
	echo "Adjusting permissions of paperless files. This may take a while."
	chown -R paperless:paperless ${tmp_dir}
	for dir in \
		"${export_dir}" \
		"${DATA_DIR}" \
		"${MEDIA_ROOT_DIR}" \
		"${CONSUME_DIR}"; do
		find "${dir}" -not \( -user paperless -and -group paperless \) -exec chown paperless:paperless {} +
	done
	set -e

	"${gosu_cmd[@]}" /sbin/docker-prepare.sh
}

install_languages() {
	echo "Installing languages..."

	local langs="$1"
	read -ra langs <<<"$langs"

	# Check that it is not empty
	if [ ${#langs[@]} -eq 0 ]; then
		return
	fi
	apt-get update

	for lang in "${langs[@]}"; do
		pkg="tesseract-ocr-$lang"
		# English is installed by default
		#if [[ "$lang" ==  "eng" ]]; then
		#    continue
		#fi

		if dpkg -s "$pkg" &>/dev/null; then
			echo "Package $pkg already installed!"
			continue
		fi

		if ! apt-cache show "$pkg" &>/dev/null; then
			echo "Package $pkg not found! :("
			continue
		fi

		echo "Installing package $pkg..."
		if ! apt-get -y install "$pkg" &>/dev/null; then
			echo "Could not install $pkg"
			exit 1
		fi
	done
}

echo "Paperless-ngx docker container starting..."

gosu_cmd=(gosu paperless)
if [ "$(id -u)" == "$(id -u paperless)" ]; then
	gosu_cmd=()
fi

# Install additional languages if specified
if [[ -n "$PAPERLESS_OCR_LANGUAGES" ]]; then
	install_languages "$PAPERLESS_OCR_LANGUAGES"
fi

initialize

if [[ "$1" != "/"* ]]; then
	echo Executing management command "$@"
	exec "${gosu_cmd[@]}" python3 manage.py "$@"
else
	echo Executing "$@"
	exec "$@"
fi
