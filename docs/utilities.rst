.. _utilities:

Utilities
=========

There's basically three utilities to Paperless: the webserver, consumer, and
if needed, the exporter.  They're all detailed here.


.. _utilities-webserver:

The Webserver
-------------

At the heart of it, Paperless is a simple Django webservice, and the entire
interface is based on Django's standard admin interface.  Once running, visiting
the URL for your service delivers the admin, through which you can get a
detailed listing of all available documents, search for specific files, and
download whatever it is you're looking for.


.. _utilities-webserver-howto:

How to Use It
.............

The webserver is started via the ``manage.py`` script:

.. code-block:: shell-session

    $ /path/to/paperless/src/manage.py runserver

By default, the server runs on localhost, port 8000, but you can change this
with a few arguments, run ``manage.py --help`` for more information.

Add the option ``--noreload`` to reduce resource usage. Otherwise, the server
continuously polls all source files for changes to auto-reload them.

Note that when exiting this command your webserver will disappear.
If you want to run this full-time (which is kind of the point)
you'll need to have it start in the background -- something you'll need to
figure out for your own system.  To get you started though, there are Systemd
service files in the ``scripts`` directory.


.. _utilities-consumer:

The Consumer
------------

The consumer script runs in an infinite loop, constantly looking at a directory
for documents to parse and index.  The process is pretty straightforward:

1. Look in ``CONSUMPTION_DIR`` for a document.  If one is found, go to #2.
   If not, wait 10 seconds and try again.  On Linux, new documents are detected
   instantly via inotify, so there's no waiting involved.
2. Parse the document with Tesseract
3. Create a new record in the database with the OCR'd text
4. Attempt to automatically assign document attributes by doing some guesswork.
   Read up on the :ref:`guesswork documentation<guesswork>` for more
   information about this process.
5. Encrypt the document (if you have a passphrase set) and store it in the
   ``media`` directory under ``documents/originals``.
6. Go to #1.


.. _utilities-consumer-howto:

How to Use It
.............

The consumer is started via the ``manage.py`` script:

.. code-block:: shell-session

    $ /path/to/paperless/src/manage.py document_consumer

This starts the service that will consume documents as they appear in
``CONSUMPTION_DIR``.

Note that this command runs continuously, so exiting it will mean your webserver
disappears.  If you want to run this full-time (which is kind of the point)
you'll need to have it start in the background -- something you'll need to
figure out for your own system.  To get you started though, there are Systemd
service files in the ``scripts`` directory.

Some command line arguments are available to customize the behavior of the
consumer. By default it will use ``/etc/paperless.conf`` values. Display the
help with:

.. code-block:: shell-session

    $ /path/to/paperless/src/manage.py document_consumer --help

.. _utilities-exporter:

The Exporter
------------

Tired of fiddling with Paperless, or just want to do something stupid and are
afraid of accidentally damaging your files?  You can export all of your
documents into neatly named, dated, and unencrypted files.


.. _utilities-exporter-howto:

How to Use It
.............

This too is done via the ``manage.py`` script:

.. code-block:: shell-session

    $ /path/to/paperless/src/manage.py document_exporter /path/to/somewhere/

This will dump all of your unencrypted documents into ``/path/to/somewhere``
for you to do with as you please.  The files are accompanied with a special
file, ``manifest.json`` which can be used to :ref:`import the files
<utilities-importer>` at a later date if you wish.


.. _utilities-exporter-howto-docker:

Docker
______

If you are :ref:`using Docker <setup-installation-docker>`, running the
expoorter is almost as easy.  To mount a volume for exports, follow the
instructions in the ``docker-compose.yml.example`` file for the ``/export``
volume (making the changes in your own ``docker-compose.yml`` file, of course).
Once you have the volume mounted, the command to run an export is:

.. code-block:: shell-session

   $ docker-compose run --rm consumer document_exporter /export

If you prefer to use ``docker run`` directly, supplying the necessary commandline
options:

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


.. _utilities-importer:

The Importer
------------

Looking to transfer Paperless data from one instance to another, or just want
to restore from a backup?  This is your go-to toy.


.. _utilities-importer-howto:

How to Use It
.............

The importer works just like the exporter.  You point it at a directory, and
the script does the rest of the work:

.. code-block:: shell-session

    $ /path/to/paperless/src/manage.py document_importer /path/to/somewhere/

Docker
______

Assuming that you've already gone through the steps above in the
:ref:`export <utilities-exporter-howto-docker>` section, then the easiest thing
to do is just re-use the ``/export`` path you already setup:

.. code-block:: shell-session

   $ docker-compose run --rm consumer document_importer /export

Similarly, if you're not using docker-compose, you can adjust the export
instructions above to do the import.


.. _utilities-retagger:

The Re-tagger
-------------

Say you've imported a few hundred documents and now want to introduce a tag
and apply its matching to all of the currently-imported docs.  This problem is
common enough that there's a tool for it.


.. _utilities-retagger-howto:

How to Use It
.............

This too is done via the ``manage.py`` script:

.. code:: bash

    $ /path/to/paperless/src/manage.py document_retagger

That's it.  It'll loop over all of the documents in your database and attempt
to match all of your tags to them.  If one matches, it'll be applied.  And
don't worry, you can run this as often as you like, it won't double-tag
a document.

.. _utilities-encyption:

Enabling Encrpytion
-------------------

Let's say you've imported a few documents to play around with paperless and now
you are using it more seriously and want to enable encryption of your files.

.. utilities-encryption-howto:

Basic Syntax
.............

Again we'll use the ``manage.py`` script, passing ``change_storage_type``:

.. code:: bash

    $ /path/to/paperless/src/manage.py change_storage_type --help
		usage: manage.py change_storage_type [-h] [--version] [-v {0,1,2,3}]
                                     [--settings SETTINGS]
                                     [--pythonpath PYTHONPATH] [--traceback]
                                     [--no-color] [--passphrase PASSPHRASE]
                                     {gpg,unencrypted} {gpg,unencrypted}

    This is how you migrate your stored documents from an encrypted state to an
    unencrypted one (or vice-versa)

    positional arguments:
      {gpg,unencrypted}     The state you want to change your documents from
      {gpg,unencrypted}     The state you want to change your documents to

    optional arguments:
      --passphrase PASSPHRASE
                            If PAPERLESS_PASSPHRASE isn't set already, you need to
                            specify it here

Enabling Encryption
...................

Basic usage to enable encryption of your document store (**USE A MORE SECURE PASSPHRASE**):

(Note: If ``PAPERLESS_PASSPHRASE`` isn't set already, you need to specify it here)

.. code:: bash

    $ /path/to/paperless/src/manage.py change_storage_type [--passphrase SECR3TP4SSPHRA$E] unencrypted gpg


Disabling Encryption
....................

Basic usage to enable encryption of your document store:

(Note: Again, if ``PAPERLESS_PASSPHRASE`` isn't set already, you need to specify it here)

.. code:: bash

    $ /path/to/paperless/src/manage.py change_storage_type [--passphrase SECR3TP4SSPHRA$E] gpg unencrypted
