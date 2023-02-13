# Docker compose files

## Introduction

This folder contains a set of docker-compose files for running paperless from the Docker registries.

Those files contain everything paperless needs to run.

Paperless supports amd64, arm and arm64 hardware.

We have to choose of the database: sqlite, postgres or mariadb,
and to have the Tika stack or not.

All compose files of paperless configure paperless in the following way:

- Paperless is (re)started on system boot, if it was running before shutdown.
- Docker volumes for storing data are managed by Docker.
- Folders for importing and exporting files are created in the same directory
  as this file and mounted to the correct folders inside the container.
- Paperless listens on port `8000`.

To install and update paperless with this file, do the following:

- Copy the chosen file as `docker-compose.yaml`, the `docker-compose.lib.yaml` and the files `.env`
  and `.env` into a folder.
- Run `docker-compose pull`.
- Run `docker-compose run --rm webserver createsuperuser` to create a user.
- Run `docker-compose up -d`.

For more extensive installation and update instructions, refer to the documentation.

## Configuration

The configuration is done in the `.env` file, if you don't modify it, the other files the migration will be easier.

## Upgrade

To Upgrade your project, you have to copy the chosen docker-compose file as `docker-compose.yaml` and the `docker-compose.lib.yaml` into your folder.

## Upgrade from older version than 1.13

The structure change in the version 1.13.

If you modify only the `docker-compose.env`, should do the following to upgrade your project:

- Copy the new `.env`, the chosen docker-compose file as `docker-compose.yaml` and the `docker-compose.lib.yaml` into your folder.
- In the `.env` file, replace everything after `# Paperless configuration` by the content of your `docker-compose.env`.
- Remove your no more needed `docker-compose.env` file.

## Portainer

Those Docker compose files can be used directly, in
[Protainer](https://docs.portainer.io), see the documentation for more information.
