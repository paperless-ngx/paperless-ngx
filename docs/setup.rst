
*****
Setup
*****

Overview of Paperless-ng
########################

Compared to paperless, paperless-ng works a little different under the hood and has
more moving parts that work together. While this increases the complexity of
the system, it also brings many benefits.

Paperless consists of the following components:

*   **The webserver:** This is pretty much the same as in paperless. It serves
    the administration pages, the API, and the new frontend. This is the main
    tool you'll be using to interact with paperless. You may start the webserver
    with

    .. code:: shell-session

        $ cd /path/to/paperless/src/
        $ gunicorn -c ../gunicorn.conf.py paperless.wsgi

    or by any other means such as Apache ``mod_wsgi``.

*   **The consumer:** This is what watches your consumption folder for documents.
    However, the consumer itself does not really consume your documents.
    Now it notifies a task processor that a new file is ready for consumption.
    I suppose it should be named differently.
    This was also used to check your emails, but that's now done elsewhere as well.

    Start the consumer with the management command ``document_consumer``:

    .. code:: shell-session

        $ cd /path/to/paperless/src/
        $ python3 manage.py document_consumer

    .. _setup-task_processor:

*   **The task processor:** Paperless relies on `Django Q <https://django-q.readthedocs.io/en/latest/>`_
    for doing most of the heavy lifting. This is a task queue that accepts tasks from
    multiple sources and processes these in parallel. It also comes with a scheduler that executes
    certain commands periodically.

    This task processor is responsible for:

    *   Consuming documents. When the consumer finds new documents, it notifies the task processor to
        start a consumption task.
    *   The task processor also performs the consumption of any documents you upload through
        the web interface.
    *   Consuming emails. It periodically checks your configured accounts for new emails and
        notifies the task processor to consume the attachment of an email.
    *   Maintaining the search index and the automatic matching algorithm. These are things that paperless
        needs to do from time to time in order to operate properly.

    This allows paperless to process multiple documents from your consumption folder in parallel! On
    a modern multi core system, this makes the consumption process with full OCR blazingly fast.

    The task processor comes with a built-in admin interface that you can use to check whenever any of the
    tasks fail and inspect the errors (i.e., wrong email credentials, errors during consuming a specific
    file, etc).

    You may start the task processor by executing:

    .. code:: shell-session

        $ cd /path/to/paperless/src/
        $ python3 manage.py qcluster

*   A `redis <https://redis.io/>`_ message broker: This is a really lightweight service that is responsible
    for getting the tasks from the webserver and the consumer to the task scheduler. These run in a different
    process (maybe even on different machines!), and therefore, this is necessary.

*   Optional: A database server. Paperless supports both PostgreSQL and SQLite for storing its data.


Installation
############

You can go multiple routes to setup and run Paperless:

* :ref:`Use the easy install docker script <setup-docker_script>`
* :ref:`Pull the image from Docker Hub <setup-docker_hub>`
* :ref:`Build the Docker image yourself <setup-docker_build>`
* :ref:`Install Paperless directly on your system manually (bare metal) <setup-bare_metal>`
* :ref:`Use ansible to install Paperless on your system automatically (bare metal) <setup-ansible>`

The Docker routes are quick & easy. These are the recommended routes. This configures all the stuff
from the above automatically so that it just works and uses sensible defaults for all configuration options.
Here you find a cheat-sheet for docker beginners: `CLI Basics <https://sehn.tech/post/devops-with-docker/>`_

The bare metal route is complicated to setup but makes it easier
should you want to contribute some code back. You need to configure and
run the above mentioned components yourself.

The ansible route combines benefits of both options:
the setup process is fully automated, reproducible and `idempotent <https://docs.ansible.com/ansible/latest/reference_appendices/glossary.html#Idempotency>`_,
it includes the same sensible defaults, and it simultaneously provides the flexibility of a bare metal installation.

.. _CLI Basics: https://sehn.tech/post/devops-with-docker/
.. _idempotent: https://docs.ansible.com/ansible/latest/reference_appendices/glossary.html#Idempotency

.. _setup-docker_script:

Install Paperless from Docker Hub using the installation script
===============================================================

