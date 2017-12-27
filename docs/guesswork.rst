.. _guesswork:

Guesswork
#########

During the consumption process, Paperless tries to guess some of the attributes
of the document it's looking at.  To do this it uses two approaches:


.. _guesswork-naming:

File Naming
===========

Any document you put into the consumption directory will be consumed, but if
you name the file right, it'll automatically set some values in the database
for you.  This is is the logic the consumer follows:

1. Try to find the correspondent, title, and tags in the file name following
   the pattern: ``Date - Correspondent - Title - tag,tag,tag.pdf``.  Note that
   the format of the date is **rigidly defined** as ``YYYYMMDDHHMMSSZ`` or
   ``YYYYMMDDZ``.  The ``Z`` refers "Zulu time" AKA "UTC".
2. If that doesn't work, we skip the date and try this pattern:
   ``Correspondent - Title - tag,tag,tag.pdf``.
3. If that doesn't work, we try to find the correspondent and title in the file
   name following the pattern: ``Correspondent - Title.pdf``.
4. If that doesn't work, just assume that the name of the file is the title.

So given the above, the following examples would work as you'd expect:

* ``20150314000700Z - Some Company Name - Invoice 2016-01-01 - money,invoices.pdf``
* ``20150314Z - Some Company Name - Invoice 2016-01-01 - money,invoices.pdf``
* ``Some Company Name - Invoice 2016-01-01 - money,invoices.pdf``
* ``Another Company - Letter of Reference.jpg``
* ``Dad's Recipe for Pancakes.png``

These however wouldn't work:

* ``2015-03-14 00:07:00 UTC - Some Company Name, Invoice 2016-01-01, money, invoices.pdf``
* ``2015-03-14 - Some Company Name, Invoice 2016-01-01, money, invoices.pdf``
* ``Some Company Name, Invoice 2016-01-01, money, invoices.pdf``
* ``Another Company- Letter of Reference.jpg``


.. _guesswork-content:

Reading the Document Contents
=============================

After the consumer has tried to figure out what it could from the file name,
it starts looking at the content of the document itself.  It will compare the
matching algorithms defined by every tag and correspondent already set in your
database to see if they apply to the text in that document.  In other words,
if you defined a tag called ``Home Utility`` that had a ``match`` property of
``bc hydro`` and a ``matching_algorithm`` of ``literal``, Paperless will
automatically tag your newly-consumed document with your ``Home Utility`` tag
so long as the text ``bc hydro`` appears in the body of the document somewhere.

The matching logic is quite powerful, and supports searching the text of your
document with different algorithms, and as such, some experimentation may be
necessary to get things Just Right.


.. _guesswork-content-howto:

How Do I Set Up These Matching Algorithms?
------------------------------------------

Setting up of the algorithms is easily done through the admin interface.  When
you create a new correspondent or tag, there are optional fields for matching
text and matching algorithm.  From the help info there:

.. note::

    Which algorithm you want to use when matching text to the OCR'd PDF.  Here,
    "any" looks for any occurrence of any word provided in the PDF, while "all"
    requires that every word provided appear in the PDF, albeit not in the
    order provided.  A "literal" match means that the text you enter must
    appear in the PDF exactly as you've entered it, and "regular expression"
    uses a regex to match the PDF.  If you don't know what a regex is, you
    probably don't want this option.

When using the "any" or "all" matching algorithms, you can search for terms that
consist of multiple words by enclosing them in double quotes. For example, defining
a match text of ``"Bank of America" BofA`` using the "any" algorithm, will match
documents that contain either "Bank of America" or "BofA", but will not match
documents containing "Bank of South America".

Then just save your tag/correspondent and run another document through the
consumer.  Once complete, you should see the newly-created document,
automatically tagged with the appropriate data.
