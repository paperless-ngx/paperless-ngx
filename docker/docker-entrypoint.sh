#!/usr/bin/env bash

set -e

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
}

initialize() {
	# Change the user and group IDs if needed
	map_uidgid

	# Check for overrides of certain folders
	map_folders

	local export_dir="/usr/src/paperless/export"

	for dir in "${export_dir}" "${DATA_DIR}" "${DATA_DIR}/index" "${MEDIA_ROOT_DIR}" "${MEDIA_ROOT_DIR}/documents" "${MEDIA_ROOT_DIR}/documents/originals" "${MEDIA_ROOT_DIR}/documents/thumbnails"; do
		if [[ ! -d "${dir}" ]]; then
			echo "Creating directory ${dir}"
			mkdir "${dir}"
		fi
	done

	local tmp_dir="/tmp/paperless"
	echo "Creating directory ${tmp_dir}"
	mkdir -p "${tmp_dir}"

	set +e
	echo "Adjusting permissions of paperless files. This may take a while."
	chown -R paperless:paperless ${tmp_dir}
	for dir in "${export_dir}" "${DATA_DIR}" "${MEDIA_ROOT_DIR}"; do
		find "${dir}" -not \( -user paperless -and -group paperless \) -exec chown paperless:paperless {} +
	done
	set -e

	gosu paperless /sbin/docker-prepare.sh
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

# Install additional languages if specified
if [[ -n "$PAPERLESS_OCR_LANGUAGES" ]]; then
	install_languages "$PAPERLESS_OCR_LANGUAGES"
fi

initialize

if [[ "$1" != "/"* ]]; then
	echo Executing management command "$@"
	exec gosu paperless python3 manage.py "$@"
else
	echo Executing "$@"
	exec "$@"
fi