Paperless provides an interactive installation script. This script will ask you
for a couple configuration options, download and create the necessary configuration files, pull the docker image, start paperless and create your user account. This script essentially
performs all the steps described in :ref:`setup-docker_hub` automatically.

1.  Make sure that docker and docker-compose are installed.
2.  Download and run the installation script:

    .. code:: shell-session

        $ curl -L https://raw.githubusercontent.com/jonaswinkler/paperless-ng/master/install-paperless-ng.sh | bash

.. _setup-docker_hub:

Install Paperless from Docker Hub
=================================

1.  Login with your user and create a folder in your home-directory `mkdir -v ~/paperless-ng` to have a place for your configuration files and consumption directory.

2.  Go to the `/docker/compose directory on the project page <https://github.com/jonaswinkler/paperless-ng/tree/master/docker/compose>`_
    and download one of the `docker-compose.*.yml` files, depending on which database backend you
    want to use. Rename this file to `docker-compose.yml`.
    If you want to enable optional support for Office documents, download a file with `-tika` in the file name.
    Download the ``docker-compose.env`` file and the ``.env`` file as well and store them
    in the same directory.

    .. hint::

        For new installations, it is recommended to use PostgreSQL as the database
        backend.

3.  Install `Docker`_ and `docker-compose`_.

    .. caution::

        If you want to use the included ``docker-compose.*.yml`` file, you
        need to have at least Docker version **17.09.0** and docker-compose
        version **1.17.0**.
        To check do: `docker-compose -v` or `docker -v`

        See the `Docker installation guide`_ on how to install the current
        version of Docker for your operating system or Linux distribution of
        choice. To get the latest version of docker-compose, follow the
        `docker-compose installation guide`_ if your package repository doesn't
        include it.

        .. _Docker installation guide: https://docs.docker.com/engine/installation/
        .. _docker-compose installation guide: https://docs.docker.com/compose/install/

4.  Modify ``docker-compose.yml`` to your preferences. You may want to change the path
    to the consumption directory. Find the line that specifies where
    to mount the consumption directory:

    .. code::

        - ./consume:/usr/src/paperless/consume

    Replace the part BEFORE the colon with a local directory of your choice:

    .. code::

        - /home/jonaswinkler/paperless-inbox:/usr/src/paperless/consume

    Don't change the part after the colon or paperless wont find your documents.

    You may also need to change the default port that the webserver will use
    from the default (8000):

     .. code::

        ports:
          - 8000:8000

    Replace the part BEFORE the colon with a port of your choice:

     .. code::

        ports:
          - 8010:8000

    Don't change the part after the colon or edit other lines that refer to
    port 8000. Modifying the part before the colon will map requests on another
    port to the webserver running on the default port.

5.  Modify ``docker-compose.env``, following the comments in the file. The
    most important change is to set ``USERMAP_UID`` and ``USERMAP_GID``
    to the uid and gid of your user on the host system. Use ``id -u`` and
    ``id -g`` to get these.

    This ensures that
    both the docker container and you on the host machine have write access
    to the consumption directory. If your UID and GID on the host system is
    1000 (the default for the first normal user on most systems), it will
    work out of the box without any modifications. `id "username"` to check.

    .. note::

        You can copy any setting from the file ``paperless.conf.example`` and paste it here.
        Have a look at :ref:`configuration` to see what's available.

    .. caution::

        Some file systems such as NFS network shares don't support file system
        notifications with ``inotify``. When storing the consumption directory
        on such a file system, paperless will not pick up new files
        with the default configuration. You will need to use ``PAPERLESS_CONSUMER_POLLING``,
        which will disable inotify. See :ref:`here <configuration-polling>`.

6.  Run ``docker-compose pull``, followed by ``docker-compose up -d``.
    This will pull the image, create and start the necessary containers.

7.  To be able to login, you will need a super user. To create it, execute the
    following command:

    .. code-block:: shell-session

        $ docker-compose run --rm webserver createsuperuser

    This will prompt you to set a username, an optional e-mail address and
    finally a password (at least 8 characters).

