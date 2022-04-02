***************
Advanced topics
***************

Paperless offers a couple features that automate certain tasks and make your life
easier.

.. _advanced-matching:

Matching tags, correspondents and document types
################################################

Paperless will compare the matching algorithms defined by every tag and
correspondent already set in your database to see if they apply to the text in
a document.  In other words, if you defined a tag called ``Home Utility``
that had a ``match`` property of ``bc hydro`` and a ``matching_algorithm`` of
``literal``, Paperless will automatically tag your newly-consumed document with
your ``Home Utility`` tag so long as the text ``bc hydro`` appears in the body
of the document somewhere.

The matching logic is quite powerful. It supports searching the text of your
document with different algorithms, and as such, some experimentation may be
necessary to get things right.

In order to have a tag, correspondent, or type assigned automatically to newly
consumed documents, assign a match and matching algorithm using the web
interface. These settings define when to assign correspondents, tags, and types
to documents.

The following algorithms are available:

* **Any:** Looks for any occurrence of any word provided in match in the PDF.
  If you define the match as ``Bank1 Bank2``, it will match documents containing
  either of these terms.
* **All:** Requires that every word provided appears in the PDF, albeit not in the
  order provided.
* **Literal:** Matches only if the match appears exactly as provided (i.e. preserve ordering) in the PDF.
* **Regular expression:** Parses the match as a regular expression and tries to
  find a match within the document.
* **Fuzzy match:** I dont know. Look at the source.
* **Auto:** Tries to automatically match new documents. This does not require you
  to set a match. See the notes below.

When using the *any* or *all* matching algorithms, you can search for terms
that consist of multiple words by enclosing them in double quotes. For example,
defining a match text of ``"Bank of America" BofA`` using the *any* algorithm,
will match documents that contain either "Bank of America" or "BofA", but will
not match documents containing "Bank of South America".

Then just save your tag/correspondent and run another document through the
consumer.  Once complete, you should see the newly-created document,
automatically tagged with the appropriate data.


.. _advanced-automatic_matching:

Automatic matching
==================

Paperless-ngx comes with a new matching algorithm called *Auto*. This matching
algorithm tries to assign tags, correspondents, and document types to your
documents based on how you have already assigned these on existing documents. It
uses a neural network under the hood.

If, for example, all your bank statements of your account 123 at the Bank of
America are tagged with the tag "bofa_123" and the matching algorithm of this
tag is set to *Auto*, this neural network will examine your documents and
automatically learn when to assign this tag.

Paperless tries to hide much of the involved complexity with this approach.
However, there are a couple caveats you need to keep in mind when using this
feature:

* Changes to your documents are not immediately reflected by the matching
  algorithm. The neural network needs to be *trained* on your documents after
  changes. Paperless periodically (default: once each hour) checks for changes
  and does this automatically for you.
* The Auto matching algorithm only takes documents into account which are NOT
  placed in your inbox (i.e. have any inbox tags assigned to them). This ensures
  that the neural network only learns from documents which you have correctly
  tagged before.
* The matching algorithm can only work if there is a correlation between the
  tag, correspondent, or document type and the document itself. Your bank
  statements usually contain your bank account number and the name of the bank,
  so this works reasonably well, However, tags such as "TODO" cannot be
  automatically assigned.
* The matching algorithm needs a reasonable number of documents to identify when
  to assign tags, correspondents, and types. If one out of a thousand documents
  has the correspondent "Very obscure web shop I bought something five years
  ago", it will probably not assign this correspondent automatically if you buy
  something from them again. The more documents, the better.
* Paperless also needs a reasonable amount of negative examples to decide when
  not to assign a certain tag, correspondent or type. This will usually be the
  case as you start filling up paperless with documents. Example: If all your
  documents are either from "Webshop" and "Bank", paperless will assign one of
  these correspondents to ANY new document, if both are set to automatic matching.

Hooking into the consumption process
####################################

Sometimes you may want to do something arbitrary whenever a document is
consumed.  Rather than try to predict what you may want to do, Paperless lets
you execute scripts of your own choosing just before or after a document is
consumed using a couple simple hooks.

Just write a script, put it somewhere that Paperless can read & execute, and
then put the path to that script in ``paperless.conf`` or ``docker-compose.env`` with the variable name
of either ``PAPERLESS_PRE_CONSUME_SCRIPT`` or
``PAPERLESS_POST_CONSUME_SCRIPT``.

.. important::

    These scripts are executed in a **blocking** process, which means that if
    a script takes a long time to run, it can significantly slow down your
    document consumption flow.  If you want things to run asynchronously,
    you'll have to fork the process in your script and exit.


Pre-consumption script
======================

