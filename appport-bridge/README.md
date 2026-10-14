# AppPort bridge for Paperless-ngx (opt-in, read-only)

A small, separate Node.js process that lets an [AppPort](https://www.npmjs.com/package/@appport/sdk) consumer discover
and call three **read-only** Paperless-ngx capabilities. It does not change Paperless-ngx: no Python code, models,
migrations, settings or frontend are touched, and nothing runs unless you start it. It is not a second backend and keeps
no index or document store of its own.

| Capability                       | Paperless-ngx endpoint used                                | Returns                                                                   |
| -------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------- |
| `paperless.documents.search@1`   | `GET /api/documents/?title__icontains=…` and/or `?query=…` | id, title, dates, owner, correspondent, type, tags, MIME type, page count |
| `paperless.documents.get@1`      | `GET /api/documents/{id}/?fields=…`                        | the same metadata for one document                                        |
| `paperless.documents.metadata@1` | `GET /api/documents/{id}/metadata/`                        | checksums, sizes, MIME type, original filename                            |

`title` search is answered from the database and is always current; `query` uses Paperless-ngx's full-text index and is
as current as that index.

## How authority stays with Paperless-ngx

- **Trusted-boundary mode** (`@appport/server` README): every call is forwarded to Paperless-ngx's own REST API (API
  version 10) with the **caller's own Paperless-ngx token** (`Authorization: Token <key>`). Paperless-ngx's views, filter
  sets and document permissions (the `view_document` model permission plus ownership / django-guardian object grants)
  decide everything.
- The bridge has **no credential of its own**, **stores nothing**, and never logs tokens or document data.
- **Document contents are not exposed.** The bridge always sends an explicit `fields=` list, so OCR text, notes and
  search highlights are never requested; from `/metadata/` it returns only file-level details, never embedded file
  metadata, barcodes or language.
- AppPort only checks that a credential was presented (anonymous calls get `UNAUTHORIZED` without reaching
  Paperless-ngx). Paperless-ngx's answers map to AppPort errors: 401 → `UNAUTHORIZED`, 403 → `FORBIDDEN`,
  404 → `NOT_FOUND`, 400 → `INVALID_INPUT`. Paperless-ngx answers **404** on `/api/documents/{id}/` but **403** on
  `/api/documents/{id}/metadata/` for a document the caller may not view; the bridge passes both through unchanged.
- Discovery is opt-in (`APPPORT_BRIDGE_PUBLIC=1`) and is never authorization.

## Run

```sh
cd appport-bridge && npm ci
APPPORT_BRIDGE_UPSTREAM=http://127.0.0.1:8000 APPPORT_BRIDGE_PORT=4430 APPPORT_BRIDGE_PUBLIC=1 npm start
```

```js
import { AppPort } from '@appport/sdk'
const app = await AppPort.discover({
  origin: 'http://127.0.0.1:4430',
  headers: { authorization: 'Token <your key>' },
})
const { documents } = await app.call(
  'paperless.documents.search',
  { title: 'invoice' },
  { version: 1 }
)
```

The bridge listens on `127.0.0.1` unless `APPPORT_BRIDGE_HOST` says otherwise. Put TLS in front of it before exposing it
beyond localhost: callers send their Paperless-ngx tokens to it.

## Test

`npm test` runs the **real Paperless-ngx Django application** (`manage.py migrate` and `runserver`, SQLite in a temp dir,
in-memory cache and channels; `PAPERLESS_PYTHON` points at a `uv sync`-ed interpreter, default `../.venv/bin/python`). It
creates synthetic users, permissions, guardian grants, tokens and placeholder documents with Paperless-ngx's own ORM,
builds the full-text index with `document_index reindex`, starts the bridge, and checks everything as an independent
consumer using only the published `@appport/sdk`:

- discovery is opt-in and `reference-verified`; it establishes no trust, authorization or approval
- every successful result is compared with **Paperless-ngx's own `documents_document` row and permission tables, read
  directly** (read-only)
- alice sees only the document granted to her; bob's document is refused to her (404 on detail, 403 on metadata) though
  the database shows it exists; a user without the global view permission is refused even for a document they own
- no credential → `UNAUTHORIZED`; an invalid token is rejected by Paperless-ngx
- a missing document is `NOT_FOUND`; malformed input is `INVALID_INPUT`; results never contain document text
- a lost response is _indeterminate_, never confirmed, and is sent once
- all disposable data is removed

No OCR, consumer, Celery, Redis or external service is needed. Package versions are pinned exactly (`@appport/sdk` 1.2.2)
and installed from the npm registry via `package-lock.json`. Requires Node 22.13+.