8.  The default ``docker-compose.yml`` exports the webserver on your local port
    8000. If you did not change this, you should now be able to visit your
    Paperless instance at ``http://127.0.0.1:8000`` or your servers IP-Address:8000.
    Use the login credentials you have created with the previous step.

.. _Docker: https://www.docker.com/
.. _docker-compose: https://docs.docker.com/compose/install/

.. _setup-docker_build:

Build the Docker image yourself
===============================

1.  Clone the entire repository of paperless:

    .. code:: shell-session

        git clone https://github.com/jonaswinkler/paperless-ng

    The master branch always reflects the latest stable version.

2.  Copy one of the ``docker/compose/docker-compose.*.yml`` to ``docker-compose.yml`` in the root folder,
    depending on which database backend you want to use. Copy
    ``docker-compose.env`` into the project root as well.

3.  In the ``docker-compose.yml`` file, find the line that instructs docker-compose to pull the paperless image from Docker Hub:

    .. code:: yaml

        webserver:
            image: jonaswinkler/paperless-ng:latest

    and replace it with a line that instructs docker-compose to build the image from the current working directory instead:

    .. code:: yaml

        webserver:
            build: .

4.  Run the ``compile-frontend.sh`` script. This requires ``node`` and ``npm >= v15``.

5.  Follow steps 3 to 8 of :ref:`setup-docker_hub`. When asked to run
    ``docker-compose pull`` to pull the image, do

    .. code:: shell-session

        $ docker-compose build

    instead to build the image.

.. _setup-bare_metal:

Bare Metal Route
================

Paperless runs on linux only. The following procedure has been tested on a minimal
installation of Debian/Buster, which is the current stable release at the time of
writing. Windows is not and will never be supported.

1.  Install dependencies. Paperless requires the following packages.

    *   ``python3`` 3.6, 3.7, 3.8, 3.9
    *   ``python3-pip``
    *   ``python3-dev``

    *   ``fonts-liberation`` for generating thumbnails for plain text files
    *   ``imagemagick`` >= 6 for PDF conversion
    *   ``optipng`` for optimizing thumbnails
    *   ``gnupg`` for handling encrypted documents
    *   ``libpq-dev`` for PostgreSQL
    *   ``libmagic-dev`` for mime type detection
    *   ``mime-support`` for mime type detection

    Use this list for your preferred package management:

    .. code::

        python3 python3-pip python3-dev imagemagick fonts-liberation optipng gnupg libpq-dev libmagic-dev mime-support

    These dependencies are required for OCRmyPDF, which is used for text recognition.

    *   ``unpaper``
    *   ``ghostscript``
    *   ``icc-profiles-free``
    *   ``qpdf``
    *   ``liblept5``
    *   ``libxml2``
    *   ``pngquant``
    *   ``zlib1g``
    *   ``tesseract-ocr`` >= 4.0.0 for OCR
    *   ``tesseract-ocr`` language packs (``tesseract-ocr-eng``, ``tesseract-ocr-deu``, etc)

    Use this list for your preferred package management:

    .. code::

        unpaper ghostscript icc-profiles-free qpdf liblept5 libxml2 pngquant zlib1g tesseract-ocr

    On Raspberry Pi, these libraries are required as well:

    *   ``libatlas-base-dev``
    *   ``libxslt1-dev``

    You will also need ``build-essential``, ``python3-setuptools`` and ``python3-wheel``
    for installing some of the python dependencies.

2.  Install ``redis`` >= 5.0 and configure it to start automatically.

3.  Optional. Install ``postgresql`` and configure a database, user and password for paperless. If you do not wish
    to use PostgreSQL, SQLite is available as well.

4.  Get the release archive from `<https://github.com/jonaswinkler/paperless-ng/releases>`_.
    If you clone the git repo as it is, you also have to compile the front end by yourself.
    Extract the archive to a place from where you wish to execute it, such as ``/opt/paperless``.

