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
   The tags are optional, so the format ``Date - Correspondent - Title.pdf``
   works as well.
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

Do I have to be so strict about naming?
---------------------------------------
Rather than using the strict document naming rules, one can also set the option
``PAPERLESS_FILENAME_DATE_ORDER`` in ``paperless.conf`` to any date order
that is accepted by dateparser_. Doing so will cause ``paperless`` to default
to any date format that is found in the title, instead of a date pulled from
the document's text, without requiring the strict formatting of the document
filename as described above.

.. _dateparser: https://github.com/scrapinghub/dateparser/blob/v0.7.0/docs/usage.rst#settings

Transforming filenames for parsing
----------------------------------
Some devices can't produce filenames that can be parsed by the default
parser. By configuring the option ``PAPERLESS_FILENAME_PARSE_TRANSFORMS`` in
``paperless.conf`` one can add transformations that are applied to the filename
before it's parsed.

The option contains a list of dictionaries of regular expressions (key:
``pattern``) and replacements (key: ``repl``) in JSON format, which are
applied in order by passing them to ``re.subn``. Transformation stops
after the first match, so at most one transformation is applied. The general
syntax is

.. code:: python

   [{"pattern":"pattern1", "repl":"repl1"}, {"pattern":"pattern2", "repl":"repl2"}, ..., {"pattern":"patternN", "repl":"replN"}]

The example below is for a Brother ADS-2400N, a scanner that allows
different names to different hardware buttons (useful for handling
multiple entities in one instance), but insists on adding ``_<count>``
to the filename.

.. code:: python

   # Brother profile configuration, support "Name_Date_Count" (the default
   # setting) and "Name_Count" (use "Name" as tag and "Count" as title).
   PAPERLESS_FILENAME_PARSE_TRANSFORMS=[{"pattern":"^([a-z]+)_(\\d{8})_(\\d{6})_([0-9]+)\\.", "repl":"\\2\\3Z - \\4 - \\1."}, {"pattern":"^([a-z]+)_([0-9]+)\\.", "repl":" - \\2 - \\1."}]

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

When using the "any" or "all" matching algorithms, you can search for terms
that consist of multiple words by enclosing them in double quotes. For example,
defining a match text of ``"Bank of America" BofA`` using the "any" algorithm,
will match documents that contain either "Bank of America" or "BofA", but will
not match documents containing "Bank of South America".

Then just save your tag/correspondent and run another document through the
consumer.  Once complete, you should see the newly-created document,
automatically tagged with the appropriate data.
