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
        groupmod -g "${USERMAP_NEW_GID}" paperless
    fi
}

set_permissions() {
    # Set permissions for consumption and export directory
    for dir in PAPERLESS_CONSUMPTION_DIR PAPERLESS_EXPORT_DIR; do
      # Extract the name of the current directory from $dir for the error message
      cur_dir_name=$(echo "$dir" | awk -F'_' '{ print tolower($2); }')
      chgrp paperless "${!dir}" || {
          echo "Changing group of ${cur_dir_name} directory:"
          echo "  ${!dir}"
          echo "failed."
          echo ""
          echo "Either try to set it on your host-mounted directory"
          echo "directly, or make sure that the directory has \`g+wx\`"
          echo "permissions and the files in it at least \`o+r\`."
      } >&2
      chmod g+wx "${!dir}" || {
          echo "Changing group permissions of ${cur_dir_name} directory:"
          echo "  ${!dir}"
          echo "failed."
          echo ""
          echo "Either try to set it on your host-mounted directory"
          echo "directly, or make sure that the directory has \`g+wx\`"
          echo "permissions and the files in it at least \`o+r\`."
      } >&2
    done
    # Set permissions for application directory
    chown -Rh paperless:paperless /usr/src/paperless
}

migrations() {
    # A simple lock file in case other containers use this startup
    LOCKFILE="/usr/src/paperless/data/db.sqlite3.migration"

    # check for and create lock file in one command 
    if (set -o noclobber; echo "$$" > "${LOCKFILE}") 2> /dev/null
    then
        trap 'rm -f "${LOCKFILE}"; exit $?' INT TERM EXIT
        sudo -HEu paperless "/usr/src/paperless/src/manage.py" "migrate"
        rm ${LOCKFILE}
    fi
}

initialize() {
    map_uidgid
    set_permissions
    migrations
}

install_languages() {
    local langs="$1"
    read -ra langs <<<"$langs"

    # Check that it is not empty
    if [ ${#langs[@]} -eq 0 ]; then
        return
    fi

    # Loop over languages to be installed
    for lang in "${langs[@]}"; do
        pkg="tesseract-ocr-data-$lang"

        # English is installed by default
        if [[ "$lang" ==  "eng" ]]; then
            continue
        fi

        if apk info -e "$pkg" > /dev/null 2>&1; then
            continue
        fi
        if ! apk --no-cache info "$pkg" > /dev/null 2>&1; then
            continue
        fi

        apk --no-cache --update add "$pkg"
    done
}


if [[ "$1" != "/"* ]]; then
    initialize

    # Install additional languages if specified
    if [[ ! -z "$PAPERLESS_OCR_LANGUAGES"  ]]; then
        install_languages "$PAPERLESS_OCR_LANGUAGES"
    fi

    exec sudo -HEu paperless "/usr/src/paperless/src/manage.py" "$@"
fi

exec "$@"