5.  Configure paperless. See :ref:`configuration` for details. Edit the included ``paperless.conf`` and adjust the
    settings to your needs. Required settings for getting paperless running are:

    *   ``PAPERLESS_REDIS`` should point to your redis server, such as redis://localhost:6379.
    *   ``PAPERLESS_DBHOST`` should be the hostname on which your PostgreSQL server is running. Do not configure this
        to use SQLite instead. Also configure port, database name, user and password as necessary.
    *   ``PAPERLESS_CONSUMPTION_DIR`` should point to a folder which paperless should watch for documents. You might
        want to have this somewhere else. Likewise, ``PAPERLESS_DATA_DIR`` and ``PAPERLESS_MEDIA_ROOT`` define where
        paperless stores its data. If you like, you can point both to the same directory.
    *   ``PAPERLESS_SECRET_KEY`` should be a random sequence of characters. It's used for authentication. Failure
        to do so allows third parties to forge authentication credentials.

    Many more adjustments can be made to paperless, especially the OCR part. The following options are recommended
    for everyone:

    *   Set ``PAPERLESS_OCR_LANGUAGE`` to the language most of your documents are written in.
    *   Set ``PAPERLESS_TIME_ZONE`` to your local time zone.

6.  Create a system user under which you wish to run paperless.

    .. code:: shell-session

        adduser paperless --system --home /opt/paperless --group

7.  Ensure that these directories exist
    and that the paperless user has write permissions to the following directories:

    *   ``/opt/paperless/media``
    *   ``/opt/paperless/data``
    *   ``/opt/paperless/consume``

    Adjust as necessary if you configured different folders.

8.  Install python requirements from the ``requirements.txt`` file.
    It is up to you if you wish to use a virtual environment or not. First you should update your pip, so it gets the actual packages.

    .. code:: shell-session

        sudo -Hu paperless pip3 install --upgrade pip

    .. code:: shell-session

        sudo -Hu paperless pip3 install -r requirements.txt

    This will install all python dependencies in the home directory of
    the new paperless user.

9.  Go to ``/opt/paperless/src``, and execute the following commands:

    .. code:: bash

        # This creates the database schema.
        sudo -Hu paperless python3 manage.py migrate

        # This creates your first paperless user
        sudo -Hu paperless python3 manage.py createsuperuser

10. Optional: Test that paperless is working by executing

      .. code:: bash

        # This collects static files from paperless and django.
        sudo -Hu paperless python3 manage.py runserver

    and pointing your browser to http://localhost:8000/.

    .. warning::

        This is a development server which should not be used in
        production. It is not audited for security and performance
        is inferior to production ready web servers.

    .. hint::

        This will not start the consumer. Paperless does this in a
        separate process.

11. Setup systemd services to run paperless automatically. You may
    use the service definition files included in the ``scripts`` folder
    as a starting point.

    Paperless needs the ``webserver`` script to run the webserver, the
    ``consumer`` script to watch the input folder, and the ``scheduler``
    script to run tasks such as email checking and document consumption.

    You may need to adjust the path to the ``gunicorn`` executable. This
    will be installed as part of the python dependencies, and is either located
    in the ``bin`` folder of your virtual environment, or in ``~/.local/bin/`` if
    no virtual environment is used.

    These services rely on redis and optionally the database server, but
    don't need to be started in any particular order. The example files
    depend on redis being started. If you use a database server, you should
    add additional dependencies.

    .. caution::

        The included scripts run a ``gunicorn`` standalone server,
        which is fine for running paperless. It does support SSL,
        however, the documentation of GUnicorn states that you should
        use a proxy server in front of gunicorn instead.

        For instructions on how to use nginx for that,
        :ref:`see the instructions below <setup-nginx>`.

12. Optional: Install a samba server and make the consumption folder
    available as a network share.

13. Configure ImageMagick to allow processing of PDF documents. Most distributions have
    this disabled by default, since PDF documents can contain malware. If
    you don't do this, paperless will fall back to ghostscript for certain steps
    such as thumbnail generation.

    Edit ``/etc/ImageMagick-6/policy.xml`` and adjust

    .. code::

        <policy domain="coder" rights="none" pattern="PDF" />

    to

    .. code::

        <policy domain="coder" rights="read|write" pattern="PDF" />

