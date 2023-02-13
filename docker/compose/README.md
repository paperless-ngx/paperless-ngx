# Docker compose files

This folder contains a set of docker-compose files for running paperless from the Docker Hub.

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

For more extensive installation and update instructions, refer to the
documentation.

## Portainer

Docker compose files that are made to be used directly, especially with
[Protainer](https://docs.portainer.io), the configuration is done just in the `.env` file.
