.. _migrating:

Migrating, Updates, and Backups
===============================

As Paperless is still under active development, there's a lot that can change
as software updates roll out.  You should backup often, so if anything goes
wrong during an update, you at least have a means of restoring to something
usable.  Thankfully, there are automated ways of backing up, restoring, and
updating the software.


.. _migrating-backup:

Backing Up
----------

So you're bored of this whole project, or you want to make a remote backup of
your files for whatever reason.  This is easy to do, simply use the
:ref:`exporter <utilities-exporter>` to dump your documents and database out
into an arbitrary directory.


.. _migrating-restoring:

Restoring
---------

Restoring your data is just as easy, since nearly all of your data exists either
in the file names, or in the contents of the files themselves.  You just need to
create an empty database (just follow the
:ref:`installation instructions <setup-installation>` again) and then import the
``tags.json`` file you created as part of your backup.  Lastly, copy your
exported documents into the consumption directory and start up the consumer.

.. code-block:: shell-session

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

    # Stop and remove your current containers
    $ docker-compose stop
    $ docker-compose rm -f

    # Recreate them, add the superuser
    $ docker-compose up -d
    $ docker-compose run --rm webserver createsuperuser

    # Load the tags
    $ cat /path/to/arbitrary/place/tags.json | docker-compose run --rm webserver loaddata_stdin -

    # Load your exported documents into the consumption directory
    # (How you do this highly depends on how you have set this up)
    $ cp /path/to/exported/docs/* /path/to/mounted/consumption/dir/

After loading the documents into the consumption directory the consumer will
immediately start consuming the documents.


.. _migrating-updates:

Updates
-------

For the most part, all you have to do to update Paperless is run ``git pull``
on the directory containing the project files, and then use Django's
``migrate`` command to execute any database schema updates that might have been
rolled in as part of the update:

.. code-block:: shell-session

    $ cd /path/to/project
    $ git pull
    $ pip install -r requirements.txt
    $ cd src
    $ ./manage.py migrate

Note that it's possible (even likely) that while ``git pull`` may update some
files, the ``migrate`` step may not update anything.  This is totally normal.

Additionally, as new features are added, the ability to control those features
is typically added by way of an environment variable set in ``paperless.conf``.
You may want to take a look at the ``paperless.conf.example`` file to see if
there's anything new in there compared to what you've got in ``/etc``.

If you are :ref:`using Docker <setup-installation-docker>` the update process
is similar:

.. code-block:: shell-session

    $ cd /path/to/project
    $ git pull
    $ docker build -t paperless .
    $ docker-compose run --rm consumer migrate
    $ docker-compose up -d

If ``git pull`` doesn't report any changes, there is no need to continue with
the remaining steps.
