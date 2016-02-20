.. _utilities:

Utilities
=========

There's basically three utilities to *Paperless*: the webserver, consumer, and
if needed, the exporter.  They're all detailed here.


.. _utilities-webserver:

The Webserver
-------------

At the heart of it, *Paperless* is a simple Django webservice, and the entire
interface is based on Django's standard admin interface.  Once running, visiting
the URL for your service delivers the admin, through which you can get a
detailed listing of all available documents, search for specific files, and
download whatever it is you're looking for.


.. _utilities-webserver-howto:

How to Use It
.............

The webserver is started via the ``manage.py`` script:

.. code:: bash

    $ /path/to/paperless/src/manage.py runserver

By default, the server runs on localhost, port 8000, but you can change this
with a few arguments, run ``manage.py --help`` for more information.

Note that this command runs continuously, so exiting it will mean your webserver
disappears.  If you want to run this full-time (which is kind of the point)
you'll need to have it start in the background -- something you'll need to
figure out for your own system.  To get you started though, there are Systemd
service files in the ``scripts`` directory.


.. _utilities-consumer:

The Consumer
------------

The consumer script runs in an infinite loop, constantly looking at a directory
for PDF files to parse and index.  The process is pretty straightforward:

1. Look in ``CONSUMPTION_DIR`` for a PDF.  If one is found, go to #2.  If not,
   wait 10 seconds and try again.
2. Parse the PDF with Tesseract
3. Create a new record in the database with the OCR'd text
4. Encrypt the PDF and store it in the ``media`` directory under
   ``documents/pdf``.
5. Go to #1.


.. _utilities-consumer-howto:

How to Use It
.............

The consumer is started via the ``manage.py`` script:

.. code:: bash

    $ /path/to/paperless/src/manage.py document_consumer

This starts the service that will run in a loop, consuming PDF files as they
appear in ``CONSUMPTION_DIR``.

Note that this command runs continuously, so exiting it will mean your webserver
disappears.  If you want to run this full-time (which is kind of the point)
you'll need to have it start in the background -- something you'll need to
figure out for your own system.  To get you started though, there are Systemd
service files in the ``scripts`` directory.


.. _utilities-exporter:

The Exporter
------------

Tired of fiddling with *Paperless*, or just want to do something stupid and are
afraid of accidentally damaging your files?  You can export all of your PDFs
into neatly named, dated, and unencrypted.


.. _utilities-exporter-howto:

How to Use It
.............

This too is done via the ``manage.py`` script:

.. code:: bash

    $ /path/to/paperless/src/manage.py document_exporter /path/to/somewhere

This will dump all of your PDFs into ``/path/to/somewhere`` for you to do with
as you please.  The naming scheme on export is identical to that used for
import, so should you can now safely delete the entire project directly,
database, encrypted PDFs and all, and later create it all again simply by
running the consumer again and dumping all of these files into
``CONSUMPTION_DIR``.


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
don't worry, you can run this as often as you like, it' won't double-tag
a document.
