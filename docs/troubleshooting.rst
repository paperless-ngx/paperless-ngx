.. _troubleshooting:

Troubleshooting
===============

.. _troubleshooting-languagemissing:

Consumer warns ``OCR for XX failed``
------------------------------------

If you find the OCR accuracy to be too low, and/or the document consumer warns
that ``OCR for XX failed, but we're going to stick with what we've got since
FORGIVING_OCR is enabled``, then you might need to install the
`Tesseract language files <http://packages.ubuntu.com/search?keywords=tesseract-ocr>`_
marching your document's languages.

As an example, if you are running Paperless from any Ubuntu or Debian
box, and your documents are written in Spanish you may need to run::

    apt-get install -y tesseract-ocr-spa


.. _troubleshooting-convertpixelcache:

Consumer dies with ``convert: unable to extent pixel cache``
------------------------------------------------------------

During the consumption process, Paperless invokes ImageMagick's ``convert``
program to translate the source document into something that the OCR engine can
understand and this can burn a Very Large amount of memory if the original
document is rather long.  Similarly, if your system doesn't have a lot of
memory to begin with (ie. a Raspberry Pi), then this can happen for even
medium-sized documents.

The solution is to tell ImageMagick *not* to Use All The RAM, as is its
default, and instead tell it to used a fixed amount.  ``convert`` will then
break up the job into hundreds of individual files and use them to slowly
compile the finished image.  Simply set ``PAPERLESS_CONVERT_MEMORY_LIMIT`` in
``/etc/paperless.conf`` to something like ``32000000`` and you'll limit
``convert`` to 32MB.  Fiddle with this value as you like.

**HOWEVER**: Simply setting this value may not be enough on system where
``/tmp`` is mounted as tmpfs, as this is where ``convert`` will write its
temporary files.  In these cases (most Systemd machines), you need to tell
ImageMagick to use a different space for its scratch work.  You do this by
setting ``PAPERLESS_CONVERT_TMPDIR`` in ``/etc/paperless.conf`` to somewhere
that's actually on a physical disk (and writable by the user running
Paperless), like ``/var/tmp/paperless`` or ``/home/my_user/tmp`` in a pinch.


.. _troubleshooting-decompressionbombwarning:

DecompressionBombWarning and/or no text in the OCR output
---------------------------------------------------------
Some users have had issues using Paperless to consume PDFs that were created
by merging Very Large Scanned Images into one PDF.  If this happens to you,
it's likely because the PDF you've created contains some very large pages
(millions of pixels) and the process of converting the PDF to a OCR-friendly
image is exploding.

Typically, this happens because the scanned images are created with a high
DPI and then rolled into the PDF with an assumed DPI of 72 (the default).
The best solution then is to specify the DPI used in the scan in the
conversion-to-PDF step.  So for example, if you scanned the original image
with a DPI of 300, then merging the images into the single PDF with
``convert`` should look like this:

.. code:: bash

    $ convert -density 300 *.jpg finished.pdf

For more information on this and situations like it, you should take a look
at `Issue #118`_ as that's where this tip originated.

.. _Issue #118: https://github.com/the-paperless-project/paperless/issues/118