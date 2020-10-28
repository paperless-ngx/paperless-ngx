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

migrations() {
    # A simple lock file in case other containers use this startup
    LOCKFILE="/usr/src/paperless/data/db.sqlite3.migration"

    # check for and create lock file in one command
    if (set -o noclobber; echo "$$" > "${LOCKFILE}") 2> /dev/null
    then
        trap 'rm -f "${LOCKFILE}"; exit $?' INT TERM EXIT
        sudo -HEu paperless python3 manage.py migrate
        rm ${LOCKFILE}
    fi
}

initialize() {
	map_uidgid

	for data_dir in index media media/documents media/thumbnails; do
		if [[ ! -d "../data/$data_dir" ]]
		then
			echo "creating directory ../data/$data_dir"
			mkdir ../data/$data_dir
		fi
	done

	chown -R paperless:paperless ../

	migrations

}

install_languages() {
	echo "TEST"
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

        if dpkg -s $pkg &> /dev/null; then
        	echo "package $pkg already installed!"
        	continue
        fi

        if ! apt-cache show $pkg &> /dev/null; then
        	echo "package $pkg not found! :("
        	continue
        fi

				echo "Installing package $pkg..."
				if ! apt-get -y install "$pkg" &> /dev/null; then
					echo "Could not install $pkg"
					exit 1
				fi
    done
}

if [[ "$1" != "/"* ]]; then
    initialize

    # Install additional languages if specified
    if [[ ! -z "$PAPERLESS_OCR_LANGUAGES"  ]]; then
        install_languages "$PAPERLESS_OCR_LANGUAGES"
    fi

    if [[ "$1" = "gunicorn" ]]; then
        shift
        cd /usr/src/paperless/src/ && \
            exec sudo -HEu paperless gunicorn -c /usr/src/paperless/gunicorn.conf.py "$@" paperless.wsgi
    fi

		exec sudo -HEu paperless python3 manage.py "$@"

fi

exec "$@"

