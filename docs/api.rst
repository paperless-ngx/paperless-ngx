
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

Full text searching is available on the ``/api/documents/`` endpoint. Two specific
query parameters cause the API to return full text search results:

*   ``/api/documents/?query=your%20search%20query``: Search for a document using a full text query.
    For details on the syntax, see :ref:`basic-usage_searching`.

*   ``/api/documents/?more_like=1234``: Search for documents similar to the document with id 1234.

Pagination works exactly the same as it does for normal requests on this endpoint.

Certain limitations apply to full text queries:

*   Results are always sorted by search score. The results matching the query best will show up first.

*   Only a small subset of filtering parameters are supported.

Furthermore, each returned document has an additional ``__search_hit__`` attribute with various information
about the search results:

.. code::

    {
        "count": 31,
        "next": "http://localhost:8000/api/documents/?page=2&query=test",
        "previous": null,
        "results": [

            ...

            {
                "id": 123,
                "title": "title",
                "content": "content",

                ...

                "__search_hit__": {
                    "score": 0.343,
                    "highlights": "text <span class=\"match\">Test</span> text",
                    "rank": 23
                }
            },

            ...

        ]
    }

*   ``score`` is an indication how well this document matches the query relative to the other search results.
*   ``highlights`` is an excerpt from the document content and highlights the search terms with ``<span>`` tags as shown above.
*   ``rank`` is the index of the search results. The first result will have rank 0.

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


.. _api-versioning:

API Versioning
##############

The REST API is versioned since Paperless-ng 1.3.0.

* Versioning ensures that changes to the API don't break older clients.
* Clients specify the specific version of the API they wish to use with every request and Paperless will handle the request using the specified API version.
* Even if the underlying data model changes, older API versions will always serve compatible data.
* If no version is specified, Paperless will serve version 1 to ensure compatibility with older clients that do not request a specific API version.

API versions are specified by submitting an additional HTTP ``Accept`` header with every request:

.. code::

    Accept: application/json; version=6

If an invalid version is specified, Paperless 1.3.0 will respond with "406 Not Acceptable" and an error message in the body.
Earlier versions of Paperless will serve API version 1 regardless of whether a version is specified via the ``Accept`` header.

If a client wishes to verify whether it is compatible with any given server, the following procedure should be performed:

1.  Perform an *authenticated* request against any API endpoint. If the server is on version 1.3.0 or newer, the server will
    add two custom headers to the response:

    .. code::

        X-Api-Version: 2
        X-Version: 1.3.0

2.  Determine whether the client is compatible with this server based on the presence/absence of these headers and their values if present.


API Changelog
=============

Version 1
---------

Initial API version.

Version 2
---------

* Added field ``Tag.color``. This read/write string field contains a hex color such as ``#a6cee3``.
* Added read-only field ``Tag.text_color``. This field contains the text color to use for a specific tag, which is either black or white depending on the brightness of ``Tag.color``.
* Removed field ``Tag.colour``.
