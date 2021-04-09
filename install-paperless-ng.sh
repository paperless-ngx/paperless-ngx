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
	echo ""
	echo "WARN: It look like the current user does not have Docker permissions."
	echo "WARN: Use 'sudo usermod -aG docker $USER' to assign Docker permissions to the user."
	echo ""
	sleep 3
fi

default_time_zone=$(timedatectl show -p Timezone --value)

set -e

echo ""
echo "############################################"
echo "###   Paperless-ng docker installation   ###"
echo "############################################"
echo ""
echo "This script will download, configure and start paperless-ng."

echo ""
echo "1. Folder configuration"
echo "======================="
echo ""
echo "The target folder is used to store the configuration files of "
echo "paperless. You can move this folder around after installing paperless."
echo "You will need this folder whenever you want to start, stop, update or "
echo "maintain your paperless instance."
echo ""

ask "Target folder" "$(pwd)/paperless-ng"
TARGET_FOLDER=$ask_result

echo ""
echo "The consume folder is where paperles will search for new documents."
echo "Point this to a folder where your scanner is able to put your scanned"
echo "documents."
echo ""
echo "CAUTION: You must specify an absolute path starting with / or a relative "
echo "path starting with ./ here. Examples:"
echo "  /mnt/consume"
echo "  ./consume"
echo ""

ask_docker_folder "Consume folder" "$TARGET_FOLDER/consume"
CONSUME_FOLDER=$ask_result

echo ""
echo "The media folder is where paperless stores your documents."
echo "Leave empty and docker will manage this folder for you."
echo "Docker usually stores managed folders in /var/lib/docker/volumes."
echo ""
echo "CAUTION: If specified, you must specify an absolute path starting with /"
echo "or a relative path starting with ./ here."
echo ""

ask_docker_folder "Media folder" ""
MEDIA_FOLDER=$ask_result

echo ""
echo "The data folder is where paperless stores other data, such as your"
echo "SQLite database (if used), the search index and other data."
echo "As with the media folder, leave empty to have this managed by docker."
echo ""
echo "CAUTION: If specified, you must specify an absolute path starting with /"
echo "or a relative path starting with ./ here."
echo ""

ask_docker_folder "Data folder" ""
DATA_FOLDER=$ask_result

echo ""
echo "2. Application configuration"
echo "============================"

echo ""
echo "The port on which the paperless webserver will listen for incoming"
echo "connections."
echo ""

ask "Port" "8000"
PORT=$ask_result

echo ""
echo "Paperless requires you to configure the current time zone correctly."
echo "Otherwise, the dates of your documents may appear off by one day,"
echo "depending on where you are on earth."
echo ""

ask "Current time zone" "$default_time_zone"
TIME_ZONE=$ask_result

echo ""
echo "Database backend: PostgreSQL and SQLite are available. Use PostgreSQL"
echo "if unsure. If you're running on a low-power device such as Raspberry"
echo "Pi, use SQLite to save resources."
echo ""

ask "Database backend" "postgres" "postgres sqlite"
DATABASE_BACKEND=$ask_result

echo ""
echo "Paperless is able to use Apache Tika to support Office documents such as"
echo "Word, Excel, Powerpoint, and Libreoffice equivalents. This feature"
echo "requires more resources due to the required services."
echo ""

ask "Enable Apache Tika?" "no" "yes no"
TIKA_ENABLED=$ask_result

echo ""
echo "Specify the default language that most of your documents are written in."
echo "Use ISO 639-2, (T) variant language codes: "
echo "https://www.loc.gov/standards/iso639-2/php/code_list.php"
echo "Common values: eng (English) deu (German) nld (Dutch) fra (French)"
echo ""

ask "OCR language" "eng"
OCR_LANGUAGE=$ask_result

echo ""
echo "Specify the user id and group id you wish to run paperless as."
echo "Paperless will also change ownership on the data, media and consume"
echo "folder to the specified values, so it's a good idea to supply the user id"
echo "and group id of your unix user account."
echo "If unsure, leave default."
echo ""

ask "User ID" "$(id -u)"
USERMAP_UID=$ask_result

ask "Group ID" "$(id -g)"
USERMAP_GID=$ask_result

echo ""
echo "3. Login credentials"
echo "===================="
echo ""
echo "Specify initial login credentials. You can change these later."
echo "A mail address is required, however it is not used in paperless. You don't"
echo "need to provide an actual mail address."
echo ""

ask "Paperless username" "$(whoami)"
USERNAME=$ask_result

while true; do
	read -sp "Paperless password: " PASSWORD
	echo ""

	if [[ -z $PASSWORD ]] ; then
		echo "Password cannot be empty."
		continue
	fi

	read -sp "Paperless password (again): " PASSWORD_REPEAT
	echo ""

	if [[ ! "$PASSWORD" == "$PASSWORD_REPEAT" ]] ; then
		echo "Passwords did not match"
	else
		break
	fi
done

ask "Email" "$USERNAME@localhost"
EMAIL=$ask_result

echo ""
echo "Summary"
echo "======="
echo ""

echo "Target folder: $TARGET_FOLDER"
echo "Consume folder: $CONSUME_FOLDER"
if [[ -z $MEDIA_FOLDER ]] ; then
	echo "Media folder: Managed by docker"
else
	echo "Media folder: $MEDIA_FOLDER"
fi
if [[ -z $DATA_FOLDER ]] ; then
	echo "Data folder: Managed by docker"
else
	echo "Data folder: $DATA_FOLDER"
fi
echo ""
echo "Port: $PORT"
echo "Database: $DATABASE_BACKEND"
echo "Tika enabled: $TIKA_ENABLED"
echo "OCR language: $OCR_LANGUAGE"
echo "User id: $USERMAP_UID"
echo "Group id: $USERMAP_GID"
echo ""
echo "Paperless username: $USERNAME"
echo "Paperless email: $EMAIL"

echo ""
read -p "Press any key to install."

echo ""
echo "Installing paperless..."
echo ""

mkdir -p "$TARGET_FOLDER"

cd "$TARGET_FOLDER"

DOCKER_COMPOSE_VERSION=$DATABASE_BACKEND

if [[ $TIKA_ENABLED == "yes" ]] ; then
	DOCKER_COMPOSE_VERSION="$DOCKER_COMPOSE_VERSION-tika"
fi

wget "https://raw.githubusercontent.com/jonaswinkler/paperless-ng/master/docker/compose/docker-compose.$DOCKER_COMPOSE_VERSION.yml" -O docker-compose.yml
wget "https://raw.githubusercontent.com/jonaswinkler/paperless-ng/master/docker/compose/.env" -O .env

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
} > docker-compose.env

sed -i "s/- 8000:8000/- $PORT:8000/g" docker-compose.yml

sed -i "s#- \./consume:/usr/src/paperless/consume#- $CONSUME_FOLDER:/usr/src/paperless/consume#g" docker-compose.yml

if [[ -n $MEDIA_FOLDER ]] ; then
	sed -i "s#- media:/usr/src/paperless/media#- $MEDIA_FOLDER:/usr/src/paperless/media#g" docker-compose.yml
fi

if [[ -n $DATA_FOLDER ]] ; then
	sed -i "s#- data:/usr/src/paperless/data#- $DATA_FOLDER:/usr/src/paperless/data#g" docker-compose.yml
fi

docker-compose pull

docker-compose run --rm -e DJANGO_SUPERUSER_PASSWORD="$PASSWORD" webserver createsuperuser --noinput --username "$USERNAME" --email "$EMAIL"

docker-compose up -d