14. Optional: Install the `jbig2enc <https://ocrmypdf.readthedocs.io/en/latest/jbig2.html>`_
    encoder. This will reduce the size of generated PDF documents. You'll most likely need
    to compile this by yourself, because this software has been patented until around 2017 and
    binary packages are not available for most distributions.

.. _setup-ansible:

Install Paperless using ansible
===============================

.. note::

    This role currently only supports Debian 10 Buster and Ubuntu 20.04 Focal or later as target hosts.
		Additionally, only i386 or amd64 based hosts are supported right now, i.e. installation on arm hosts will fail.

1.  Install ansible 2.7+ on the management node.
    This may be the target host paperless-ng is being installed on or any remote host which can access the target host.
    For further details, check the ansible `inventory <https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html>`_ documentation.

    On Debian and Ubuntu, the official repositories should provide a suitable version:

    .. code:: bash

        apt install ansible
        ansible --version

    Alternatively, you can install the most recent ansible release using PyPI:

    .. code:: bash

        python3 -m pip install ansible
        ansible --version

    Make sure your taget hosts are accessible:

    .. code:: sh

        ansible -m ping YourAnsibleTargetHostGoesHere

2.  Install the latest tag of the ansible role using ansible-galaxy

    .. code:: sh

        ansible-galaxy install git+https://github.com/jonaswinkler/paperless-ng.git,ng-1.4.2

3.  Create an ansible ``playbook.yml`` in a directory of your choice:

    .. code:: yaml

        - hosts: YourAnsibleTargetHostGoesHere
          become: yes
          vars_files:
            - vars/paperless-ng.yml
          roles:
            - paperless-ng

    Optional: If you also want to use PostgreSQL on the target system, install and add (for example) the `geerlingguy.postgresql <https://github.com/geerlingguy/ansible-role-postgresql>`_ role:

    .. code:: sh

        ansible-galaxy install geerlingguy.postgresql

    .. code:: yaml

        - hosts: YourAnsibleTargetHostGoesHere
          become: yes
          vars_files:
            - vars/paperless-ng.yml
          roles:
            - geerlingguy.postgresql
            - paperless-ng

    Optional: If you also want to use a reverse proxy on the target system, install and add (for example) the `geerlingguy.nginx <https://github.com/geerlingguy/ansible-role-nginx>`_ role:

    .. code:: sh

        ansible-galaxy install geerlingguy.nginx

    .. code:: yaml

        - hosts: YourAnsibleTargetHostGoesHere
          become: yes
          vars_files:
            - vars/paperless-ng.yml
          roles:
            - geerlingguy.postgresql
            - paperless-ng
            - geerlingguy.nginx

4.  Create ``vars/paperless-ng.yml`` to configure your ansible deployment:

    .. code:: yaml

        paperlessng_secret_key: PleaseGenerateAStrongKeyForThis

        paperlessng_superuser_name: YourUserName
        paperlessng_superuser_email: name@domain.tld
        paperlessng_superuser_password: YourDesiredPasswordUsedForFirstLogin

        paperlessng_ocr_languages:
            - eng
            - deu

    For all of the available options, please check ``ansible/README.md`` and :ref:`configuration`.

    Optional configurations for the above-mentioned PostgreSQL and nginx roles would also go here.

5. Run the ansible playbook from the management node:

    .. code:: sh

        ansible-playbook playbook.yml

    When this step completes successfully, paperless-ng will be available on the target host at ``http://127.0.0.1:8000`` (or the address you configured).

Migration to paperless-ng
#########################

At its core, paperless-ng is still paperless and fully compatible. However, some
things have changed under the hood, so you need to adapt your setup depending on
how you installed paperless.

This setup describes how to update an existing paperless Docker installation.
The important things to keep in mind are as follows:

* Read the :ref:`changelog <paperless_changelog>` and take note of breaking changes.
* You should decide if you want to stick with SQLite or want to migrate your database
  to PostgreSQL. See :ref:`setup-sqlite_to_psql` for details on how to move your data from
  SQLite to PostgreSQL. Both work fine with paperless. However, if you already have a
  database server running for other services, you might as well use it for paperless as well.
