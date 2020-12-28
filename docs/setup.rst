
*****
Setup
*****

Download
########

Go to the project page on GitHub and download the
`latest release <https://github.com/jonaswinkler/paperless-ng/releases>`_.
There are multiple options available.

*   Download the dockerfiles archive if you want to pull paperless from
    Docker Hub.

*   Download the dist archive and extract it if you want to build the docker image
    yourself or want to install paperless without docker.

.. hint::

    In contrast to paperless, the recommended way to get and update paperless-ng
    is not to pull the entire git repository. Paperless-ng includes artifacts
    that need to be compiled, and that's already done for you in the release.

.. admonition:: Want to try out paperless-ng before migrating?

    The release contains a file ``.env`` which sets the docker-compose project
    name to "paperless", which is the same as before and instructs docker-compose
    to reuse and upgrade your paperless volumes.

    Just rename the project name in that file to anything else and docker-compose
    will create fresh volumes for you!


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
        $ pipenv run gunicorn -c /usr/src/paperless/gunicorn.conf.py -b 0.0.0.0:8000 paperless.wsgi

    or by any other means such as Apache ``mod_wsgi``.

*   **The consumer:** This is what watches your consumption folder for documents.
    However, the consumer itself does not consume really consume your documents anymore.
    It rather notifies a task processor that a new file is ready for consumption.
    I suppose it should be named differently.
    This also used to check your emails, but that's now gone elsewhere as well.

    Start the consumer with the management command ``document_consumer``:

    .. code:: shell-session

        $ cd /path/to/paperless/src/
        $ pipenv run python3 manage.py document_consumer

    .. _setup-task_processor:

*   **The task processor:** Paperless relies on `Django Q <https://django-q.readthedocs.io/en/latest/>`_
    for doing much of the heavy lifting. This is a task queue that accepts tasks from
    multiple sources and processes tasks in parallel. It also comes with a scheduler that executes
    certain commands periodically.

    This task processor is responsible for:

    *   Consuming documents. When the consumer finds new documents, it notifies the task processor to
        start a consumption task.
    *   Consuming emails. It periodically checks your configured accounts for new mails and
        produces consumption tasks for any documents it finds.
    *   The task processor also performs the consumption of any documents you upload through
        the web interface.
    *   Maintain the search index and the automatic matching algorithm. These are things that paperless
        needs to do from time to time in order to operate properly.

    This allows paperless to process multiple documents from your consumption folder in parallel! On
    a modern multi core system, consumption with full ocr is blazing fast.

    The task processor comes with a built-in admin interface that you can use to see whenever any of the
    tasks fail and inspect the errors (i.e., wrong email credentials, errors during consuming a specific
    file, etc).

    You may start the task processor by executing:

    .. code:: shell-session

        $ cd /path/to/paperless/src/
        $ pipenv run python3 manage.py qcluster

*   A `redis <https://redis.io/>`_ message broker: This is a really lightweight service that is responsible
    for getting the tasks from the webserver and consumer to the task scheduler. These run in different
    processes (maybe even on different machines!), and therefore, this is necessary.

*   Optional: A database server. Paperless supports both PostgreSQL and SQLite for storing its data.


Installation
############

You can go multiple routes with setting up and running Paperless:

* The `docker route`_
* The `bare metal route`_

The `docker route`_ is quick & easy. This is the recommended route. This configures all the stuff
from above automatically so that it just works and uses sensible defaults for all configuration options.

The `bare metal route`_ is more complicated to setup but makes it easier
should you want to contribute some code back. You need to configure and
run the above mentioned components yourself.

.. _setup-docker_route:

Docker Route
============

