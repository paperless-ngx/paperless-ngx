.. _extending:

Extending Paperless
===================

For the most part, Paperless is monolithic, so extending it is often best
managed by way of modifying the code directly and issuing a pull request on
`GitHub`_.  However, over time the project has been evolving to be a little
more "pluggable" so that users can write their own stuff that talks to it.

.. _GitHub: https://github.com/danielquinn/paperless


.. _extending-parsers:

Parsers
-------

You can leverage Paperless' consumption model to have it consume files *other*
than ones handled by default like ``.pdf``, ``.jpg``, and ``.tiff``.  To do so,
you simply follow Django's convention of creating a new app, with a few key
requirements.


.. _extending-parsers-parserspy:

parsers.py
..........

In this file, you create a class that extends
``documents.parsers.DocumentParser`` and go about implementing the three
required methods:

* ``get_thumbnail()``: Returns the path to a file we can use as a thumbnail for
  this document.
* ``get_text()``: Returns the text from the document and only the text.
* ``get_date()``: If possible, this returns the date of the document, otherwise
  it should return ``None``.


.. _extending-parsers-signalspy:

signals.py
..........

At consumption time, Paperless emits a ``document_consumer_declaration``
signal which your module has to react to in order to let the consumer know
whether or not it's capable of handling a particular file.  Think of it like
this:

1. Consumer finds a file in the consumption directory.
2. It asks all the available parsers: *"Hey, can you handle this file?"*
3. The first parser that says yes gets to handle the file.  The order in which
   the parsers are asked is handled by sorting ``INSTALLED_APPS`` in
   ``settings.py``.


.. _extending-parsers-appspy:

apps.py
.......

This is a standard Django file, but you'll need to add some code to it to
register your parser as being able to handle particular files.


.. _extending-parsers-finally:

Finally
.......

The last step is to update ``settings.py`` to include your new module.
Eventually, this will be dynamic, but at the moment, you have to edit the
``INSTALLED_APPS`` section manually.  Simply add the path to your AppConfig to
the list like this:

.. code:: python

    INSTALLED_APPS = [
        ...
        "my_module.apps.MyModuleConfig",
        "paperless_tesseract.apps.PaperlessTesseractConfig",
        ...
    ]

Note that we're placing our module *above* ``PaperlessTesseractConfig``.  This
is to ensure that if your module wants to handle any files typically handled by
the default module, yours will win instead.  If there's no conflict between
what your module does and the default, then order doesn't matter.


.. _extending-parsers-example:

An Example
..........

The core Paperless functionality is based on this design, so if you want to see
what a parser module should look like, have a look at `parsers.py`_,
`signals.py`_, and `apps.py`_ in the `paperless_tesseract`_ module.

.. _parsers.py: https://github.com/danielquinn/paperless/blob/master/src/paperless_tesseract/parsers.py
.. _signals.py: https://github.com/danielquinn/paperless/blob/master/src/paperless_tesseract/signals.py
.. _apps.py: https://github.com/danielquinn/paperless/blob/master/src/paperless_tesseract/apps.py
.. _paperless_tesseract: https://github.com/danielquinn/paperless/blob/master/src/paperless_tesseract/
