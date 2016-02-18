.. _migrating:

Migrating, Updates, and Backups
===============================

As *Paperless* is still under active development, there's a lot that can change
as software updates roll out.  The thing you just need to remember for all of
this is that for the most part, **the database is expendable** so long as you
have your files.  This is because the file name of the exported files includes
the name of the sender, the title, and the tags (if any) on each file.


.. _migrating-updates:

Updates
-------

For the most part, all you have to do to update *Paperless* is run ``git pull``
on the directory containing the project files, and then use Django's ``migrate``
command to execute any database schema updates that might have been rolled in
as part of the update:

.. code:: bash

    $ cd /path/to/project
    $ git pull
    $ cd src
    $ ./manage.py migrate

Note that it's possible (even likely) that while ``git pull`` may update some
files, the ``migrate`` step may not update anything.  This is totally normal.

If you are :ref:`using Docker <setup-installation-docker>` the update process
requires only one additional step:

.. code-block:: shell-session

    $ cd /path/to/project
    $ git pull
    $ docker build -t paperless .
    $ docker-compose up -d
    $ docker-compose run --rm webserver migrate

If ``git pull`` doesn't report any changes, there is no need to continue with
the remaining steps.


.. _migrating-backup:

Backing Up
----------

So you're bored of this whole project, or you want to make a remote backup of
the unencrypted files for whatever reason.  This is easy to do, simply use the
:ref:`exporter <utilities-exporter>` to dump your documents out into an
arbitrary directory.

Additionally however, you'll need to back up the tags themselves.  The file
names contain the tag names, but you still need to define the tags and their
matching algorithms in the database for things to work properly.  We do this
with Django's ``dumpdata`` command, which produces JSON output.

.. code:: bash

    $ cd /path/to/project
    $ cd src
    $ ./manage.py document_export /path/to/arbitrary/place/
    $ ./manage.py dumpdata documents.Tag > /path/to/arbitrary/place/tags.json

If you are :ref:`using Docker <setup-installation-docker>`, exporting your tags
as JSON is almost as easy:

.. code-block:: shell-session

    $ docker-compose run --rm webserver dumpdata documents.Tag > /path/to/arbitrary/place/tags.json

Exporting the documents though is a little more involved, since docker-compose
doesn't support mounting additional volumes with the ``run`` command. You have
three general options:

1. Use the consumption directory if you happen to already have it mounted to a
   host directory.

   .. code-block:: console

       $ # Stop the consumer so that it doesn't consume the exported documents
       $ docker-compose stop consumer
       $ # Export into the consumption directory
       $ docker-compose run --rm consumer document_exporter /consume

2. Add another volume to ``docker-compose.yml`` for exports and use
   ``docker-compose run``:

   .. code-block:: diff

      diff --git a/docker-compose.yml b/docker-compose.yml
      --- a/docker-compose.yml
      +++ b/docker-compose.yml
      @@ -17,9 +18,8 @@ services:
               volumes:
                   - paperless-data:/usr/src/paperless/data
                   - paperless-media:/usr/src/paperless/media
                   - /consume
      +            - /path/to/arbitrary/place:/export

   .. code-block:: shell-session

       $ docker-compose run --rm consumer document_exporter /export

3. Use ``docker run`` directly, supplying the necessary commandline options:

   .. code-block:: shell-session

       $ # Identify your containers
       $ docker-compose ps
               Name                       Command                State     Ports
       -------------------------------------------------------------------------
       paperless_consumer_1    /sbin/docker-entrypoint.sh ...   Exit 0
       paperless_webserver_1   /sbin/docker-entrypoint.sh ...   Exit 0

       $ # Make sure to replace your passphrase and remove or adapt the id mapping
       $ docker run --rm \
           --volumes-from paperless_data_1 \
           --volume /path/to/arbitrary/place:/export \
           -e PAPERLESS_PASSPHRASE=YOUR_PASSPHRASE \
           -e USERMAP_UID=1000 -e USERMAP_GID=1000 \
           paperless document_exporter /export


.. _migrating-restoring:

Restoring
---------

Restoring your data is just as easy, since nearly all of your data exists either
in the file names, or in the contents of the files themselves.  You just need to
create an empty database (just follow the
:ref:`installation instructions <setup-installation>` again) and then import the
``tags.json`` file you created as part of your backup.  Lastly, copy your
exported documents into the consumption directory and start up the consumer.

.. code:: bash

    $ cd /path/to/project
    $ rm data/db.sqlite3  # Delete the database
    $ cd src
    $ ./manage.py migrate  # Create the database
    $ ./manage.py createsuperuser
    $ ./manage.py loaddata /path/to/arbitrary/place/tags.json
    $ cp /path/to/exported/docs/* /path/to/consumption/dir/
    $ ./manage.py document_consumer

Importing your data if you are :ref:`using Docker <setup-installation-docker>`
is almost as simple:

.. code-block:: shell-session

    $ # Stop and remove your current containers
    $ docker-compose stop
    $ docker-compose rm -f

    $ # Recreate them, add the superuser
    $ docker-compose up -d
    $ docker-compose run --rm webserver createsuperuser

    $ # Load the tags
    $ cat /path/to/arbitrary/place/tags.json | docker-compose run --rm webserver loaddata_stdin -

    $ # Load your exported documents into the consumption directory
    $ # (How you do this highly depends on how you have set this up)
    $ cp /path/to/exported/docs/* /path/to/mounted/consumption/dir/

After loading the documents into the consumption directory the consumer will
immediately start consuming the documents.
