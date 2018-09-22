.. _consumption:

Consumption
###########

Once you've got Paperless setup, you need to start feeding documents into it.
Currently, there are three options: the consumption directory, IMAP (email), and
HTTP POST.


.. _consumption-directory:

The Consumption Directory
=========================

The primary method of getting documents into your database is by putting them in
the consumption directory.  The ``document_consumer`` script runs in an infinite
loop looking for new additions to this directory and when it finds them, it goes
about the process of parsing them with the OCR, indexing what it finds, and
encrypting the PDF (if ``PAPERLESS_PASSPHRASE`` is set), storing it in the
media directory.

Getting stuff into this directory is up to you.  If you're running Paperless
on your local computer, you might just want to drag and drop files there, but if
you're running this on a server and want your scanner to automatically push
files to this directory, you'll need to setup some sort of service to accept the
files from the scanner.  Typically, you're looking at an FTP server like
`Proftpd`_ or `Samba`_.

.. _Proftpd: http://www.proftpd.org/
.. _Samba: http://www.samba.org/

So where is this consumption directory?  It's wherever you define it.  Look for
the ``CONSUMPTION_DIR`` value in ``settings.py``.  Set that to somewhere
appropriate for your use and put some documents in there.  When you're ready,
follow the :ref:`consumer <utilities-consumer>` instructions to get it running.


.. _consumption-directory-hook:

Hooking into the Consumption Process
------------------------------------

Sometimes you may want to do something arbitrary whenever a document is
consumed.  Rather than try to predict what you may want to do, Paperless lets
you execute scripts of your own choosing just before or after a document is
consumed using a couple simple hooks.

Just write a script, put it somewhere that Paperless can read & execute, and
then put the path to that script in ``paperless.conf`` with the variable name
of either ``PAPERLESS_PRE_CONSUME_SCRIPT`` or
``PAPERLESS_POST_CONSUME_SCRIPT``.  The script will be executed before or
or after the document is consumed respectively.

.. important::

    These scripts are executed in a **blocking** process, which means that if
    a script takes a long time to run, it can significantly slow down your
    document consumption flow.  If you want things to run asynchronously,
    you'll have to fork the process in your script and exit.


.. _consumption-directory-hook-variables:

What Can These Scripts Do?
..........................

It's your script, so you're only limited by your imagination and the laws of
physics.  However, the following values are passed to the scripts in order:


.. _consumption-director-hook-variables-pre:

Pre-consumption script
::::::::::::::::::::::

* Document file name

A simple but common example for this would be creating a simple script like
this:

``/usr/local/bin/ocr-pdf``

.. code:: bash

    #!/usr/bin/env bash
    pdf2pdfocr.py -i ${1}

``/etc/paperless.conf``

.. code:: bash

    ...
    PAPERLESS_PRE_CONSUME_SCRIPT="/usr/local/bin/ocr-pdf"
    ...

This will pass the path to the document about to be consumed to ``/usr/local/bin/ocr-pdf``,
which will in turn call `pdf2pdfocr.py`_ on your document, which will then
overwrite the file with an OCR'd version of the file and exit.  At which point,
the consumption process will begin with the newly modified file.

.. _pdf2pdfocr.py: https://github.com/LeoFCardoso/pdf2pdfocr


.. _consumption-director-hook-variables-post:

Post-consumption script
:::::::::::::::::::::::

* Document id
* Generated file name
* Source path
* Thumbnail path
* Download URL
* Thumbnail URL
* Correspondent
* Tags

The script can be in any language you like, but for a simple shell script
example, you can take a look at ``post-consumption-example.sh`` in the
``scripts`` directory in this project.


.. _consumption-imap:

IMAP (Email)
============

Another handy way to get documents into your database is to email them to
yourself.  The typical use-case would be to be out for lunch and want to send a
copy of the receipt back to your system at home.  Paperless can be taught to
pull emails down from an arbitrary account and dump them into the consumption
directory where the process :ref:`above <consumption-directory>` will follow the
usual pattern on consuming the document.

Some things you need to know about this feature:

