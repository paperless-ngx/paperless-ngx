#!/bin/bash

set -e

# Source: https://github.com/sameersbn/docker-gitlab/
map_uidgid() {
	USERMAP_ORIG_UID=$(id -u paperless)
	USERMAP_ORIG_GID=$(id -g paperless)
	USERMAP_NEW_UID=${USERMAP_UID:-$USERMAP_ORIG_UID}
	USERMAP_NEW_GID=${USERMAP_GID:-${USERMAP_ORIG_GID:-$USERMAP_NEW_UID}}
	if [[ ${USERMAP_NEW_UID} != "${USERMAP_ORIG_UID}" || ${USERMAP_NEW_GID} != "${USERMAP_ORIG_GID}" ]]; then
		echo "Mapping UID and GID for paperless:paperless to $USERMAP_NEW_UID:$USERMAP_NEW_GID"
		usermod -u "${USERMAP_NEW_UID}" paperless
		groupmod -o -g "${USERMAP_NEW_GID}" paperless
	fi
}

initialize() {
	map_uidgid

	for dir in export data data/index media media/documents media/documents/originals media/documents/thumbnails; do
		if [[ ! -d "../$dir" ]]; then
			echo "Creating directory ../$dir"
			mkdir ../$dir
		fi
	done

	echo "Creating directory /tmp/paperless"
	mkdir -p /tmp/paperless

	set +e
	echo "Adjusting permissions of paperless files. This may take a while."
	chown -R paperless:paperless /tmp/paperless
	find .. -not \( -user paperless -and -group paperless \) -exec chown paperless:paperless {} +
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

		if dpkg -s $pkg &>/dev/null; then
			echo "Package $pkg already installed!"
			continue
		fi

		if ! apt-cache show $pkg &>/dev/null; then
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

echo "Paperless-ng docker container starting..."

# Install additional languages if specified
if [[ ! -z "$PAPERLESS_OCR_LANGUAGES" ]]; then
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