1.  Install `Docker`_ and `docker-compose`_. [#compose]_

    .. caution::

        If you want to use the included ``docker-compose.*.yml`` file, you
        need to have at least Docker version **17.09.0** and docker-compose
        version **1.17.0**.

        See the `Docker installation guide`_ on how to install the current
        version of Docker for your operating system or Linux distribution of
        choice. To get an up-to-date version of docker-compose, follow the
        `docker-compose installation guide`_ if your package repository doesn't
        include it.

        .. _Docker installation guide: https://docs.docker.com/engine/installation/
        .. _docker-compose installation guide: https://docs.docker.com/compose/install/

2.  Copy either ``docker-compose.sqlite.yml`` or ``docker-compose.postgres.yml`` to
    ``docker-compose.yml``, depending on which database backend you want to use.

    .. hint::

        For new installations, it is recommended to use PostgreSQL as the database
        backend.

2.  Modify ``docker-compose.yml`` to your preferences. You may want to change the path
    to the consumption directory in this file. Find the line that specifies where
    to mount the consumption directory:

    .. code::

        - ./consume:/usr/src/paperless/consume

    Replace the part BEFORE the colon with a local directory of your choice:

    .. code::

        - /home/jonaswinkler/paperless-inbox:/usr/src/paperless/consume

    Don't change the part after the colon or paperless wont find your documents.


3.  Modify ``docker-compose.env``, following the comments in the file. The
    most important change is to set ``USERMAP_UID`` and ``USERMAP_GID``
    to the uid and gid of your user on the host system. This ensures that
    both the docker container and you on the host machine have write access
    to the consumption directory. If your UID and GID on the host system is
    1000 (the default for the first normal user on most systems), it will
    work out of the box without any modifications.

    .. note::

        You can use any settings from the file ``paperless.conf`` in this file.
        Have a look at :ref:`configuration` to see whats available.

4.  Run ``docker-compose up -d``. This will create and start the necessary
    containers. This will also build the image of paperless if you grabbed the
    source archive.

5.  To be able to login, you will need a super user. To create it, execute the
    following command:

    .. code-block:: shell-session

        $ docker-compose run --rm webserver createsuperuser

    This will prompt you to set a username, an optional e-mail address and
    finally a password.

6.  The default ``docker-compose.yml`` exports the webserver on your local port
    8000. If you haven't adapted this, you should now be able to visit your
    Paperless instance at ``http://127.0.0.1:8000``. You can login with the
    user and password you just created.

.. _Docker: https://www.docker.com/
.. _docker-compose: https://docs.docker.com/compose/install/

.. [#compose] You of course don't have to use docker-compose, but it
   simplifies deployment immensely. If you know your way around Docker, feel
   free to tinker around without using compose!

.. _`setup-bare_metal`:

Bare Metal Route
================

Paperless runs on linux only. The following procedure has been tested on a minimal
installation of Debian/Buster, which is the current stable release at the time of
writing. Windows is not and will never be supported.

1.  Install dependencies. Paperless requires the following packages.

    *   ``python3`` 3.6, 3.7, 3.8 (3.9 is untested).
    *   ``python3-pip``, optionally ``pipenv`` for package installation
    *   ``python3-dev``

    *   ``fonts-liberation`` for generating thumbnails for plain text files
    *   ``imagemagick`` >= 6 for PDF conversion
    *   ``optipng`` for optimizing thumbnails
    *   ``gnupg`` for handling encrypted documents
    *   ``libpoppler-cpp-dev`` for PDF to text conversion
    *   ``libmagic-dev`` for mime type detection
    *   ``libpq-dev`` for PostgreSQL

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

    You will also need ``build-essential``, ``python3-setuptools`` and ``python3-wheel``
    for installing some of the python dependencies.

2.  Install ``redis`` >= 5.0 and configure it to start automatically.

3.  Optional. Install ``postgresql`` and configure a database, user and password for paperless. If you do not wish
    to use PostgreSQL, SQLite is avialable as well.

4.  Get the release archive. If you pull the git repo as it is, you also have to compile the front end by yourself.
    Extract the frontend to a place from where you wish to execute it, such as ``/opt/paperless``.

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

6.  Setup permissions. Create a system users under which you wish to run paperless. Ensure that these directories exist
    and that the user has write permissions to the following directories
    
    *   ``/opt/paperless/media``
    *   ``/opt/paperless/data``
    *   ``/opt/paperless/consume``

    Adjust as necessary if you configured different folders.

7.  Install python requirements. Paperless comes with both Pipfiles for ``pipenv`` as well as with a ``requirements.txt``.
    Both will install exactly the same requirements. It is up to you if you wish to use a virtual environment or not.

8.  Go to ``/opt/paperless/src``, and execute the following commands:

    .. code:: bash

        # This collects static files from paperless and django.
        python3 manage.py collectstatic --clear --no-input
        
        # This creates the database schema.
        python3 manage.py migrate

        # This creates your first paperless user
        python3 manage.py createsuperuser

9.  Optional: Test that paperless is working by executing

      .. code:: bash

        # This collects static files from paperless and django.
        python3 manage.py runserver
    
    and pointing your browser to http://localhost:8000/.

    .. warning::

        This is a development server which should not be used in
        production.

    .. hint::

        This will not start the consumer. Paperless does this in a
        separate process.

10. Setup systemd services to run paperless automatically. You may
    use the service definition files included in the ``scripts`` folder
    as a starting point.

    Paperless needs the ``webserver`` script to run the webserver, the
    ``consumer`` script to watch the input folder, and the ``scheduler``
    script to run tasks such as email checking and document consumption.

    These services rely on redis and optionally the database server, but
    don't need to be started in any particular order. The example files
    depend on redis being started. If you use a database server, you should
    add additinal dependencies.

    .. hint::

        You may optionally set up your preferred web server to serve
        paperless as a wsgi application directly instead of running the
        ``webserver`` service. The module containing the wsgi application
        is named ``paperless.wsgi``.

    .. caution::

        The included scripts run a ``gunicorn`` standalone server,
        which is fine for running paperless. It does support SSL,
        however, the documentation of GUnicorn states that you should
        use a proxy server in front of gunicorn instead.

11. Optional: Install a samba server and make the consumption folder
    available as a network share.

12. Configure ImageMagick to allow processing of PDF documents. Most distributions have
    this disabled by default, since PDF documents can contain malware. If
    you don't do this, paperless will fall back to ghostscript for certain steps
    such as thumbnail generation.

    Edit ``/etc/ImageMagick-6/policy.xml`` and adjust

    .. code::

        <policy domain="coder" rights="none" pattern="PDF" />
    
    to

    .. code::

        <policy domain="coder" rights="read|write" pattern="PDF" />

Migration to paperless-ng
#########################

At its core, paperless-ng is still paperless and fully compatible. However, some
things have changed under the hood, so you need to adapt your setup depending on
how you installed paperless. The important things to keep in mind are as follows.

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
    docker-compose files or use the archive to build the image yourself.
    You can either replace your current paperless folder or put paperless-ng
    in a different location.

    .. caution::

        The release include a ``.env`` file. This will set the
        project name for docker compose to ``paperless`` so that paperless-ng will
        automatically reuse your existing paperless volumes. When you start it, it
        will migrate your existing data. After that, your old paperless installation
        will be incompatible with the migrated volumes.

4.  Copy the ``docker-compose.sqlite.yml`` file to ``docker-compose.yml``.
    If you want to switch to PostgreSQL, do that after you migrated your existing
    SQLite database.

5.  Adjust ``docker-compose.yml`` and
    ``docker-compose.env`` to your needs.
    See `docker route`_ for details on which edits are advised.

6.  Since ``docker-compose`` would just use the the old paperless image, we need to
    manually build a new image:

    .. code:: shell-session

        $ docker-compose build

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
    redirect is still in place and prevents access to the new UI. Clear
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
    
    b)  Without docker, open a shell in your virtual environment, switch to
        the ``src`` directory and create the database schema:

        .. code:: shell-session

            $ cd /path/to/paperless
            $ pipenv shell
            $ cd src
            $ python3 manage.py migrate
        
        This will not copy any data yet.

4.  Dump your data from SQLite:

    .. code:: shell-session

        $ python3 manage.py dumpdata --database=sqlite --exclude=contenttypes --exclude=auth.Permission > data.json
    
5.  Load your data into PostgreSQL:

    .. code:: shell-session

        $ python3 manage.py loaddata data.json

6.  Exit the shell.

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
    the first page of your documents.
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
*   Set ``PAPERLESS_OPTIMIZE_THUMBNAILS`` to 'false' if you want faster consumption
    times. Thumbnails will be about 20% larger.

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
