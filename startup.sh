#!/usr/bin/env bash

curl -fsSL get.docker.com -o get-docker.sh
sudo sh get-docker.sh

sudo apt-get update -y
sudo apt-get install docker-compose-plugin

curl https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docker/compose/.env -o .env
curl https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docker/compose/docker-compose.env -o docker-compose.env
curl https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docker/compose/docker-compose.postgres-tika.yml -o docker-compose.yml

docker compose run --rm webserver createsuperuser