Executed after the consumer sees a new document in the consumption folder, but
before any processing of the document is performed. This script receives exactly
one argument:

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

.. _advanced-post_consume_script:

Post-consumption script
=======================

Executed after the consumer has successfully processed a document and has moved it
into paperless. It receives the following arguments:

* Document id
* Generated file name
* Source path
* Thumbnail path
* Download URL
* Thumbnail URL
* Correspondent
* Tags

The script can be in any language, but for a simple shell script
example, you can take a look at `post-consumption-example.sh`_ in this project.

The post consumption script cannot cancel the consumption process.

Docker
------
Assumed you have ``/home/foo/paperless-ngx/scripts/post-consumption-example.sh``.

You can pass that script into the consumer container via a host mount in your ``docker-compose.yml``.

.. code:: bash
   ...
   consumer:
           ...
           volumes:
					     ...
               - /home/paperless-ngx/scripts:/path/in/container/scripts/
   ...

Example (docker-compose.yml): ``- /home/foo/paperless-ngx/scripts:/usr/src/paperless/scripts``

which in turn requires the variable ``PAPERLESS_POST_CONSUME_SCRIPT`` in ``docker-compose.env``  to point to ``/path/in/container/scripts/post-consumption-example.sh``.

Example (docker-compose.env): ``PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless/scripts/post-consumption-example.sh``

Troubleshooting:

- Monitor the docker-compose log ``cd ~/paperless-ngx; docker-compose logs -f``
- Check your script's permission e.g. in case of permission error ``sudo chmod 755 post-consumption-example.sh``
- Pipe your scripts's output to a log file e.g. ``echo "${DOCUMENT_ID}" | tee --append /usr/src/paperless/scripts/post-consumption-example.log``

.. _post-consumption-example.sh: https://github.com/paperless-ngx/paperless-ngx/blob/main/scripts/post-consumption-example.sh

.. _advanced-file_name_handling:

File name handling
##################

By default, paperless stores your documents in the media directory and renames them
using the identifier which it has assigned to each document. You will end up getting
files like ``0000123.pdf`` in your media directory. This isn't necessarily a bad
thing, because you normally don't have to access these files manually. However, if
you wish to name your files differently, you can do that by adjusting the
``PAPERLESS_FILENAME_FORMAT`` configuration option.

This variable allows you to configure the filename (folders are allowed) using
placeholders. For example, configuring this to

.. code:: bash

    PAPERLESS_FILENAME_FORMAT={created_year}/{correspondent}/{title}

will create a directory structure as follows:

.. code::

    2019/
      My bank/
        Statement January.pdf
        Statement February.pdf
    2020/
      My bank/
        Statement January.pdf
        Letter.pdf
        Letter_01.pdf
      Shoe store/
        My new shoes.pdf

.. danger::

    Do not manually move your files in the media folder. Paperless remembers the
    last filename a document was stored as. If you do rename a file, paperless will
    report your files as missing and won't be able to find them.

Paperless provides the following placeholders withing filenames:

* ``{asn}``: The archive serial number of the document, or "none".
* ``{correspondent}``: The name of the correspondent, or "none".
* ``{document_type}``: The name of the document type, or "none".
* ``{tag_list}``: A comma separated list of all tags assigned to the document.
* ``{title}``: The title of the document.
* ``{created}``: The full date (ISO format) the document was created.
* ``{created_year}``: Year created only.
* ``{created_month}``: Month created only (number 01-12).
* ``{created_day}``: Day created only (number 01-31).
* ``{added}``: The full date (ISO format) the document was added to paperless.
* ``{added_year}``: Year added only.
* ``{added_month}``: Month added only (number 01-12).
* ``{added_day}``: Day added only (number 01-31).


Paperless will try to conserve the information from your database as much as possible.
However, some characters that you can use in document titles and correspondent names (such
as ``: \ /`` and a couple more) are not allowed in filenames and will be replaced with dashes.

If paperless detects that two documents share the same filename, paperless will automatically
append ``_01``, ``_02``, etc to the filename. This happens if all the placeholders in a filename
evaluate to the same value.

.. hint::

    Paperless checks the filename of a document whenever it is saved. Therefore,
    you need to update the filenames of your documents and move them after altering
    this setting by invoking the :ref:`document renamer <utilities-renamer>`.

.. warning::

    Make absolutely sure you get the spelling of the placeholders right, or else
    paperless will use the default naming scheme instead.

.. caution::

    As of now, you could totally tell paperless to store your files anywhere outside
    the media directory by setting

    .. code::

        PAPERLESS_FILENAME_FORMAT=../../my/custom/location/{title}

    However, keep in mind that inside docker, if files get stored outside of the
    predefined volumes, they will be lost after a restart of paperless.