* The task scheduler of paperless, which is used to execute periodic tasks
  such as email checking and maintenance, requires a `redis`_ message broker
  instance. The docker-compose route takes care of that.
* The layout of the folder structure for your documents and data remains the
  same, so you can just plug your old docker volumes into paperless-ng and
  expect it to find everything where it should be.

Migration to paperless-ng is then performed in a few simple steps:

1.  Stop paperless.

    .. code:: bash

        $ cd /path/to/current/paperless
        $ docker-compose down

2.  Do a backup for two purposes: If something goes wrong, you still have your
    data. Second, if you don't like paperless-ng, you can switch back to
    paperless.

3.  Download the latest release of paperless-ng. You can either go with the
    docker-compose files from `here <https://github.com/jonaswinkler/paperless-ng/tree/master/docker/compose>`__
    or clone the repository to build the image yourself (see :ref:`above <setup-docker_build>`).
    You can either replace your current paperless folder or put paperless-ng
    in a different location.

    .. caution::

        Paperless-ng includes a ``.env`` file. This will set the
        project name for docker compose to ``paperless``, which will also define the name
        of the volumes by paperless-ng. However, if you experience that paperless-ng
        is not using your old paperless volumes, verify the names of your volumes with

        .. code:: shell-session

            $ docker volume ls | grep _data

        and adjust the project name in the ``.env`` file so that it matches the name
        of the volumes before the ``_data`` part.


4.  Download the ``docker-compose.sqlite.yml`` file to ``docker-compose.yml``.
    If you want to switch to PostgreSQL, do that after you migrated your existing
    SQLite database.

5.  Adjust ``docker-compose.yml`` and ``docker-compose.env`` to your needs.
    See :ref:`setup-docker_hub` for details on which edits are advised.

6.  :ref:`Update paperless. <administration-updating>`

7.  In order to find your existing documents with the new search feature, you need
    to invoke a one-time operation that will create the search index:

    .. code:: shell-session

        $ docker-compose run --rm webserver document_index reindex

    This will migrate your database and create the search index. After that,
    paperless will take care of maintaining the index by itself.

8.  Start paperless-ng.

    .. code:: bash

        $ docker-compose up -d

    This will run paperless in the background and automatically start it on system boot.

9.  Paperless installed a permanent redirect to ``admin/`` in your browser. This
    redirect is still in place and prevents access to the new UI. Clear your
    browsing cache in order to fix this.

10.  Optionally, follow the instructions below to migrate your existing data to PostgreSQL.


.. _setup-sqlite_to_psql:

Moving data from SQLite to PostgreSQL
=====================================

Moving your data from SQLite to PostgreSQL is done via executing a series of django
management commands as below.

.. caution::

    Make sure that your SQLite database is migrated to the latest version.
    Starting paperless will make sure that this is the case. If your try to
    load data from an old database schema in SQLite into a newer database
    schema in PostgreSQL, you will run into trouble.

.. warning::

    On some database fields, PostgreSQL enforces predefined limits on maximum
    length, whereas SQLite does not. The fields in question are the title of documents
    (128 characters), names of document types, tags and correspondents (128 characters),
    and filenames (1024 characters). If you have data in these fields that surpasses these
    limits, migration to PostgreSQL is not possible and will fail with an error.


1.  Stop paperless, if it is running.
2.  Tell paperless to use PostgreSQL:

    a)  With docker, copy the provided ``docker-compose.postgres.yml`` file to
        ``docker-compose.yml``. Remember to adjust the consumption directory,
        if necessary.
    b)  Without docker, configure the database in your ``paperless.conf`` file.
        See :ref:`configuration` for details.

3.  Open a shell and initialize the database:

    a)  With docker, run the following command to open a shell within the paperless
        container:

        .. code:: shell-session

            $ cd /path/to/paperless
            $ docker-compose run --rm webserver /bin/bash

        This will launch the container and initialize the PostgreSQL database.

    b)  Without docker, remember to activate any virtual environment, switch to
        the ``src`` directory and create the database schema:

        .. code:: shell-session

            $ cd /path/to/paperless/src
            $ python3 manage.py migrate

        This will not copy any data yet.

