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
encrypting the PDF, storing it in the media directory.

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


.. _consumption-directory-hook-variables

What Can These Scripts Do?
..........................

It's your script, so you're only limited by your imagination and the laws of
physics.  However, the following values are passed to the scripts in order:


.. _consumption-director-hook-variables-pre

Pre-consumption script
::::::::::::::::::::::

* Document file name


.. _consumption-director-hook-variables-post

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
2. In ``settings.py`` set all of the appropriate values in ``MAIL_CONSUMPTION``.
   If you decided to use a subfolder of an existing account, then make sure you
   set ``INBOX`` accordingly here.  You also have to set the
   ``UPLOAD_SHARED_SECRET`` to something you can remember 'cause you'll have to
   include that in every email you send.
3. Restart the :ref:`consumer <utilities-consumer>`.  The consumer will check
   the configured email account every 10 minutes for something new and pull down
   whatever it finds.
4. Send yourself an email!  Note that the subject is treated as the file name,
   so if you set the subject to ``Correspondent - Title - tag,tag,tag``, you'll
   get what you expect.  Also, you must include the aforementioned secret
   string in every email so the fetcher knows that it's safe to import.
5. After a few minutes, the consumer will poll your mailbox, pull down the
   message, and place the attachment in the consumption directory with the
   appropriate name.  A few minutes later, the consumer will import it like any
   other file.


.. _consumption-http:

HTTP POST
=========

You can also submit a document via HTTP POST.  It doesn't do tags yet, and the
URL schema isn't concrete, but it's a start.

To push your document to Paperless, send an HTTP POST to the server with the
following name/value pairs:

* ``correspondent``: The name of the document's correspondent.  Note that there
  are restrictions on what characters you can use here.  Specifically,
  alphanumeric characters, `-`, `,`, `.`, and `'` are ok, everything else it
  out.  You also can't use the sequence ` - ` (space, dash, space).
* ``title``: The title of the document.  The rules for characters is the same
  here as the correspondent.
* ``signature``: For security reasons, we have the correspondent send a
  signature using a "shared secret" method to make sure that random strangers
  don't start uploading stuff to your server.  The means of generating this
  signature is defined below.

Specify ``enctype="multipart/form-data"``, and then POST your file with::

    Content-Disposition: form-data; name="document"; filename="whatever.pdf"


.. _consumption-http-signature:

Generating the Signature
------------------------

Generating a signature based a shared secret is pretty simple: define a secret,
and store it on the server and the client.  Then use that secret, along with
the text you want to verify to generate a string that you can use for
verification.

In the case of Paperless, you configure the server with the secret by setting
``UPLOAD_SHARED_SECRET``.  Then on your client, you generate your signature by
concatenating the correspondent, title, and the secret, and then using sha256
to generate a hexdigest.

If you're using Python, this is what that looks like:

.. code:: python

    from hashlib import sha256
    signature = sha256(correspondent + title + secret).hexdigest()
