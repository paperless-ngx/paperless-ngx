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
marching your documents languages.

As an example, if you are running Paperless from the Vagrant setup provided
(or from any Ubuntu or Debian box), and your documents are written in Spanish
you may need to run::

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
