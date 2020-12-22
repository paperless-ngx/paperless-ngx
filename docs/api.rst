
************
The REST API
************


Paperless makes use of the `Django REST Framework`_ standard API interface.
It provides a browsable API for most of its endpoints, which you can inspect
at ``http://<paperless-host>:<port>/api/``. This also documents most of the
available filters and ordering fields.

.. _Django REST Framework: http://django-rest-framework.org/

The API provides 5 main endpoints:

*   ``/api/documents/``: Full CRUD support, except POSTing new documents. See below.
*   ``/api/correspondents/``: Full CRUD support.
*   ``/api/document_types/``: Full CRUD support.
*   ``/api/logs/``: Read-Only.
*   ``/api/tags/``: Full CRUD support.

All of these endpoints except for the logging endpoint
allow you to fetch, edit and delete individual objects
by appending their primary key to the path, for example ``/api/documents/454/``.

The objects served by the document endpoint contain the following fields:

*   ``id``: ID of the document. Read-only.
*   ``title``: Title of the document.
*   ``content``: Plain text content of the document.
*   ``tags``: List of IDs of tags assigned to this document, or empty list.
*   ``document_type``: Document type of this document, or null.
*   ``correspondent``:  Correspondent of this document or null.
*   ``created``: The date at which this document was created.
*   ``modified``: The date at which this document was last edited in paperless. Read-only.
*   ``added``: The date at which this document was added to paperless. Read-only.
*   ``archive_serial_number``: The identifier of this document in a physical document archive.
*   ``original_file_name``: Verbose filename of the original document. Read-only.
*   ``archived_file_name``: Verbose filename of the archived document. Read-only. Null if no archived document is available.


Downloading documents
#####################

In addition to that, the document endpoint offers these additional actions on
individual documents:

*   ``/api/documents/<pk>/download/``: Download the document.
*   ``/api/documents/<pk>/preview/``: Display the document inline,
    without downloading it.
*   ``/api/documents/<pk>/thumb/``: Download the PNG thumbnail of a document.

Paperless generates archived PDF/A documents from consumed files and stores both
the original files as well as the archived files. By default, the endpoints
for previews and downloads serve the archived file, if it is available.
Otherwise, the original file is served.
Some document cannot be archived.

The endpoints correctly serve the response header fields ``Content-Disposition``
and ``Content-Type`` to indicate the filename for download and the type of content of
the document.

In order to download or preview the original document when an archied document is available,
supply the query parameter ``original=true``.

.. hint::

    Paperless used to provide these functionality at ``/fetch/<pk>/preview``,
    ``/fetch/<pk>/thumb`` and ``/fetch/<pk>/doc``. Redirects to the new URLs
    are in place. However, if you use these old URLs to access documents, you
    should update your app or script to use the new URLs.


Getting document metadata
#########################

The api also has an endpoint to retrieve read-only metadata about specific documents. this
information is not served along with the document objects, since it requires reading
files and would therefore slow down document lists considerably.

Access the metadata of a document with an ID ``id`` at ``/api/documents/<id>/metadata/``.

The endpoint reports the following data:

*   ``original_checksum``: MD5 checksum of the original document.
*   ``original_size``: Size of the original document, in bytes.
*   ``original_mime_type``: Mime type of the original document.
*   ``media_filename``: Current filename of the document, under which it is stored inside the media directory.
*   ``has_archive_version``: True, if this document is archived, false otherwise.
*   ``original_metadata``: A list of metadata associated with the original document. See below.
*   ``archive_checksum``: MD5 checksum of the archived document, or null.
*   ``archive_size``: Size of the archived document in bytes, or null.
*   ``archive_metadata``: Metadata associated with the archived document, or null. See below.

File metadata is reported as a list of objects in the following form:

.. code:: json

    [
        {
            "namespace": "http://ns.adobe.com/pdf/1.3/",
            "prefix": "pdf",
            "key": "Producer",
            "value": "SparklePDF, Fancy edition"
        },
    ]

``namespace`` and ``prefix`` can be null. The actual metadata reported depends on the file type and the metadata
available in that specific document. Paperless only reports PDF metadata at this point.

Authorization
#############

