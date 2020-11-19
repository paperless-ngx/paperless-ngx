
**************
Administration
**************

.. _administration-backup:

Making backups
##############

Multiple options exist for making backups of your paperless instance,
depending on how you installed paperless.

Before making backups, make sure that paperless is not running.

Options available to any installation of paperless:

*   Use the :ref:`document exporter <utilities-exporter>`.
    The document exporter exports all your documents, thumbnails and
    metadata to a specific folder. You may import your documents into a
    fresh instance of paperless again or store your documents in another
    DMS with this export.

Options available to docker installations:

*   Backup the docker volumes. These usually reside within
    ``/var/lib/docker/volumes`` on the host and you need to be root in order
    to access them.

    Paperless uses 3 volumes:

    *   ``paperless_media``: This is where your documents are stored.
    *   ``paperless_data``: This is where auxilliary data is stored. This
        folder also contains the SQLite database, if you use it.
    *   ``paperless_pgdata``: Exists only if you use PostgreSQL and contains
        the database.

Options available to bare-metal and non-docker installations:

*   Backup the entire paperless folder. This ensures that if your paperless instance
    crashes at some point or your disk fails, you can simply copy the folder back
    into place and it works.

    When using PostgreSQL, you'll also have to backup the database.

.. _migrating-restoring:

Restoring
=========




.. _administration-updating:

Updating paperless
##################

If a new release of paperless-ng is available, upgrading depends on how you
installed paperless-ng in the first place. The releases are available at
`release page <https://github.com/jonaswinkler/paperless-ng/releases>`_.

First of all, ensure that paperless is stopped.

.. code:: shell-session

    $ cd /path/to/paperless
    $ docker-compose down

After that, :ref:`make a backup <administration-backup>`.

A.  If you used the docker-compose file, simply download the files of the new release,
    adjust the settings in the files (i.e., the path to your consumption directory),
    and replace your existing docker-compose files. Then start paperless as usual,
    which will pull the new image, and update your database, if necessary:

    .. code:: shell-session

        $ cd /path/to/paperless
        $ docker-compose up

    If you see everything working, you can start paperless-ng with "-d" to have it
    run in the background.

    .. hint::

        The released docker-compose files specify exact versions to be pulled from the hub.
        This is to ensure that if the docker-compose files should change at some point
        (i.e., services updates/configured differently), you wont run into trouble due to
        docker pulling the ``latest`` image and running it in an older environment.
        
B.  If you built the image yourself, grab the new archive and replace your current
    paperless folder with the new contents.

    After that, make the necessary adjustments to the docker-compose.yml (i.e.,
    adjust your consumption directory).

    Build and start the new image with:

    .. code:: shell-session

        $ cd /path/to/paperless
        $ docker-compose build
        $ docker-compose up

    If you see everything working, you can start paperless-ng with "-d" to have it
    run in the background.

.. hint::

    You can usually keep your ``docker-compose.env`` file, since this file will
    never include mandantory configuration options. However, it is worth checking
    out the new version of this file, since it might have new recommendations
    on what to configure.


Updating paperless without docker
=================================

After grabbing the new release and unpacking the contents, do the following:

1.  Update python requirements. Paperless uses
    `Pipenv`_ for managing dependencies:

    .. code:: shell-session

        $ pip install --upgrade pipenv
        $ cd /path/to/paperless
        $ pipenv install
        $ pipenv clean

    This creates a new virtual environment (or uses your existing environment)
    and installs all dependencies into it.

2.  Collect static files.

    .. code:: shell-session

        $ cd src
        $ pipenv run python3 manage.py collectstatic --clear
    
3.  Migrate the database.

    .. code:: shell-session

        $ cd src
        $ pipenv run python3 manage.py migrate

        
Management utilities
####################

Paperless comes with some management commands that perform various maintenance
tasks on your paperless instance. You can invoke these commands either by

.. code:: bash

    $ cd /path/to/paperless
    $ docker-compose run --rm webserver <command> <arguments>

or

.. code:: bash

    $ cd /path/to/paperless/src
    $ pipenv run python manage.py <command> <arguments>

depending on whether you use docker or not.

All commands have built-in help, which can be accessed by executing them with
the argument ``--help``.

.. _utilities-exporter:

Document exporter
=================

The document exporter exports all your data from paperless into a folder for
backup or migration to another DMS.

.. code::

    document_exporter target

``target`` is a folder to which the data gets written. This includes documents,
thumbnails and a ``manifest.json`` file. The manifest contains all metadata from
the database (correspondents, tags, etc).

When you use the provided docker compose script, specify ``../export`` as the
target. This path inside the container is automatically mounted on your host on
the folder ``export``.


.. _utilities-importer:

Document importer
=================

The document importer takes the export produced by the `Document exporter`_ and
imports it into paperless.

The importer works just like the exporter.  You point it at a directory, and
the script does the rest of the work:

