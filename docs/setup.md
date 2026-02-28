---
title: Setup
---

# Installation

!!! tip "Quick Start"

    If you just want Paperless-ngx running quickly, use our installation script:
    ```shell-session
    bash -c "$(curl --location --silent --show-error https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/install-paperless-ngx.sh)"
    ```
    _If piping into a shell directly from the internet makes you nervous, inspect [the script](https://github.com/paperless-ngx/paperless-ngx/blob/main/install-paperless-ngx.sh) first!_

## Overview

Choose the installation route that best fits your setup:

| Route                                                                                                             | Best for                                                                            | Effort |
| ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------ |
| [Installation script](#docker_script)                                                                             | Fastest first-time setup with guided prompts (recommended for most users)           | Low    |
| [Docker Compose templates](#docker)                                                                               | Manual control over compose files and settings                                      | Medium |
| [Bare metal](#bare_metal)                                                                                         | Advanced setups, packaging, and development-adjacent workflows                      | High   |
| [Hosted providers (wiki)](https://github.com/paperless-ngx/paperless-ngx/wiki/Related-Projects#hosting-providers) | Managed hosting options maintained by the community &mdash; check details carefully | Varies |

For most users, Docker is the best option. It is faster to set up,
easier to maintain, and ships with sensible defaults.

The bare-metal route gives you more control, but it requires manual
installation and operation of all components. It is usually best suited
for advanced users and contributors.

!!! info

    Because [superuser](usage.md#superusers) accounts have full access to all objects and documents, you may want to create a separate user account for daily use,
    or "downgrade" your superuser account to a normal user account after setup.

## Installation Script {#docker_script}

Paperless-ngx provides an interactive script for Docker Compose setups.
It asks a few configuration questions, then creates the required files,
pulls the image, starts the containers, and creates your [superuser](usage.md#superusers)
account. In short, it automates the [Docker Compose setup](#docker) described below.

#### Prerequisites

-   Docker and Docker Compose must be [installed](https://docs.docker.com/engine/install/){:target="\_blank"}.
-   macOS users will need [GNU sed](https://formulae.brew.sh/formula/gnu-sed) with support for running as `sed` as well as [wget](https://formulae.brew.sh/formula/wget).

#### Run the installation script

```shell-session
bash -c "$(curl --location --silent --show-error https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/install-paperless-ngx.sh)"
```

#### After installation

Paperless-ngx should be available at `http://127.0.0.1:8000` (or similar,
depending on your configuration) and you will be able to login with the
credentials you provided during the installation script.

## Docker Compose Install {#docker}

#### Prerequisites

-   Docker and Docker Compose must be [installed](https://docs.docker.com/engine/install/){:target="\_blank"}.

#### Installation

1.  Go to the [/docker/compose directory on the project
    page](https://github.com/paperless-ngx/paperless-ngx/tree/main/docker/compose){:target="\_blank"}
    and download one `docker-compose.*.yml` file for your preferred
    database backend. Save it in a local directory as `docker-compose.yml`.
    Also download `docker-compose.env` and `.env` into that same directory.

    If you want to enable optional support for Office and other documents, download a
    file with `-tika` in the file name.

    !!! tip

        For new installations, it is recommended to use PostgreSQL as the
        database backend.

2.  Modify `docker-compose.yml` as needed. For example, you may want to
    change the paths for `consume`, `media`, and other directories to
    use bind mounts.
    Find the line that specifies where to mount the directory, e.g.:

    ```yaml
    - ./consume:/usr/src/paperless/consume
    ```

    Replace the part _before_ the colon with your local directory:

    ```yaml
    - /home/jonaswinkler/paperless-inbox:/usr/src/paperless/consume
    ```

    You may also want to change the default port that the webserver will
    use from the default (8000) to something else, e.g. for port 8010:

    ```yaml
    ports:
        - 8010:8000
    ```

3.  Modify `docker-compose.env` with any configuration options you need.
    See the [configuration documentation](configuration.md) for all options.

    You may also need to set `USERMAP_UID` and `USERMAP_GID` to
    the UID and GID of your user on the host system. Use `id -u` and
    `id -g` to get these values. This ensures both the container and the
    host user can write to the consumption directory. If your UID and
    GID are `1000` (the default for the first normal user on many
    systems), this usually works out of the box without
    modifications. Run `id "username"` to check.

    !!! note

        You can utilize Docker secrets for configuration settings by
        appending `_FILE` to configuration values. For example [`PAPERLESS_DBUSER`](configuration.md#PAPERLESS_DBUSER)
        can be set using `PAPERLESS_DBUSER_FILE=/var/run/secrets/password.txt`.

4.  Run `docker compose pull`. This pulls the image from the GitHub container registry
    by default, but you can pull from Docker Hub by changing the `image`
    line to `image: paperlessngx/paperless-ngx:latest`.

5.  Run `docker compose up -d`. This will create and start the necessary containers.

#### After installation

Your Paperless-ngx instance should now be accessible at
`http://127.0.0.1:8000` (or similar, depending on your configuration).
When you first access the web interface, you will be prompted to create
a [superuser](usage.md#superusers) account.

#### Optional Advanced Compose Configurations {#advanced_compose data-toc-label="Advanced Compose Configurations"}

**Rootless**

!!! warning

    It is currently not possible to run the container rootless if additional languages are specified via `PAPERLESS_OCR_LANGUAGES`.

If you want to run Paperless as a rootless container, make this
change in `docker-compose.yml`:

-   Set the `user` running the container to map to the `paperless`
    user in the container. This value (`user_id` below) should be
    the same ID that `USERMAP_UID` and `USERMAP_GID` are set to in
    `docker-compose.env`. See `USERMAP_UID` and `USERMAP_GID`
    [here](configuration.md#docker).

Your entry for Paperless should contain something like:

> ```
> webserver:
>   image: ghcr.io/paperless-ngx/paperless-ngx:latest
>   user: <user_id>
> ```

**File systems without inotify support (e.g. NFS)**

Some file systems, such as NFS network shares, don't support file system
notifications with `inotify`. When the consumption directory is on such a
file system, Paperless-ngx will not pick up new files with the default
configuration. Use [`PAPERLESS_CONSUMER_POLLING`](configuration.md#PAPERLESS_CONSUMER_POLLING)
to enable polling and disable inotify. See [here](configuration.md#polling).

## Bare Metal Install {#bare_metal}

#### Prerequisites

-   Paperless runs on Linux only, Windows is not supported.
-   Python 3 is required with versions 3.10 - 3.12 currently supported. Newer versions may work, but some dependencies may not be fully compatible.

#### Installation

1.  Install dependencies. Paperless requires the following packages:

    -   `python3`
    -   `python3-pip`
    -   `python3-dev`
    -   `default-libmysqlclient-dev` for MariaDB
    -   `pkg-config` for mysqlclient (python dependency)
    -   `fonts-liberation` for generating thumbnails for plain text
        files
    -   `imagemagick` >= 6 for PDF conversion
    -   `gnupg` for handling encrypted documents
    -   `libpq-dev` for PostgreSQL
    -   `libmagic-dev` for mime type detection
    -   `mariadb-client` for MariaDB compile time
    -   `poppler-utils` for barcode detection

    Use this list for your preferred package management:

    ```
    python3 python3-pip python3-dev imagemagick fonts-liberation gnupg libpq-dev default-libmysqlclient-dev pkg-config libmagic-dev poppler-utils
    ```

    These dependencies are required for OCRmyPDF, which is used for text
    recognition.

    -   `unpaper`
    -   `ghostscript`
    -   `icc-profiles-free`
    -   `qpdf`
    -   `liblept5`
    -   `libxml2`
    -   `pngquant` (suggested for certain PDF image optimizations)
    -   `zlib1g`
    -   `tesseract-ocr` >= 4.0.0 for OCR
    -   `tesseract-ocr` language packs (`tesseract-ocr-eng`,
        `tesseract-ocr-deu`, etc)

    Use this list for your preferred package management:

    ```
    unpaper ghostscript icc-profiles-free qpdf liblept5 libxml2 pngquant zlib1g tesseract-ocr
    ```

    On Raspberry Pi, these libraries are required as well:

    -   `libatlas-base-dev`
    -   `libxslt1-dev`
    -   `mime-support`

    You will also need these for installing some of the python dependencies:

    -   `build-essential`
    -   `python3-setuptools`
    -   `python3-wheel`

    Use this list for your preferred package management:

    ```
    build-essential python3-setuptools python3-wheel
    ```

2.  Install `redis` >= 6.0 and configure it to start automatically.

3.  Optional: Install `postgresql` and configure a database, user, and
    password for Paperless-ngx. If you do not wish to use PostgreSQL,
    MariaDB and SQLite are available as well.

    !!! note

        On bare-metal installations using SQLite, ensure the [JSON1
        extension](https://code.djangoproject.com/wiki/JSON1Extension) is
        enabled. This is usually the case, but not always.

4.  Create a system user with a new home folder in which you want
    to run Paperless-ngx.

    ```shell-session
    adduser paperless --system --home /opt/paperless --group
    ```

5.  Download a release archive from
    <https://github.com/paperless-ngx/paperless-ngx/releases>. For example:

    ```shell-session
    curl -O -L https://github.com/paperless-ngx/paperless-ngx/releases/download/vX.Y.Z/paperless-ngx-vX.Y.Z.tar.xz
    ```

    Extract the archive with

    ```shell-session
    tar -xf paperless-ngx-vX.Y.Z.tar.xz
    ```

    and copy the contents to the home directory of the user you created
    earlier (`/opt/paperless`).

    Optional: If you cloned the Git repository, you will need to
    compile the frontend yourself. See [here](development.md#front-end-development)
    and use the `build` step, not `serve`.

6.  Configure Paperless-ngx. See [configuration](configuration.md) for details.
    Edit the included `paperless.conf` and adjust the settings to your
    needs. Required settings for getting Paperless-ngx running are:

    -   [`PAPERLESS_REDIS`](configuration.md#PAPERLESS_REDIS) should point to your Redis server, such as
        `redis://localhost:6379`.
    -   [`PAPERLESS_DBENGINE`](configuration.md#PAPERLESS_DBENGINE) is optional, and should be one of `postgres`,
        `mariadb`, or `sqlite`
    -   [`PAPERLESS_DBHOST`](configuration.md#PAPERLESS_DBHOST) should be the hostname on which your
        PostgreSQL server is running. Do not configure this to use
        SQLite instead. Also configure port, database name, user and
        password as necessary.
    -   [`PAPERLESS_CONSUMPTION_DIR`](configuration.md#PAPERLESS_CONSUMPTION_DIR) should point to the folder
        that Paperless-ngx should watch for incoming documents.
        Likewise, [`PAPERLESS_DATA_DIR`](configuration.md#PAPERLESS_DATA_DIR) and
        [`PAPERLESS_MEDIA_ROOT`](configuration.md#PAPERLESS_MEDIA_ROOT) define where Paperless-ngx stores its data.
        If needed, these can point to the same directory.
    -   [`PAPERLESS_SECRET_KEY`](configuration.md#PAPERLESS_SECRET_KEY) should be a random sequence of
        characters. It's used for authentication. Failure to do so
        allows third parties to forge authentication credentials.
    -   Set [`PAPERLESS_URL`](configuration.md#PAPERLESS_URL) if you are behind a reverse proxy. This should
        point to your domain. Please see
        [configuration](configuration.md) for more
        information.

    You can make many more adjustments, especially for OCR.
    The following options are recommended for most users:

    -   Set [`PAPERLESS_OCR_LANGUAGE`](configuration.md#PAPERLESS_OCR_LANGUAGE) to the language most of your
        documents are written in.
    -   Set [`PAPERLESS_TIME_ZONE`](configuration.md#PAPERLESS_TIME_ZONE) to your local time zone.

    !!! warning

        Ensure your Redis instance [is secured](https://redis.io/docs/latest/operate/oss_and_stack/management/security/).

7.  Create the following directories if they do not already exist:

    -   `/opt/paperless/media`
    -   `/opt/paperless/data`
    -   `/opt/paperless/consume`

    Adjust these paths if you configured different folders.
    Then verify that the `paperless` user has write permissions:

    ```shell-session
    ls -l -d /opt/paperless/media
    ```

    If needed, change the owner with

    ```shell-session
    sudo chown paperless:paperless /opt/paperless/media
    sudo chown paperless:paperless /opt/paperless/data
    sudo chown paperless:paperless /opt/paperless/consume
    ```

8.  Install Python dependencies from `requirements.txt`.

    ```shell-session
    sudo -Hu paperless pip3 install -r requirements.txt
    ```

    This will install all Python dependencies in the home directory of
    the new paperless user.

    !!! tip

        You can use a virtual environment if you prefer. If you do,
        you may need to adjust the example scripts for your virtual
        environment paths.

    !!! tip

        If you use modern Python tooling, such as `uv`, installation will not include
        dependencies for PostgreSQL or MariaDB. You can select those
        extras with `--extra <EXTRA>`, or install all extras with
        `--all-extras`.

9.  Go to `/opt/paperless/src` and execute the following command:

    ```bash
    # This creates the database schema.
    sudo -Hu paperless python3 manage.py migrate
    ```

10. Optional: Test that Paperless-ngx is working by running

    ```bash
    # Manually starts the webserver
    sudo -Hu paperless python3 manage.py runserver
    ```

    Then point your browser to `http://localhost:8000` if
    accessing from the same device on which Paperless-ngx is installed.
    If accessing from another machine, set up systemd services. You may need
    to set `PAPERLESS_DEBUG=true` in order for the development server to work
    normally in your browser.

    !!! warning

        This is a development server which should not be used in production.
        It is not audited for security, and performance is inferior to
        production-ready web servers.

    !!! tip

        This will not start the consumer. Paperless does this in a separate
        process.

11. Set up systemd services to run Paperless-ngx automatically. You may use
    the service definition files included in the `scripts` folder as a
    starting point.

    Paperless needs:

    -   The `webserver` script to run the webserver.
    -   The `consumer` script to watch the input folder.
    -   The `taskqueue` script for background workers (document consumption, etc.).
    -   The `scheduler` script for periodic tasks such as email checking.

    !!! note

        The `socket` script enables `granian` to run on port 80 without
        root privileges. For this you need to uncomment the
        `Require=paperless-webserver.socket` in the `webserver` script
        and configure `granian` to listen on port 80 (set `GRANIAN_PORT`).

    These services rely on Redis and optionally the database server, but
    don't need to be started in any particular order. The example files
    depend on Redis being started. If you use a database server, you
    should add additional dependencies.

    !!! note

        For instructions on using a reverse proxy,
        [see the wiki](https://github.com/paperless-ngx/paperless-ngx/wiki/Using-a-Reverse-Proxy-with-Paperless-ngx#).

    !!! warning

        If Celery won't start, check
        `sudo systemctl status paperless-task-queue.service` for
        `paperless-task-queue.service` and `paperless-scheduler.service`.
        You may need to change the path in the files. Example:
        `ExecStart=/opt/paperless/.local/bin/celery --app paperless worker --loglevel INFO`

12. Configure ImageMagick to allow processing of PDF documents. Most
    distributions have this disabled by default, since PDF documents can
    contain malware. If you don't do this, Paperless-ngx will fall back to
    Ghostscript for certain steps such as thumbnail generation.

    Edit `/etc/ImageMagick-6/policy.xml` and adjust

    ```
    <policy domain="coder" rights="none" pattern="PDF" />
    ```

    to

    ```
    <policy domain="coder" rights="read|write" pattern="PDF" />
    ```

**Optional: Install the [jbig2enc](https://ocrmypdf.readthedocs.io/en/latest/jbig2.html) encoder.**
This will reduce the size of generated PDF documents. You'll most likely need to compile this yourself, because this
software has been patented until around 2017 and binary packages are not available for most distributions.

**Optional: download the NLTK data**
If using the NLTK machine-learning processing (see [`PAPERLESS_ENABLE_NLTK`](configuration.md#PAPERLESS_ENABLE_NLTK) for details),
download the NLTK data for the Snowball Stemmer, Stopwords and Punkt tokenizer to `/usr/share/nltk_data`. Refer to the [NLTK
instructions](https://www.nltk.org/data.html) for details on how to download the data.

#### After installation

Your Paperless-ngx instance should now be accessible at `http://localhost:8000` (or similar, depending on your configuration).
When you first access the web interface you will be prompted to create a [superuser](usage.md#superusers) account.

## Build the Docker image yourself {#docker_build data-toc-label="Building the Docker image"}

Building the Docker image yourself is typically used for development, but it can also be used for production
if you want to customize the image. See [Building the Docker image](development.md#docker_build) in the
development documentation.

## Migrating to Paperless-ngx

You can migrate to Paperless-ngx from Paperless-ng or from the original
Paperless project.

<h3 id="migration_ng">Migrating from Paperless-ng</h3>

Paperless-ngx is meant to be a drop-in replacement for Paperless-ng, and
upgrading should be trivial for most users, especially when using
Docker. However, as with any major change, it is recommended to take a
full backup first. Once you are ready, simply change the docker image to
point to the new source. For example, if using Docker Compose, edit
`docker-compose.yml` and change:

```
image: jonaswinkler/paperless-ng:latest
```

to

```
image: ghcr.io/paperless-ngx/paperless-ngx:latest
```

and then run `docker compose up -d`, which will pull the new image and
recreate the container. That's it.

Users who installed with the bare-metal route should also update their
Git clone to point to `https://github.com/paperless-ngx/paperless-ngx`,
for example using:
`git remote set-url origin https://github.com/paperless-ngx/paperless-ngx`
and then pull the latest version.

<h3 id="migration_paperless">Migrating from Paperless</h3>

At its core, Paperless-ngx is still Paperless and fully compatible.
However, some things have changed under the hood, so you need to adapt
your setup depending on how you installed Paperless.

This section describes how to update an existing Paperless Docker
installation. Keep these points in mind:

-   Read the [changelog](changelog.md) and
    take note of breaking changes.
-   Decide whether to stay on SQLite or migrate to PostgreSQL.
    Both work fine with Paperless-ngx.
    However, if you already have a database server running
    for other services, you might as well use it for Paperless as well.
-   The task scheduler of Paperless, which is used to execute periodic
    tasks such as email checking and maintenance, requires a
    [Redis](https://redis.io/) message broker instance. The
    Docker Compose route takes care of that.
-   The layout of the folder structure for your documents and data
    remains the same, so you can plug your old Docker volumes into
    paperless-ngx and expect it to find everything where it should be.

Migration to Paperless-ngx is then performed in a few simple steps:

1.  Stop Paperless.

    ```bash
    cd /path/to/current/paperless
    docker compose down
    ```

2.  Create a backup for two reasons: if something goes wrong, you still
    have your data; and if you don't like paperless-ngx, you can
    switch back to Paperless.

3.  Download the latest release of Paperless-ngx. You can either use
    the Docker Compose files from
    [here](https://github.com/paperless-ngx/paperless-ngx/tree/main/docker/compose)
    or clone the repository to build the image yourself (see
    [development docs](development.md#docker_build)). You can either replace your current paperless
    folder or put Paperless-ngx in
    a different location.

    !!! warning

        Paperless-ngx includes a `.env` file. This will set the project name
        for Docker Compose to `paperless`, which will also define the
        volume names created by Paperless-ngx. However, if you notice that
        paperless-ngx is not using your old paperless volumes, verify the
        names of your volumes with

        ``` shell-session
        docker volume ls | grep _data
        ```

        and adjust the project name in the `.env` file so that it matches
        the name of the volumes before the `_data` part.

4.  Download the `docker-compose.sqlite.yml` file to
    `docker-compose.yml`. If you want to switch to PostgreSQL, do that
    after you migrated your existing SQLite database.

5.  Adjust `docker-compose.yml` and `docker-compose.env` to your needs.
    See [Docker setup](#docker) for details on
    which edits are recommended.

6.  Follow the update procedure in [Update paperless](administration.md#updating).

7.  In order to find your existing documents with the new search
    feature, you need to invoke a one-time operation that will create
    the search index:

    ```shell-session
    docker compose run --rm webserver document_index reindex
    ```

    This will migrate your database and create the search index. After
    that, Paperless-ngx will maintain the index automatically.

8.  Start Paperless-ngx.

    ```bash
    docker compose up -d
    ```

    This will run Paperless-ngx in the background and automatically start it
    on system boot.

9.  Paperless may have installed a permanent redirect to `admin/` in your
    browser. This redirect is still in place and prevents access to the
    new UI. Clear your browser cache to fix this.

10. Optionally, follow the instructions below to migrate your existing
    data to PostgreSQL.

<h3 id="migration_lsio">Migrating from LinuxServer.io Docker Image</h3>

As with any upgrade or large change, it is highly recommended to
create a backup before starting. This assumes the image was running
using Docker Compose, but the instructions are translatable to Docker
commands as well.

1.  Stop and remove the Paperless container.
2.  If using an external database, stop that container.
3.  Update Redis configuration.

    1. If `REDIS_URL` is already set, change it to [`PAPERLESS_REDIS`](configuration.md#PAPERLESS_REDIS)
       and continue to step 4.

    1. Otherwise, add a new Redis service in `docker-compose.yml`,
       following [the example compose
       files](https://github.com/paperless-ngx/paperless-ngx/tree/main/docker/compose)

    1. Set the environment variable [`PAPERLESS_REDIS`](configuration.md#PAPERLESS_REDIS) so it points to
       the new Redis container.

4.  Update user mapping.

    1. If set, change the environment variable `PUID` to `USERMAP_UID`.

    1. If set, change the environment variable `PGID` to `USERMAP_GID`.

5.  Update configuration paths.

    1. Set the environment variable [`PAPERLESS_DATA_DIR`](configuration.md#PAPERLESS_DATA_DIR) to `/config`.

6.  Update media paths.

    1. Set the environment variable [`PAPERLESS_MEDIA_ROOT`](configuration.md#PAPERLESS_MEDIA_ROOT) to
       `/data/media`.

7.  Update timezone.

    1. Set the environment variable [`PAPERLESS_TIME_ZONE`](configuration.md#PAPERLESS_TIME_ZONE) to the same
       value as `TZ`.

8.  Modify `image:` to point to
    `ghcr.io/paperless-ngx/paperless-ngx:latest` or a specific version
    if preferred.
9.  Start the containers as before, using `docker compose`.

## Running Paperless-ngx on less powerful devices {#less-powerful-devices data-toc-label="Less Powerful Devices"}

Paperless runs on Raspberry Pi. Some tasks can be slow on lower-powered
hardware, but a few settings can improve performance:

-   Stick with SQLite to save some resources. See [troubleshooting](troubleshooting.md#log-reports-creating-paperlesstask-failed)
    if you encounter issues with SQLite locking.
-   If you do not need the filesystem-based consumer, consider disabling it
    entirely by setting [`PAPERLESS_CONSUMER_DISABLE`](configuration.md#PAPERLESS_CONSUMER_DISABLE) to `true`.
-   Consider setting [`PAPERLESS_OCR_PAGES`](configuration.md#PAPERLESS_OCR_PAGES) to 1, so that Paperless
    OCRs only the first page of your documents. In most cases, this page
    contains enough information to be able to find it.
-   [`PAPERLESS_TASK_WORKERS`](configuration.md#PAPERLESS_TASK_WORKERS) and [`PAPERLESS_THREADS_PER_WORKER`](configuration.md#PAPERLESS_THREADS_PER_WORKER) are
    configured to use all cores. The Raspberry Pi models 3 and up have 4
    cores, meaning that Paperless will use 2 workers and 2 threads per
    worker. This may result in sluggish response times during
    consumption, so you might want to lower these settings (example: 2
    workers and 1 thread to always have some computing power left for
    other tasks).
-   Keep [`PAPERLESS_OCR_MODE`](configuration.md#PAPERLESS_OCR_MODE) at its default value `skip` and consider
    OCRing your documents before feeding them into Paperless. Some
    scanners are able to do this!
-   Set [`PAPERLESS_OCR_SKIP_ARCHIVE_FILE`](configuration.md#PAPERLESS_OCR_SKIP_ARCHIVE_FILE) to `with_text` to skip archive
    file generation for already OCRed documents, or `always` to skip it
    for all documents.
-   If you want to perform OCR on the device, consider using
    `PAPERLESS_OCR_CLEAN=none`. This will speed up OCR times and use
    less memory at the expense of slightly worse OCR results.
-   If using Docker, consider setting [`PAPERLESS_WEBSERVER_WORKERS`](configuration.md#PAPERLESS_WEBSERVER_WORKERS) to 1. This will save some memory.
-   Consider setting [`PAPERLESS_ENABLE_NLTK`](configuration.md#PAPERLESS_ENABLE_NLTK) to false, to disable the
    more advanced language processing, which can take more memory and
    processing time.

For details, refer to [configuration](configuration.md).

!!! note

    Updating the
    [automatic matching algorithm](advanced_usage.md#automatic-matching) takes quite a bit of time. However, the update mechanism
    checks if your data has changed before doing the heavy lifting. If you
    experience the algorithm taking too much CPU time, consider changing the
    schedule in the admin interface to daily. You can also manually invoke
    the task by changing the date and time of the next run to today/now.

    The actual matching of the algorithm is fast and works on Raspberry Pi
    as well as on any other device.

## Additional considerations

**Using a reverse proxy with Paperless-ngx**

Please see [the wiki](https://github.com/paperless-ngx/paperless-ngx/wiki/Using-a-Reverse-Proxy-with-Paperless-ngx#nginx) for user-maintained documentation on using nginx with Paperless-ngx.

**Enhancing security**

Please see [the wiki](https://github.com/paperless-ngx/paperless-ngx/wiki/Using-Security-Tools-with-Paperless-ngx) for user-maintained documentation on configuring security tools like Fail2ban with Paperless-ngx.
