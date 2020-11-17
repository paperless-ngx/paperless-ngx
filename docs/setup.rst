
*****
Setup
*****

Download
########

Go to the project page on GitHub and download the
`latest release <https://github.com/jonaswinkler/paperless-ng/releases>`_.
There are multiple options available.

*   Download the docker-compose files if you want to pull paperless from
    Docker Hub.

*   Download the archive and extract it if you want to build the docker image
    yourself or want to install paperless without docker.

.. hint::

    In contrast to paperless, the recommended way to get and update paperless-ng
    is not to pull the entire git repository. Paperless-ng includes artifacts
    that need to be compiled, and that's already done for you in the release.


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
    tasks fail and inspect the errors.

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

        If you want to use the included ``docker-compose.yml.example`` file, you
        need to have at least Docker version **17.09.0** and docker-compose
        version **1.17.0**.

        See the `Docker installation guide`_ on how to install the current
        version of Docker for your operating system or Linux distribution of
        choice. To get an up-to-date version of docker-compose, follow the
        `docker-compose installation guide`_ if your package repository doesn't
        include it.

        .. _Docker installation guide: https://docs.docker.com/engine/installation/
        .. _docker-compose installation guide: https://docs.docker.com/compose/install/

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
* It is recommended to use postgresql as the database now. The docker-compose
  deployment will automatically create a postgresql instance and instruct
  paperless to use it. This means that if you use the docker-compose script
  with your current paperless media and data volumes and used the default
  sqlite database, **it will not use your sqlite database and it may seem
  as if your documents are gone**. You may use the provided
  ``docker-compose.sqlite.yml`` script instead, which does not use postgresql. See
  :ref:`setup-sqlite_to_psql` for details on how to move your data from
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
    in a different location. Paperless-ng will use the same docker volumes
    as paperless.

4.  Adjust ``docker-compose.yml`` and
    ``docker-compose.env`` to your needs.
    See `docker route`_ for details on which edits are required.

5.  Update paperless. See :ref:`administration-updating` for details.

6.  Start paperless-ng.

    .. code:: bash

        $ docker-compose up -d

7.  Paperless installed a permanent redirect to ``admin/`` in your browser. This
    redirect is still in place and prevents access to the new UI. Clear 
    everything related to paperless in your browsers data in order to fix
    this issue.

.. _setup-sqlite_to_psql:

Moving data from sqlite to postgresql
=====================================

.. warning::

    TBD.

.. _redis: https://redis.io/
