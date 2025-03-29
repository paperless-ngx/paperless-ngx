#!/usr/bin/env bash

set -e

# Source: https://github.com/sameersbn/docker-gitlab/
map_uidgid() {
	local -r usermap_original_uid=$(id -u edoc)
	local -r usermap_original_gid=$(id -g edoc)
	local -r usermap_new_uid=${USERMAP_UID:-$usermap_original_uid}
	local -r usermap_new_gid=${USERMAP_GID:-${usermap_original_gid:-$usermap_new_uid}}
	if [[ ${usermap_new_uid} != "${usermap_original_uid}" || ${usermap_new_gid} != "${usermap_original_gid}" ]]; then
		echo "Mapping UID and GID for edoc:edoc to $usermap_new_uid:$usermap_new_gid"
		usermod -o -u "${usermap_new_uid}" edoc
		groupmod -o -g "${usermap_new_gid}" edoc
	fi
}

map_folders() {
	# Export these so they can be used in docker-prepare.sh
	export DATA_DIR="${EDOC_DATA_DIR:-/usr/src/edoc/data}"
	export MEDIA_ROOT_DIR="${EDOC_MEDIA_ROOT:-/usr/src/edoc/media}"
	export CONSUME_DIR="${EDOC_CONSUMPTION_DIR:-/usr/src/edoc/consume}"
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

initialize() {

	# Setup environment from secrets before anything else
	# Check for a version of this var with _FILE appended
	# and convert the contents to the env var value
	# Source it so export is persistent
	# shellcheck disable=SC1091
	source /sbin/env-from-file.sh

	# Change the user and group IDs if needed
	map_uidgid

	# Check for overrides of certain folders
	map_folders

	local -r export_dir="/usr/src/edoc/export"

	for dir in \
		"${export_dir}" \
		"${DATA_DIR}" "${DATA_DIR}/index" \
		"${MEDIA_ROOT_DIR}" "${MEDIA_ROOT_DIR}/documents" "${MEDIA_ROOT_DIR}/documents/originals" "${MEDIA_ROOT_DIR}/documents/thumbnails" \
		"${CONSUME_DIR}"; do
		if [[ ! -d "${dir}" ]]; then
			echo "Creating directory ${dir}"
			mkdir --parents "${dir}"
		fi
	done

	local -r tmp_dir="${EDOC_SCRATCH_DIR:=/tmp/edoc}"
	echo "Creating directory scratch directory ${tmp_dir}"
	mkdir --parents "${tmp_dir}"

	set +e
	echo "Adjusting permissions of edoc files. This may take a while."
	chown -R edoc:edoc "${tmp_dir}"
	for dir in \
		"${export_dir}" \
		"${DATA_DIR}" \
		"${MEDIA_ROOT_DIR}" \
		"${CONSUME_DIR}"; do
		find "${dir}" -not \( -user edoc -and -group edoc \) -exec chown edoc:edoc {} +
	done
	set -e

	"${gosu_cmd[@]}" /sbin/docker-prepare.sh

	# Leave this last thing
	custom_container_init

}

install_languages() {
	echo "Installing languages..."

	read -ra langs <<<"$1"

	# Check that it is not empty
	if [ ${#langs[@]} -eq 0 ]; then
		return
	fi
	apt-get update

	for lang in "${langs[@]}"; do
		pkg="tesseract-ocr-$lang"

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

gosu_cmd=(gosu edoc)
if [ "$(id -u)" == "$(id -u edoc)" ]; then
	gosu_cmd=()
fi

# Install additional languages if specified
if [[ -n "$EDOC_OCR_LANGUAGES" ]]; then
	install_languages "$EDOC_OCR_LANGUAGES"
fi

initialize

if [[ "$1" != "/"* ]]; then
	echo Executing management command "$@"
	exec "${gosu_cmd[@]}" python3 manage.py "$@"
else
	echo Executing "$@"
	exec "$@"
fi
