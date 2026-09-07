# External suggestion provider

[Fork development and local review](README.md)

Configure a trusted HTTP service on the web process and Celery workers:

```ini
PAPERLESS_AI_ENABLED=true
PAPERLESS_AI_SUGGESTIONS_ENDPOINT=http://provider:8080/suggestions
PAPERLESS_AI_SUGGESTIONS_API_KEY=provider-specific-secret
PAPERLESS_AI_SUGGESTIONS_ALLOW_INTERNAL=true
PAPERLESS_AI_SUGGESTIONS_TIMEOUT=120
```

An empty endpoint retains upstream classification. The native AI enable switch
still controls feature visibility. The provider replaces classification only;
embedding and chat configuration remain independent. Use HTTPS outside a trusted
local network. Internal destinations require opt-in. Connections are DNS-pinned;
redirects and environment proxies are disabled. The optional API key is sent as
a Bearer header. The timeout applies to HTTP connection/read operations.

## Suggestion request

Native **Suggest** and **Apply AI Suggestions** POST to the same endpoint:

| Field | Meaning |
| --- | --- |
| `protocol_version` | Integer `1`. |
| `event` | `suggestions.requested`. |
| `request_id` | Unique request identifier; echo it in the response. |
| `context_id` | Opaque context fingerprint; echo it unchanged. |
| `requester_id` | Interactive user's ID; workflows use the document owner's ID, or `null` for an unowned document. |
| `output_language` | Requested output language, or `null`. |
| `document` | Saved metadata, tags, typed custom-field values, complete Content and its source version. |
| `taxonomy` | Visible `{id, name}` objects for tags, correspondents, document types and storage paths. |
| `classic_suggestions` | Native matching candidates as IDs and parsed date strings. |

`document.id` is the metadata document. `document.content_version.id`,
`version_index`, checksums and original filename identify the source of Content:
the latest version for a root document, or the explicitly addressed version
document. Metadata includes owner, modified date, title, created date,
correspondent, document type, Storage Path, tags, archive serial number and
custom fields (`field`, `name`, `data_type`, `value`). An OCR text change changes
context even if the original file checksum remains the same.

Return HTTP 200 with JSON:

```json
{
  "protocol_version": 1,
  "request_id": "echo the request value",
  "context_id": "echo the request value",
  "suggestions": {
    "title": "Suggested title",
    "tags": {"existing_ids": [], "new_names": []},
    "correspondents": {"existing_ids": [], "new_names": []},
    "document_types": {"existing_ids": [], "new_names": []},
    "storage_paths": {"existing_ids": [], "new_names": []},
    "dates": ["2026-01-02"]
  }
}
```

All suggestion fields are required. IDs must come from the supplied taxonomy.
Title and names are limited to 128 characters; each category permits up to 100
IDs and eight new names; at most three valid ISO dates are accepted. Responses
are capped at 1 MiB. Unknown fields, incorrect types and mismatched request/context
IDs are rejected. For existing-taxonomy-only policies return no `new_names`.
Leave Storage Path choices empty when that field should remain Paperless-managed.

Request handling must be read-only with respect to the document. Paperless
re-reads saved state after the response; a changed version, Content, metadata,
tags or custom fields rejects the proposal as stale. Add-on writes follow a save
notification or automatic-application notification, not suggestion generation.

Paperless does not cache external suggestions. The provider may reuse results
using the context fingerprint **and its own rules/configuration/model revision**,
while echoing each incoming request ID. The editor reports stale state as HTTP
409, transient provider failure as 503 and invalid responses as 502. Failed
external requests do not silently fall back to native LLM classification. The
workflow task retries transient failures and stale inputs up to three times.
Permanent failures fail the task without applying suggestions.

## Automatic-application notification

After a native workflow changes metadata, a separate Celery task POSTs
`event: suggestions.applied` to the same endpoint. It contains `protocol_version`,
`event_id`, `document_id`, `content_version_id`, `document_state_id`,
`workflow_action_id` and `changed_fields`; Content is not repeated. Acknowledge
with HTTP 200 and `{"event_id": "the received event ID"}`.

The receiver deduplicates by `event_id` and re-reads current Paperless state
before enrichment. Notification retries keep that ID and never repeat
classification or metadata application. Transient delivery failures retry up
to five times and then remain visible in Celery worker logs. Delivery depends
on the existing task broker; no transactional-outbox guarantee is provided.

Normal user saves continue to use native Document Updated workflows. Automatic
AI application uses the dedicated callback to avoid an Updated → Apply AI loop.
Native field selection, create-missing, overwrite and additive-tag behavior
remain authoritative. Rules, inference, review status and add-on custom-field
ownership belong to the external service.