* It's disabled by default.  By setting the values below it will be enabled.
* It's been tested in a limited environment, so it may not work for you (please
  submit a pull request if you can!)
* It's designed to **delete mail from the server once consumed**.  So don't go
  pointing this to your personal email account and wonder where all your stuff
  went.
* Currently, only one photo (attachment) per email will work.

So, with all that in mind, here's what you do to get it running:

1. Setup a new email account somewhere, or if you're feeling daring, create a
   folder in an existing email box and note the path to that folder.
2. In ``/etc/paperless.conf`` set all of the appropriate values in
   ``PATHS AND FOLDERS`` and ``SECURITY``.
   If you decided to use a subfolder of an existing account, then make sure you
   set ``PAPERLESS_CONSUME_MAIL_INBOX`` accordingly here.  You also have to set
   the ``PAPERLESS_EMAIL_SECRET`` to something you can remember 'cause you'll
   have to include that in every email you send.
3. Restart the :ref:`consumer <utilities-consumer>`.  The consumer will check
   the configured email account at startup and from then on every 10 minutes
   for something new and pulls down whatever it finds.
4. Send yourself an email!  Note that the subject is treated as the file name,
   so if you set the subject to ``Correspondent - Title - tag,tag,tag``, you'll
   get what you expect.  Also, you must include the aforementioned secret
   string in every email so the fetcher knows that it's safe to import.
   Note that Paperless only allows the email title to consist of safe characters
   to be imported. These consist of alpha-numeric characters and ``-_ ,.'``.
5. After a few minutes, the consumer will poll your mailbox, pull down the
   message, and place the attachment in the consumption directory with the
   appropriate name.  A few minutes later, the consumer will import it like any
   other file.


.. _consumption-http:

HTTP POST
=========

You can also submit a document via HTTP POST, so long as you do so after
authenticating.  To push your document to Paperless, send an HTTP POST to the
server with the following name/value pairs:

* ``correspondent``: The name of the document's correspondent.  Note that there
  are restrictions on what characters you can use here.  Specifically,
  alphanumeric characters, `-`, `,`, `.`, and `'` are ok, everything else is
  out.  You also can't use the sequence ` - ` (space, dash, space).
* ``title``: The title of the document.  The rules for characters is the same
  here as the correspondent.
* ``document``: The file you're uploading

Specify ``enctype="multipart/form-data"``, and then POST your file with::

    Content-Disposition: form-data; name="document"; filename="whatever.pdf"

An example of this in HTML is a typical form:

.. code:: html

    <form method="post" enctype="multipart/form-data">
        <input type="text" name="correspondent" value="My Correspondent" />
        <input type="text" name="title" value="My Title" />
        <input type="file" name="document" />
        <input type="submit" name="go" value="Do the thing" />
    </form>

But a potentially more useful way to do this would be in Python.  Here we use
the requests library to handle basic authentication and to send the POST data
to the URL.

.. code:: python

    import os

    from hashlib import sha256

    import requests
    from requests.auth import HTTPBasicAuth

    # You authenticate via BasicAuth or with a session id.
    # We use BasicAuth here
    username = "my-username"
    password = "my-super-secret-password"

    # Where you have Paperless installed and listening
    url = "http://localhost:8000/push"

    # Document metadata
    correspondent = "Test Correspondent"
    title = "Test Title"

    # The local file you want to push
    path = "/path/to/some/directory/my-document.pdf"


    with open(path, "rb") as f:

        response = requests.post(
            url=url,
            data={"title": title,  "correspondent": correspondent},
            files={"document": (os.path.basename(path), f, "application/pdf")},
            auth=HTTPBasicAuth(username, password),
            allow_redirects=False
        )

        if response.status_code == 202:

            # Everything worked out ok
            print("Upload successful")

        else:

            # If you don't get a 202, it's probably because your credentials
            # are wrong or something.  This will give you a rough idea of what
            # happened.

            print("We got HTTP status code: {}".format(response.status_code))
            for k, v in response.headers.items():
                print("{}: {}".format(k, v))