.. code::

    document_importer source

When you use the provided docker compose script, put the export inside the
``export`` folder in your paperless source directory. Specify ``../export``
as the ``source``.


.. _utilities-retagger:

Document retagger
=================

Say you've imported a few hundred documents and now want to introduce
a tag or set up a new correspondent, and apply its matching to all of
the currently-imported docs. This problem is common enough that
there are tools for it.

.. code::

    document_retagger [-h] [-c] [-T] [-t] [-i] [--use-first] [-f]

    optional arguments:
    -c, --correspondent
    -T, --tags
    -t, --document_type
    -i, --inbox-only
    --use-first
    -f, --overwrite

Run this after changing or adding matching rules. It'll loop over all
of the documents in your database and attempt to match documents
according to the new rules.

Specify any combination of ``-c``, ``-T`` and ``-t`` to have the
retagger perform matching of the specified metadata type. If you don't
specify any of these options, the document retagger won't do anything.

Specify ``-i`` to have the document retagger work on documents tagged
with inbox tags only. This is useful when you don't want to mess with
your already processed documents.

When multiple document types or correspondents match a single document,
the retagger won't assign these to the document. Specify ``--use-first``
to override this behaviour and just use the first correspondent or type
it finds. This option does not apply to tags, since any amount of tags
can be applied to a document.

Finally, ``-f`` specifies that you wish to overwrite already assigned
correspondents, types and/or tags. The default behaviour is to not
assign correspondents and types to documents that have this data already
assigned. ``-f`` works differently for tags: By default, only additional tags get
added to documents, no tags will be removed. With ``-f``, tags that don't
match a document anymore get removed as well.


Managing the Automatic matching algorithm
=========================================

The *Auto* matching algorithm requires a trained neural network to work.
This network needs to be updated whenever somethings in your data
changes. The docker image takes care of that automatically with the task
scheduler. You can manually renew the classifier by invoking the following
management command:

.. code::

    document_create_classifier

This command takes no arguments.


Managing the document search index
==================================

The document search index is responsible for delivering search results for the
website. The document index is automatically updated whenever documents get
added to, changed, or removed from paperless. However, if the search yields
non-existing documents or won't find anything, you may need to recreate the
index manually.

.. code::

    document_index {reindex,optimize}

Specify ``reindex`` to have the index created from scratch. This may take some
time.

Specify ``optimize`` to optimize the index. This updates certain aspects of
the index and usually makes queries faster and also ensures that the
autocompletion works properly. This command is regularly invoked by the task
scheduler.

.. _utilities-renamer:

Managing filenames
==================

If you use paperless' feature to
:ref:`assign custom filenames to your documents <advanced-file_name_handling>`,
you can use this command to move all your files after changing
the naming scheme.

.. warning::

    Since this command moves you documents around alot, it is advised to to
    a backup before. The renaming logic is robust and will never overwrite
    or delete a file, but you can't ever be careful enough.

.. code::

    document_renamer

The command takes no arguments and processes all your documents at once.


Fetching e-mail
===============

Paperless automatically fetches your e-mail every 10 minutes by default. If
you want to invoke the email consumer manually, call the following management
command:

.. code::

    mail_fetcher

The command takes no arguments and processes all your mail accounts and rules.

.. _utilities-encyption:

Managing encryption
===================

Documents can be stored in Paperless using GnuPG encryption.

.. danger::

    Encryption is depreceated since paperless-ng 0.9 and doesn't really provide any
    additional security, since you have to store the passphrase in a configuration
    file on the same system as the encrypted documents for paperless to work.
    Furthermore, the entire text content of the documents is stored plain in the
    database, even if your documents are encrypted. Filenames are not encrypted as
    well.
    
    Also, the web server provides transparent access to your encrypted documents.

    Consider running paperless on an encrypted filesystem instead, which will then
    at least provide security against physical hardware theft.

.. code::

    change_storage_type [--passphrase PASSPHRASE] {gpg,unencrypted} {gpg,unencrypted}

    positional arguments:
      {gpg,unencrypted}     The state you want to change your documents from
      {gpg,unencrypted}     The state you want to change your documents to

    optional arguments:
      --passphrase PASSPHRASE

Enabling encryption
-------------------

Basic usage to enable encryption of your document store (**USE A MORE SECURE PASSPHRASE**):

(Note: If ``PAPERLESS_PASSPHRASE`` isn't set already, you need to specify it here)

.. code::

    change_storage_type [--passphrase SECR3TP4SSPHRA$E] unencrypted gpg


Disabling encryption
--------------------

Basic usage to enable encryption of your document store:

(Note: Again, if ``PAPERLESS_PASSPHRASE`` isn't set already, you need to specify it here)

.. code::

    change_storage_type [--passphrase SECR3TP4SSPHRA$E] gpg unencrypted


.. _Pipenv: https://pipenv.pypa.io/en/latest/