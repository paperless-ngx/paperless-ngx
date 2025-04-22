# The REST API

Paperless-ngx now ships with a fully-documented REST API and a browsable
web interface to explore it. The API browsable interface is available at
`/api/schema/view/`.

Further documentation is provided here for some endpoints and features.

## Authorization

The REST api provides four different forms of authentication.

1.  Basic authentication

    Authorize by providing a HTTP header in the form

    ```
    Authorization: Basic <credentials>
    ```

    where `credentials` is a base64-encoded string of
    `<username>:<password>`

2.  Session authentication

    When you're logged into paperless in your browser, you're
    automatically logged into the API as well and don't need to provide
    any authorization headers.

3.  Token authentication

    You can create (or re-create) an API token by opening the "My Profile"
    link in the user dropdown found in the web UI and clicking the circular
    arrow button.

    Paperless also offers an endpoint to acquire authentication tokens.

    POST a username and password as a form or json string to
    `/api/token/` and paperless will respond with a token, if the login
    data is correct. This token can be used to authenticate other
    requests with the following HTTP header:

    ```
    Authorization: Token <token>
    ```

    Tokens can also be managed in the Django admin.

4.  Remote User authentication

    If enabled (see
    [configuration](configuration.md#PAPERLESS_ENABLE_HTTP_REMOTE_USER_API)),
    you can authenticate against the API using Remote User auth.

## Searching for documents

Full text searching is available on the `/api/documents/` endpoint. Two
specific query parameters cause the API to return full text search
results:

-   `/api/documents/?query=your%20search%20query`: Search for a document
    using a full text query. For details on the syntax, see [Basic Usage - Searching](usage.md#basic-usage_searching).
-   `/api/documents/?more_like_id=1234`: Search for documents similar to
    the document with id 1234.

Pagination works exactly the same as it does for normal requests on this
endpoint.

Furthermore, each returned document has an additional `__search_hit__`
attribute with various information about the search results:

```
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
                "highlights": "text <span class="match">Test</span> text",
                "rank": 23
            }
        },

        ...

    ]
}
```

-   `score` is an indication how well this document matches the query
    relative to the other search results.
-   `highlights` is an excerpt from the document content and highlights
    the search terms with `<span>` tags as shown above.
-   `rank` is the index of the search results. The first result will
    have rank 0.

### Filtering by custom fields

You can filter documents by their custom field values by specifying the
`custom_field_query` query parameter. Here are some recipes for common
use cases:

1. Documents with a custom field "due" (date) between Aug 1, 2024 and
   Sept 1, 2024 (inclusive):

    `?custom_field_query=["due", "range", ["2024-08-01", "2024-09-01"]]`

2. Documents with a custom field "customer" (text) that equals "bob"
   (case sensitive):

    `?custom_field_query=["customer", "exact", "bob"]`

3. Documents with a custom field "answered" (boolean) set to `true`:

    `?custom_field_query=["answered", "exact", true]`

4. Documents with a custom field "favorite animal" (select) set to either
   "cat" or "dog":

    `?custom_field_query=["favorite animal", "in", ["cat", "dog"]]`

5. Documents with a custom field "address" (text) that is empty:

    `?custom_field_query=["OR", ["address", "isnull", true], ["address", "exact", ""]]`

6. Documents that don't have a field called "foo":

    `?custom_field_query=["foo", "exists", false]`

7. Documents that have document links "references" to both document 3 and 7:

    `?custom_field_query=["references", "contains", [3, 7]]`

All field types support basic operations including `exact`, `in`, `isnull`,
and `exists`. String, URL, and monetary fields support case-insensitive
substring matching operations including `icontains`, `istartswith`, and
`iendswith`. Integer, float, and date fields support arithmetic comparisons
including `gt` (>), `gte` (>=), `lt` (<), `lte` (<=), and `range`.
Lastly, document link fields support a `contains` operator that behaves
like a "is superset of" check.

### `/api/search/autocomplete/`

Get auto completions for a partial search term.

Query parameters:

-   `term`: The incomplete term.
-   `limit`: Amount of results. Defaults to 10.

Results returned by the endpoint are ordered by importance of the term
in the document index. The first result is the term that has the highest
[Tf/Idf](https://en.wikipedia.org/wiki/Tf%E2%80%93idf) score in the index.

```json
["term1", "term3", "term6", "term4"]
```

## POSTing documents {#file-uploads}

The API provides a special endpoint for file uploads:

`/api/documents/post_document/`

POST a multipart form to this endpoint, where the form field `document`
contains the document that you want to upload to paperless. The filename
is sanitized and then used to store the document in a temporary
directory, and the consumer will be instructed to consume the document
from there.

The endpoint supports the following optional form fields:

-   `title`: Specify a title that the consumer should use for the
    document.
-   `created`: Specify a DateTime where the document was created (e.g.
    "2016-04-19" or "2016-04-19 06:15:00+02:00").
-   `correspondent`: Specify the ID of a correspondent that the consumer
    should use for the document.
-   `document_type`: Similar to correspondent.
-   `storage_path`: Similar to correspondent.
-   `tags`: Similar to correspondent. Specify this multiple times to
    have multiple tags added to the document.
-   `archive_serial_number`: An optional archive serial number to set.
-   `custom_fields`: An array of custom field ids to assign (with an empty
    value) to the document.

The endpoint will immediately return HTTP 200 if the document consumption
process was started successfully, with the UUID of the consumption task
as the data. No additional status information about the consumption process
itself is available immediately, since that happens in a different process.
However, querying the tasks endpoint with the returned UUID e.g.
`/api/tasks/?task_id={uuid}` will provide information on the state of the
consumption including the ID of a created document if consumption succeeded.

## Permissions

All objects (documents, tags, etc.) allow setting object-level permissions
with optional `owner` and / or a `set_permissions` parameters which are of
the form:

```
"owner": ...,
"set_permissions": {
    "view": {
        "users": [...],
        "groups": [...],
    },
    "change": {
        "users": [...],
        "groups": [...],
    },
}
```

!!! note

    Arrays should contain user or group ID numbers.

If these parameters are supplied the object's permissions will be overwritten,
assuming the authenticated user has permission to do so (the user must be
the object owner or a superuser).

### Retrieving full permissions

By default, the API will return a truncated version of object-level
permissions, returning `user_can_change` indicating whether the current user
can edit the object (either because they are the object owner or have permissions
granted). You can pass the parameter `full_perms=true` to API calls to view the
full permissions of objects in a format that mirrors the `set_permissions`
parameter above.

## Bulk Editing

The API supports various bulk-editing operations which are executed asynchronously.

### Documents

For bulk operations on documents, use the endpoint `/api/documents/bulk_edit/` which accepts
a json payload of the format:

```json
{
  "documents": [LIST_OF_DOCUMENT_IDS],
  "method": METHOD, // see below
  "parameters": args // see below
}
```

The following methods are supported:

-   `set_correspondent`
    -   Requires `parameters`: `{ "correspondent": CORRESPONDENT_ID }`
-   `set_document_type`
    -   Requires `parameters`: `{ "document_type": DOCUMENT_TYPE_ID }`
-   `set_storage_path`
    -   Requires `parameters`: `{ "storage_path": STORAGE_PATH_ID }`
-   `add_tag`
    -   Requires `parameters`: `{ "tag": TAG_ID }`
-   `remove_tag`
    -   Requires `parameters`: `{ "tag": TAG_ID }`
-   `modify_tags`
    -   Requires `parameters`: `{ "add_tags": [LIST_OF_TAG_IDS] }` and `{ "remove_tags": [LIST_OF_TAG_IDS] }`
-   `delete`
    -   No `parameters` required
-   `reprocess`
    -   No `parameters` required
-   `set_permissions`
    -   Requires `parameters`:
        -   `"set_permissions": PERMISSIONS_OBJ` (see format [above](#permissions)) and / or
        -   `"owner": OWNER_ID or null`
        -   `"merge": true or false` (defaults to false)
    -   The `merge` flag determines if the supplied permissions will overwrite all existing permissions (including
        removing them) or be merged with existing permissions.
-   `merge`
    -   No additional `parameters` required.
    -   The ordering of the merged document is determined by the list of IDs.
    -   Optional `parameters`:
        -   `"metadata_document_id": DOC_ID` apply metadata (tags, correspondent, etc.) from this document to the merged document.
        -   `"delete_originals": true` to delete the original documents. This requires the calling user being the owner of
            all documents that are merged.
-   `split`
    -   Requires `parameters`:
        -   `"pages": [..]` The list should be a list of pages and/or a ranges, separated by commas e.g. `"[1,2-3,4,5-7]"`
    -   Optional `parameters`:
        -   `"delete_originals": true` to delete the original document after consumption. This requires the calling user being the owner of
            the document.
    -   The split operation only accepts a single document.
-   `rotate`
    -   Requires `parameters`:
        -   `"degrees": DEGREES`. Must be an integer i.e. 90, 180, 270
-   `delete_pages`
    -   Requires `parameters`:
        -   `"pages": [..]` The list should be a list of integers e.g. `"[2,3,4]"`
    -   The delete_pages operation only accepts a single document.
-   `modify_custom_fields`
    -   Requires `parameters`:
        -   `"add_custom_fields": { CUSTOM_FIELD_ID: VALUE }`: JSON object consisting of custom field id:value pairs to add to the document, can also be a list of custom field IDs
            to add with empty values.
        -   `"remove_custom_fields": [CUSTOM_FIELD_ID]`: custom field ids to remove from the document.

### Objects

Bulk editing for objects (tags, document types etc.) currently supports set permissions or delete
operations, using the endpoint: `/api/bulk_edit_objects/`, which requires a json payload of the format:

```json
{
  "objects": [LIST_OF_OBJECT_IDS],
  "object_type": "tags", "correspondents", "document_types" or "storage_paths",
  "operation": "set_permissions" or "delete",
  "owner": OWNER_ID, // optional
  "permissions": { "view": { "users": [] ... }, "change": { ... } }, // (see 'set_permissions' format above)
  "merge": true / false // defaults to false, see above
}
```

## API Versioning

The REST API is versioned since Paperless-ngx 1.3.0.

-   Versioning ensures that changes to the API don't break older
    clients.
-   Clients specify the specific version of the API they wish to use
    with every request and Paperless will handle the request using the
    specified API version.
-   Even if the underlying data model changes, older API versions will
    always serve compatible data.
-   If no version is specified, Paperless will serve version 1 to ensure
    compatibility with older clients that do not request a specific API
    version.

API versions are specified by submitting an additional HTTP `Accept`
header with every request:

```
Accept: application/json; version=6
```

If an invalid version is specified, Paperless 1.3.0 will respond with
"406 Not Acceptable" and an error message in the body. Earlier
versions of Paperless will serve API version 1 regardless of whether a
version is specified via the `Accept` header.

If a client wishes to verify whether it is compatible with any given
server, the following procedure should be performed:

1.  Perform an _authenticated_ request against any API endpoint. If the
    server is on version 1.3.0 or newer, the server will add two custom
    headers to the response:

    ```
    X-Api-Version: 2
    X-Version: 1.3.0
    ```

2.  Determine whether the client is compatible with this server based on
    the presence/absence of these headers and their values if present.

### API Version Deprecation Policy

Older API versions are guaranteed to be supported for at least one year
after the release of a new API version. After that, support for older
API versions may be (but is not guaranteed to be) dropped.

### API Changelog

#### Version 1

Initial API version.

#### Version 2

-   Added field `Tag.color`. This read/write string field contains a hex
    color such as `#a6cee3`.
-   Added read-only field `Tag.text_color`. This field contains the text
    color to use for a specific tag, which is either black or white
    depending on the brightness of `Tag.color`.
-   Removed field `Tag.colour`.

#### Version 3

-   Permissions endpoints have been added.
-   The format of the `/api/ui_settings/` has changed.

#### Version 4

-   Consumption templates were refactored to workflows and API endpoints
    changed as such.

#### Version 5

-   Added bulk deletion methods for documents and objects.

#### Version 6

-   Moved acknowledge tasks endpoint to be under `/api/tasks/acknowledge/`.

#### Version 7

-   The format of select type custom fields has changed to return the options
    as an array of objects with `id` and `label` fields as opposed to a simple
    list of strings. When creating or updating a custom field value of a
    document for a select type custom field, the value should be the `id` of
    the option whereas previously was the index of the option.

#### Version 8

-   The user field of document notes now returns a simplified user object
    rather than just the user ID.
