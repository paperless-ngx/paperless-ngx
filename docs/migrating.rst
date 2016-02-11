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

