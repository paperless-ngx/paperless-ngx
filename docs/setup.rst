
*****
Setup
*****

Download
########

The source is currently only available via GitHub, so grab it from there,
by using ``git``:

.. code:: bash

    $ git clone https://github.com/jonaswinkler/paperless-ng.git
    $ cd paperless

Installation
############

You can go multiple routes with setting up and running Paperless:

* The `docker route`_
* The `bare metal route`_

The recommended setup route is docker, since it takes care of all dependencies
for you.

The `docker route`_ is quick & easy.

The `bare metal route`_ is more complicated to setup but makes it easier
should you want to contribute some code back.

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

2.  Create a copy of ``docker-compose.yml.example`` as ``docker-compose.yml``
    and a copy of ``docker-compose.env.example`` as ``docker-compose.env``.
    You'll be editing both these files: taking a copy ensures that you can
    ``git pull`` to receive updates without risking merge conflicts with your
    modified versions of the configuration files.
3.  Modify ``docker-compose.yml`` to your preferences. You should change the path
    to the consumption directory in this file. Find the line that specifies where
    to mount the consumption directory:

    .. code::
    
        - ./consume:/usr/src/paperless/consume
    
    Replace the part BEFORE the colon with a local directory of your choice:

    .. code::

        - /home/jonaswinkler/paperless-inbox:/usr/src/paperless/consume
    
    Don't change the part after the colon or paperless wont find your documents.


4.  Modify ``docker-compose.env``, following the comments in the file. The
    most important change is to set ``USERMAP_UID`` and ``USERMAP_GID``
    to the uid and gid of your user on the host system. This ensures that
    both the docker container and you on the host machine have write access
    to the consumption directory. If your UID and GID on the host system is
    1000 (the default for the first normal user on most systems), it will
    work out of the box without any modifications.

5. Run ``docker-compose up -d``. This will create and start the necessary
   containers.

6.  To be able to login, you will need a super user. To create it, execute the
    following command:

    .. code-block:: shell-session

        $ docker-compose run --rm webserver createsuperuser

    This will prompt you to set a username, an optional e-mail address and
    finally a password.

7.  The default ``docker-compose.yml`` exports the webserver on your local port
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
  ``docker-compose.yml.sqlite.example`` script, which does not use postgresql.
* The task scheduler of paperless, which is used to execute periodic tasks
  such as email checking and maintenance, requires a `redis`_ message broker
  instance. The docker-compose route takes care of that.
* The layout of the folder structure for your documents and data remains the
  same.
* The frontend needs to be built from source. The docker image takes care of
  that.

Migration to paperless-ng is then performed in a few simple steps:

1.  Do a backup for two purposes: If something goes wrong, you still have your
    data. Second, if you don't like paperless-ng, you can switch back to
    paperless.

2.  Replace the paperless source with paperless-ng. If you're using git, this
    is done by:

    .. code:: bash

        $ git remote set-url origin https://github.com/jonaswinkler/paperless-ng
        $ git pull

3.  If you are using docker, copy ``docker-compose.yml.example`` to
    ``docker-compose.yml`` and ``docker-compose.env.example`` to
    ``docker-compose.env``. Make adjustments to these files as necessary.
    See `docker route`_ for details.

4.  Update paperless. See :ref:`administration-updating` for details.

5.  Start paperless-ng.

    .. code:: bash

        $ docker-compose up
        
    This will also migrate your database as usual. Verify by inspecting the
    output that the migration was successfully executed. CTRL-C will then
    gracefully stop the container. After that, you can start paperless-ng as
    usuall with 

    .. code:: bash

        $ docker-compose up -d

6.  Paperless installed a permanent redirect to ``admin/`` in your browser. This
    redirect is still in place and prevents access to the new UI. Clear 
    everything related to paperless in your browsers data in order to fix
    this issue.

Moving data from sqlite to postgresql
=====================================

.. warning::

    TBD.

  .. _redis: https://redis.io/