The REST api provides three different forms of authentication.

1.  Basic authentication

    Authorize by providing a HTTP header in the form

    .. code::

        Authorization: Basic <credentials>

    where ``credentials`` is a base64-encoded string of ``<username>:<password>``

2.  Session authentication

    When you're logged into paperless in your browser, you're automatically
    logged into the API as well and don't need to provide any authorization
    headers.

3.  Token authentication

    Paperless also offers an endpoint to acquire authentication tokens.

    POST a username and password as a form or json string to ``/api/token/``
    and paperless will respond with a token, if the login data is correct.
    This token can be used to authenticate other requests with the
    following HTTP header:

    .. code::

        Authorization: Token <token>

    Tokens can be managed and revoked in the paperless admin.

Searching for documents
#######################

Paperless-ng offers API endpoints for full text search. These are as follows:

``/api/search/``
================

Get search results based on a query.

Query parameters:

*   ``query``: The query string. See
    `here <https://whoosh.readthedocs.io/en/latest/querylang.html>`_
    for details on the syntax.
*   ``page``: Specify the page you want to retrieve. Each page
    contains 10 search results and the first page is ``page=1``, which
    is the default if this is omitted.

Result list object returned by the endpoint:

.. code:: json

    {
        "count": 1,
        "page": 1,
        "page_count": 1,
        "corrected_query": "",
        "results": [

        ]
    }

*   ``count``: The approximate total number of results.
*   ``page``: The page returned to you. This might be different from
    the page you requested, if you requested a page that is behind
    the last page. In that case, the last page is returned.
*   ``page_count``: The total number of pages.
*   ``corrected_query``: Corrected version of the query string. Can be null.
    If not null, can be used verbatim to start a new query.
*   ``results``: A list of result objects on the current page.

Result object:

.. code:: json

    {
        "id": 1,
        "highlights": [

        ],
        "score": 6.34234,
        "rank": 23,
        "document": {

        }
    }

*   ``id``: the primary key of the found document
*   ``highlights``: an object containing parsable highlights for the result.
    See below.
*   ``score``: The score assigned to the document. A higher score indicates a
    better match with the query. Search results are sorted descending by score.
*   ``rank``: the position of the document within the entire search results list.
*   ``document``: The full json of the document, as returned by
    ``/api/documents/<id>/``.

Highlights object:

Highlights are provided as a list of fragments. A fragment is a longer section of
text from the original document.
Each fragment contains a list of strings, and some of them are marked as a highlight.

.. code:: json

    [
        [
            {"text": "This is a sample text with a ", "highlight": false},
            {"text": "highlighted", "highlight": true},
            {"text": " word.", "highlight": false}
        ],
        [
            {"text": "Another", "highlight": true},
            {"text": " fragment with a highlight.", "highlight": false}
        ]
    ]

A client may use this example to produce the following output:

... This is a sample text with a **highlighted** word. ... **Another** fragment with a highlight. ...

``/api/search/autocomplete/``
=============================

Get auto completions for a partial search term.

Query parameters:

*   ``term``: The incomplete term.
*   ``limit``: Amount of results. Defaults to 10.

Results returned by the endpoint are ordered by importance of the term in the
document index. The first result is the term that has the highest Tf/Idf score
in the index.

.. code:: json

    [
        "term1",
        "term3",
        "term6",
        "term4"
    ]


.. _api-file_uploads:

POSTing documents
#################

The API provides a special endpoint for file uploads:

``/api/documents/post_document/``

POST a multipart form to this endpoint, where the form field ``document`` contains
the document that you want to upload to paperless. The filename is sanitized and
then used to store the document in a temporary directory, and the consumer will
be instructed to consume the document from there.

The endpoint supports the following optional form fields:

*   ``title``: Specify a title that the consumer should use for the document.
*   ``correspondent``: Specify the ID of a correspondent that the consumer should use for the document.
*   ``document_type``: Similar to correspondent.
*   ``tags``: Similar to correspondent. Specify this multiple times to have multiple tags added
    to the document.

The endpoint will immediately return "OK" if the document consumption process
was started successfully. No additional status information about the consumption
process itself is available, since that happens in a different process.
