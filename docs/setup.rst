
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
    a modern multicore system, consumption with full ocr is blazing fast.

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

*   A database server. Paperless supports PostgreSQL and sqlite for storing its data. However, with the
    added concurrency, it is strongly advised to use PostgreSQL, as sqlite has its limits in that regard.


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

        For new installations, it is recommended to use postgresql as the database
        backend. This is due to the increased amount of concurrency in paperless-ng.

2.  Modify ``docker-compose.yml`` to your preferences. You should change the path
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


Bare Metal Route
================

.. warning::

    TBD. User docker for now.

Migration to paperless-ng
#########################

At its core, paperless-ng is still paperless and fully compatible. However, some
things have changed under the hood, so you need to adapt your setup depending on
how you installed paperless. The important things to keep in mind are as follows.

* Read the :ref:`changelog <paperless_changelog>` and take note of breaking changes.
* It is recommended to use postgresql as the database now. If you want to continue
  using SQLite, which is the default of paperless, use ``docker-compose.sqlite.yml``.
  See :ref:`setup-sqlite_to_psql` for details on how to move your data from
  sqlite to postgres.
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
    If you want to migrate to PostgreSQL, do that after you migrated your existing
    SQLite database.

5.  Adjust ``docker-compose.yml`` and
    ``docker-compose.env`` to your needs.
    See `docker route`_ for details on which edits are advised.

6.  Start paperless-ng.

    .. code:: bash

        $ docker-compose up

    If you see everything working (you should see some migrations getting
    applied, for instance), you can gracefully stop paperless-ng with Ctrl-C
    and then start paperless-ng as usual with

    .. code:: bash

        $ docker-compose up -d

    This will run paperless in the background and automatically start it on system boot.

7.  Paperless installed a permanent redirect to ``admin/`` in your browser. This
    redirect is still in place and prevents access to the new UI. Clear
    browsing cache in order to fix this.

8.  Optionally, follow the instructions below to migrate your existing data to PostgreSQL.


.. _setup-sqlite_to_psql:

Moving data from SQLite to PostgreSQL
=====================================

Moving your data from SQLite to PostgreSQL is done via executing a series of django
management commands as below.

.. caution::

    Make sure that your sqlite database is migrated to the latest version.
    Starting paperless will make sure that this is the case. If your try to
    load data from an old database schema in SQLite into a newer database
    schema in PostgreSQL, you will run into trouble.

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
        
        This will lauch the container and initialize the PostgreSQL database.
    
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


.. _redis: https://redis.io/