4.  Dump your data from SQLite:

    .. code:: shell-session

        $ python3 manage.py dumpdata --database=sqlite --exclude=contenttypes --exclude=auth.Permission > data.json

5.  Load your data into PostgreSQL:

    .. code:: shell-session

        $ python3 manage.py loaddata data.json

6.  If operating inside Docker, you may exit the shell now.

    .. code:: shell-session

        $ exit

7.  Start paperless.


Moving back to paperless
========================

Lets say you migrated to Paperless-ng and used it for a while, but decided that
you don't like it and want to move back (If you do, send me a mail about what
part you didn't like!), you can totally do that with a few simple steps.

Paperless-ng modified the database schema slightly, however, these changes can
be reverted while keeping your current data, so that your current data will
be compatible with original Paperless.

Execute this:

.. code:: shell-session

    $ cd /path/to/paperless
    $ docker-compose run --rm webserver migrate documents 0023

Or without docker:

.. code:: shell-session

    $ cd /path/to/paperless/src
    $ python3 manage.py migrate documents 0023

After that, you need to clear your cookies (Paperless-ng comes with updated
dependencies that do cookie-processing differently) and probably your cache
as well.

.. _setup-less_powerful_devices:


Considerations for less powerful devices
########################################

Paperless runs on Raspberry Pi. However, some things are rather slow on the Pi and
configuring some options in paperless can help improve performance immensely:

*   Stick with SQLite to save some resources.
*   Consider setting ``PAPERLESS_OCR_PAGES`` to 1, so that paperless will only OCR
    the first page of your documents. In most cases, this page contains enough
    information to be able to find it.
*   ``PAPERLESS_TASK_WORKERS`` and ``PAPERLESS_THREADS_PER_WORKER`` are configured
    to use all cores. The Raspberry Pi models 3 and up have 4 cores, meaning that
    paperless will use 2 workers and 2 threads per worker. This may result in
    sluggish response times during consumption, so you might want to lower these
    settings (example: 2 workers and 1 thread to always have some computing power
    left for other tasks).
*   Keep ``PAPERLESS_OCR_MODE`` at its default value ``skip`` and consider OCR'ing
    your documents before feeding them into paperless. Some scanners are able to
    do this! You might want to even specify ``skip_noarchive`` to skip archive
    file generation for already ocr'ed documents entirely.
*   If you want to perform OCR on the the device, consider using ``PAPERLESS_OCR_CLEAN=none``.
    This will speed up OCR times and use less memory at the expense of slightly worse
    OCR results.
*   Set ``PAPERLESS_OPTIMIZE_THUMBNAILS`` to 'false' if you want faster consumption
    times. Thumbnails will be about 20% larger.
*   If using docker, consider setting ``PAPERLESS_WEBSERVER_WORKERS`` to
    1. This will save some memory.

For details, refer to :ref:`configuration`.

.. note::

    Updating the :ref:`automatic matching algorithm <advanced-automatic_matching>`
    takes quite a bit of time. However, the update mechanism checks if your
    data has changed before doing the heavy lifting. If you experience the
    algorithm taking too much cpu time, consider changing the schedule in the
    admin interface to daily. You can also manually invoke the task
    by changing the date and time of the next run to today/now.

    The actual matching of the algorithm is fast and works on Raspberry Pi as
    well as on any other device.

.. _redis: https://redis.io/


.. _setup-nginx:

Using nginx as a reverse proxy
##############################

If you want to expose paperless to the internet, you should hide it behind a
reverse proxy with SSL enabled.

In addition to the usual configuration for SSL,
the following configuration is required for paperless to operate:

.. code:: nginx

    http {

        # Adjust as required. This is the maximum size for file uploads.
        # The default value 1M might be a little too small.
        client_max_body_size 10M;

        server {

            location / {

                # Adjust host and port as required.
                proxy_pass http://localhost:8000/;

                # These configuration options are required for WebSockets to work.
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";

                proxy_redirect off;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Host $server_name;
            }
        }
    }

Also read `this <https://channels.readthedocs.io/en/stable/deploying.html#nginx-supervisor-ubuntu>`__, towards the end of the section.
