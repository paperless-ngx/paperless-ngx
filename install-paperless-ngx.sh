#!/bin/bash

ask() {
	while true ; do
		if [[ -z $3 ]] ; then
			read -p "$1 [$2]: " result
		else
			read -p "$1 ($3) [$2]: " result
		fi
		if [[ -z $result ]]; then
			ask_result=$2
			return
		fi
		array=$3
		if [[ -z $3 || " ${array[@]} " =~ " ${result} " ]]; then
			ask_result=$result
			return
		else
			echo "Invalid option: $result"
		fi
	done
}

ask_docker_folder() {
	while true ; do

		read -p "$1 [$2]: " result

		if [[ -z $result ]]; then
			ask_result=$2
			return
		fi

		if [[ $result == /* || $result == ./* ]]; then
			ask_result=$result
			return
		else
			echo "Invalid folder: $result"
		fi


	done
}

if [[ $(id -u) == "0" ]] ; then
	echo "Do not run this script as root."
	exit 1
fi

if [[ -z $(which wget) ]] ; then
	echo "wget executable not found. Is wget installed?"
	exit 1
fi

if [[ -z $(which docker) ]] ; then
	echo "docker executable not found. Is docker installed?"
	exit 1
fi

if [[ -z $(which docker-compose) ]] ; then
	echo "docker-compose executable not found. Is docker-compose installed?"
	exit 1
fi

# Check if user has permissions to run Docker by trying to get the status of Docker (docker status).
# If this fails, the user probably does not have permissions for Docker.
docker stats --no-stream 2>/dev/null 1>&2
if [ $? -ne 0 ] ; then
    cat <<EOM

WARN: It look like the current user does not have Docker permissions.
WARN: Use 'sudo usermod -aG docker $USER' to assign Docker permissions to the user.

EOM
	sleep 3
fi

default_time_zone=$(timedatectl show -p Timezone --value)

set -e

[[ -r "${HOME}/.paperless-ngx.setup.env" ]] && source "${HOME}/.paperless-ngx.setup.env"

function dumpEnv() {
    mv "${HOME}/.paperless-ngx.setup.env" "${HOME}/.paperless-ngx.setup.env.bak" || true
    cat > "${HOME}/.paperless-ngx.setup.env" <<EOF
#==================================================================
# Papaerless NGX config,  $(date)
#==================================================================
PORT="${PORT}"
TIME_ZONE="${TIME_ZONE}"
DATABASE_BACKEND="${DATABASE_BACKEND}"
TIKA_ENABLED="${TIKA_ENABLED}"
OCR_LANGUAGE="${OCR_LANGUAGE}"
USERMAP_UID="${USERMAP_UID}"
USERMAP_GID="${USERMAP_GID}"
TARGET_FOLDER="${TARGET_FOLDER}"
CONSUME_FOLDER="${CONSUME_FOLDER}"
MEDIA_FOLDER="${MEDIA_FOLDER}"
DATA_FOLDER="${DATA_FOLDER}"
POSTGRES_FOLDER="${POSTGRES_FOLDER}"
USERNAME="${USERNAME}"
EMAIL="${EMAIL}"
FILENAME_FORMAT="${FILENAME_FORMAT}"
# FILENAME_FORMAT="{created_year}/{correspondent}/{title}"
# FILENAME_FORMAT="{tag_list}/{created_year}/{correspondent}/{title}"

EOF
    cat "${HOME}/.paperless-ngx.setup.env.bak" \
    | sed -e 's/^/# /' \
    >> "${HOME}/.paperless-ngx.setup.env"
}

cat <<EOM

#############################################"
###   paperless-ngx docker installation   ###"
#############################################"

This script will download, configure and start paperless-ngx.


1. Application configuration
============================


The port on which the paperless webserver will listen for incoming
connections.

EOM

ask "Port" "${PORT:-8000}"
PORT="${ask_result}"

cat <<EOM

Paperless requires you to configure the current time zone correctly.
Otherwise, the dates of your documents may appear off by one day,
depending on where you are on earth.

EOM

ask "Current time zone" "${TIME_ZONE:-${default_time_zone}}"
TIME_ZONE="${ask_result}"

cat <<EOM

Database backend: PostgreSQL and SQLite are available. Use PostgreSQL
if unsure. If you're running on a low-power device such as Raspberry
Pi, use SQLite to save resources.

EOM

ask "Database backend" "${DATABASE_BACKEND:-postgres}" "postgres sqlite"
DATABASE_BACKEND="${ask_result}"

cat <<EOM

Paperless is able to use Apache Tika to support Office documents such as
Word, Excel, Powerpoint, and Libreoffice equivalents. This feature
requires more resources due to the required services.

EOM

ask "Enable Apache Tika?" "${TIKA_ENABLED:-no}" "yes no"
TIKA_ENABLED="${ask_result}"

cat <<EOM

Specify the default language that most of your documents are written in.
Use ISO 639-2, (T) variant language codes:
https://www.loc.gov/standards/iso639-2/php/code_list.php
Common values: eng (English) deu (German) nld (Dutch) fra (French)
This can be a combination of multiple languages such as deu+eng

EOM

ask "OCR language" "${OCR_LANGUAGE:-eng}"
OCR_LANGUAGE="${ask_result}"

cat <<EOM

Specify the user id and group id you wish to run paperless as.
Paperless will also change ownership on the data, media and consume
folder to the specified values, so it's a good idea to supply the user id
and group id of your unix user account.
If unsure, leave default.

EOM

ask "User ID" "${USERMAP_UID:-$(id -u)}"
USERMAP_UID="${ask_result}"

ask "Group ID" "${USERMAP_GID:-$(id -g)}"
USERMAP_GID="${ask_result}"

cat <<EOM

2. Folder configuration
=======================

The target folder is used to store the configuration files of
paperless. You can move this folder around after installing paperless.
You will need this folder whenever you want to start, stop, update or
maintain your paperless instance.

EOM

ask "Target folder" "${TARGET_FOLDER:-$(/bin/pwd)/paperless-ngx}"
TARGET_FOLDER="${ask_result}"

cat <<EOM

The consume folder is where paperles will search for new documents.
Point this to a folder where your scanner is able to put your scanned
documents.

CAUTION: You must specify an absolute path starting with / or a relative
path starting with ./ here. Examples:
  /mnt/consume
  ./consume

EOM

ask_docker_folder "Consume folder" "${CONSUME_FOLDER:-${TARGET_FOLDER}/consume}"
CONSUME_FOLDER="${ask_result}"

cat <<EOM

The media folder is where paperless stores your documents.
Leave empty and docker will manage this folder for you.
Docker usually stores managed folders in /var/lib/docker/volumes.

CAUTION: If specified, you must specify an absolute path starting with /
or a relative path starting with ./ here.

EOM

ask_docker_folder "Media folder" "${MEDIA_FOLDER}"
MEDIA_FOLDER="${ask_result}"

[[ "${DATABASE_BACKEND}" == "sqlite" ]] && msgPfx="SQLite database, the "
cat <<EOM

The data folder is where paperless stores other data, such as your
${msgPfx}search index and other data.
As with the media folder, leave empty to have this managed by docker.

CAUTION: If specified, you must specify an absolute path starting with /
or a relative path starting with ./ here.

EOM

ask_docker_folder "Data folder" "${DATA_FOLDER}"
DATA_FOLDER="${ask_result}"

if [[ "${DATABASE_BACKEND}" == "postgres" ]] ; then
    cat <<EOM

The database folder, where postgres stores its data.
Leave empty to have this managed by docker.

CAUTION: If specified, you must specify an absolute path starting with /
or a relative path starting with ./ here.

EOM

	ask_docker_folder "Database (postgres) folder" "${POSTGRES_FOLDER}"
	POSTGRES_FOLDER="${ask_result}"
fi

cat <<EOM

3. Login credentials
====================

Specify initial login credentials. You can change these later.
A mail address is required, however it is not used in paperless. You don't
need to provide an actual mail address.

EOM

ask "Paperless username" "${USERNAME:-$(whoami)}"
USERNAME="${ask_result}"

while true; do
	read -sp "Paperless password: " PASSWORD
	echo

	if [[ -z $PASSWORD ]] ; then
		echo "Password cannot be empty."
		continue
	fi

	read -sp "Paperless password (again): " PASSWORD_REPEAT
	echo

	if [[ "$PASSWORD" == "$PASSWORD_REPEAT" ]] ; then
		break
	fi

    echo "Passwords did not match"
done

ask "Email" "${EMAIL:-$USERNAME@localhost}"
EMAIL="${ask_result}"

dumpEnv

# dbFolderMsg="Database: SQLite"
[[ "$DATABASE_BACKEND" == "postgres" ]] && dbFolderMsg="Database (postgres) folder: ${POSTGRES_FOLDER:-Managed by docker}"
cat <<EOM

Summary
=======

Target folder      : ${TARGET_FOLDER}
Consume folder     : ${CONSUME_FOLDER}
Media folder       : ${MEDIA_FOLDER:-Managed by docker}
Data folder        : ${DATA_FOLDER:-Managed by docker}

Port               : ${PORT}
Database           : ${DATABASE_BACKEND}
${dbFolderMsg}
Tika enabled       : ${TIKA_ENABLED}
OCR language       : ${OCR_LANGUAGE}
User  id           : ${USERMAP_UID}
Group id           : ${USERMAP_GID}

Paperless username : ${USERNAME}
Paperless email    : ${EMAIL}

EOM
read -p "Press any key to install."

cat <<EOM

Installing paperless...

EOM

mkdir -p "${TARGET_FOLDER}"

cd "${TARGET_FOLDER}"

DOCKER_COMPOSE_VERSION="${DATABASE_BACKEND}"

if [[ "${TIKA_ENABLED}" == "yes" ]] ; then
	DOCKER_COMPOSE_VERSION="${DOCKER_COMPOSE_VERSION}-tika"
fi

BASE_URL="https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docker/compose"
wget "${BASE_URL}/docker-compose.${DOCKER_COMPOSE_VERSION}.yml" -O docker-compose.yml
wget "${BASE_URL}/.env" -O .env

SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)

DEFAULT_LANGUAGES="deu eng fra ita spa"

{
	if [[ ! $USERMAP_UID == "1000" ]] ; then
		echo "USERMAP_UID=$USERMAP_UID"
	fi
	if [[ ! $USERMAP_GID == "1000" ]] ; then
		echo "USERMAP_GID=$USERMAP_GID"
	fi
	echo "PAPERLESS_TIME_ZONE=$TIME_ZONE"
	echo "PAPERLESS_OCR_LANGUAGE=$OCR_LANGUAGE"
	echo "PAPERLESS_SECRET_KEY=$SECRET_KEY"
	if [[ ! " ${DEFAULT_LANGUAGES[@]} " =~ " ${OCR_LANGUAGE} " ]] ; then
		echo "PAPERLESS_OCR_LANGUAGES=$OCR_LANGUAGE"
	fi
	[[ -z "${FILENAME_FORMAT}" ]] || echo "PAPERLESS_FILENAME_FORMAT=${FILENAME_FORMAT}"
} > docker-compose.env

sed -i "s/- 8000:8000/- $PORT:8000/g" docker-compose.yml

sed -i "s#- \./consume:/usr/src/paperless/consume#- $CONSUME_FOLDER:/usr/src/paperless/consume#g" docker-compose.yml

if [[ -n $MEDIA_FOLDER ]] ; then
	sed -i "s#- media:/usr/src/paperless/media#- $MEDIA_FOLDER:/usr/src/paperless/media#g" docker-compose.yml
fi

if [[ -n $DATA_FOLDER ]] ; then
	sed -i "s#- data:/usr/src/paperless/data#- $DATA_FOLDER:/usr/src/paperless/data#g" docker-compose.yml
fi

if [[ -n $POSTGRES_FOLDER ]] ; then
	sed -i "s#- pgdata:/var/lib/postgresql/data#- $POSTGRES_FOLDER:/var/lib/postgresql/data#g" docker-compose.yml
fi

docker-compose pull

docker-compose run --rm -e DJANGO_SUPERUSER_PASSWORD="$PASSWORD" webserver createsuperuser --noinput --username "$USERNAME" --email "$EMAIL" || true

docker-compose up -d
