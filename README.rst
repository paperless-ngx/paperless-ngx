Paperless
#########

|Documentation|
|Chat|
|Travis|

Index and archive all of your scanned paper documents

I hate paper.  Environmental issues aside, it's a tech person's nightmare:

* There's no search feature
* It takes up physical space
* Backups mean more paper

In the past few months I've been bitten more than a few times by the problem
of not having the right document around.  Sometimes I recycled a document I
needed (who keeps water bills for two years?) and other times I just lost
it... because paper.  I wrote this to make my life easier.


How it Works
============

Paperless does not control your scanner, it only helps you deal with what your
scanner produces

1. Buy a document scanner that can write to a place on your network.  If you
   need some inspiration, have a look at the `scanner recommendations`_ page.
2. Set it up to "scan to FTP" or something similar. It should be able to push
   scanned images to a server without you having to do anything.  Of course if
   your scanner doesn't know how to automatically upload the file somewhere,
   you can always do that manually.  Paperless doesn't care how the documents
   get into its local consumption directory.
3. Have the target server run the Paperless consumption script to OCR the file
   and index it into a local database.
4. Use the web frontend to sift through the database and find what you want.
5. Download the PDF you need/want via the web interface and do whatever you
   like with it.  You can even print it and send it as if it's the original.
   In most cases, no one will care or notice.

Here's what you get:

.. image:: docs/_static/screenshot.png
   :alt: The before and after
   :target: docs/_static/screenshot.png


Stability
=========

Paperless is still under active development (just look at the git commit
history) so don't expect it to be 100% stable.  You can backup the sqlite3
database, media directory and your configuration file to be on the safe side.


Requirements
============

This is all really a quite simple, shiny, user-friendly wrapper around some
very powerful tools.

* `ImageMagick`_ converts the images between colour and greyscale.
* `Tesseract`_ does the character recognition.
* `Unpaper`_ despeckles and deskews the scanned image.
* `GNU Privacy Guard`_ is used as the encryption backend.
* `Python 3`_ is the language of the project.

  * `Pillow`_ loads the image data as a python object to be used with PyOCR.
  * `PyOCR`_ is a slick programmatic wrapper around tesseract.
  * `Django`_ is the framework this project is written against.
  * `Python-GNUPG`_ decrypts the PDFs on-the-fly to allow you to download
    unencrypted files, leaving the encrypted ones on-disk.


Documentation
=============

It's all available on `ReadTheDocs`_.


Similar Projects
================

There's another project out there called `Mayan EDMS`_ that has a surprising
amount of technical overlap with Paperless.  Also based on Django and using
a consumer model with Tesseract and Unpaper, Mayan EDMS is *much* more
featureful and comes with a slick UI as well, but still in Python 2. It may be
that Paperless consumes fewer resources, but to be honest, this is just a guess
as I haven't tested this myself.  One thing's for certain though, *Paperless*
is a **much** better name.


Important Note
==============

Document scanners are typically used to scan sensitive documents.  Things like
your social insurance number, tax records, invoices, etc.  While Paperless
encrypts the original files via the consumption script, the OCR'd text is *not*
encrypted and is therefore stored in the clear (it needs to be searchable, so
if someone has ideas on how to do that on encrypted data, I'm all ears).  This
means that Paperless should never be run on an untrusted host.  Instead, I
recommend that if you do want to use it, run it locally on a server in your own
home.


Donations
=========

As with all Free software, the power is less in the finances and more in the
collective efforts.  I really appreciate every pull request and bug report
offered up by Paperless' users, so please keep that stuff coming.  If however,
you're not one for coding/design/documentation, and would like to contribute
financially, I won't say no ;-)

The thing is, I'm doing ok for money, so I would instead ask you to donate to
the `United Nations High Commissioner for Refugees`_.  They're doing important
work and they need the money a lot more than I do.

.. _scanner recommendations: https://paperless.readthedocs.io/en/latest/scanners.html
.. _ImageMagick: http://imagemagick.org/
.. _Tesseract: https://github.com/tesseract-ocr
.. _Unpaper: https://www.flameeyes.eu/projects/unpaper
.. _GNU Privacy Guard: https://gnupg.org/
.. _Python 3: https://python.org/
.. _Pillow: https://pypi.python.org/pypi/pillowfight/
.. _PyOCR: https://github.com/jflesch/pyocr
.. _Django: https://www.djangoproject.com/
.. _Python-GNUPG: http://pythonhosted.org/python-gnupg/
.. _ReadTheDocs: https://paperless.readthedocs.org/
.. _Mayan EDMS: https://mayan.readthedocs.org/en/latest/
.. _United Nations High Commissioner for Refugees: https://donate.unhcr.org/int-en/general
.. |Documentation| image:: https://readthedocs.org/projects/paperless/badge/?version=latest
   :alt: Read the documentation at https://paperless.readthedocs.org/
   :target: https://paperless.readthedocs.org/
.. |Chat| image:: https://badges.gitter.im/danielquinn/paperless.svg
   :alt: Join the chat at https://gitter.im/danielquinn/paperless
   :target: https://gitter.im/danielquinn/paperless?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
.. |Travis| image:: https://travis-ci.org/danielquinn/paperless.svg?branch=master
   :target: https://travis-ci.org/danielquinn/paperless
