# Document review

Document review is part of the existing document detail screen (Review tab) and
the sidebar Review queue. It never grants document access or changes downloads.

## Setup and migration

Use the normal development setup in [development.md](development.md). No new
Python or JavaScript dependencies, external services, or credentials are needed.
The locked frontend currently requires Node 24.15+ and pnpm 11.15.1. Install
Ghostscript, Tesseract, Poppler, qpdf, libmagic and **unpaper** for OCR regression
tests; refresh the package index before installing system packages.

From the repository root:

```sh
uv sync --group dev --group typing
.venv/bin/prek install
pnpm install --frozen-lockfile --dir src-ui
mkdir -p consume media
# Supply PAPERLESS_SECRET_KEY through the development environment (not source control).
.venv/bin/python src/manage.py migrate
.venv/bin/python src/manage.py makemigrations --check --dry-run
.venv/bin/python src/manage.py check
```

Migration `documents.0028` creates two sparse review tables and their indexes and
constraints. It does not update existing document rows, permissions, versions,
metadata or files. An absent review row means unreviewed at revision zero.
Back up the database before deployment and run migrations before starting the
updated application/workers. Database persistence is sufficient for state,
history and successful-request replay across restarts.

Review mutations are synchronous and need no new worker. Existing workers still
perform ingestion, version creation and reprocessing; deploy the updated Python
code to them too so their content writes invalidate reviews. Review invalidation
does not approve a document or grant any permissions.

## API and permissions

- `GET /api/documents/{id}/review/`: state, revision, assignment and ordered history.
- `POST /api/documents/{id}/review/`: `action`, `expected_revision`, `request_id`.
  Submit also requires `reviewer`; reject requires `comment`. Neither field is
  accepted for other actions. Rejection comments are trimmed, with 1-2000 Unicode
  code points. The endpoint rejects all unexpected fields.
- `GET /api/documents/{id}/reviewers/?search=...`: permitted actions and up to 50
  eligible reviewer usernames for this document; search allows finding other
  eligible users without access to the administrative user directory.
- `GET /api/review_queue/?state=pending&reviewer=42&page=1&page_size=20`: only
  visible, non-trashed reviewed records, ordered by document ID. Filters apply
  before counting/pagination; page size must be 1-100.

Use existing global **and** effective object permissions, including ownership,
groups and superusers. Version documents use their root's effective permissions.
Submit/reopen and reviewers require view and change. Only the assigned reviewer
can decide; neither self-review nor superuser assignment bypasses are allowed.
Inaccessible documents return 404. Invalid assignments return a generic 400.

Transitions are unreviewed -> pending -> approved/rejected. Reopen moves either
terminal state to unreviewed and clears assignment. Invalid transitions or stale
revisions return 409 without changes. Retries use a UUID scoped to document and
actor: identical successful payloads return the original response; different
payloads return 409. Current access is rechecked before replay. The UI retains the
key on network failures and reloads current state after a conflict.

## Content, versions and history

Content/checksum changes, version addition/removal and merges atomically reset
pending/approved reviews to unreviewed, increment revision and append `invalidate`.
Title-only changes and no-op content/checksum writes do not invalidate. The
invalidation actor is the initiating user when supplied by the existing operation,
otherwise null (background work). Comments are rendered through text interpolation.

Document model saves and review-aware querysets share a document write lock with
review decisions. Version updates also lock/invalidate the root. Queryset content
updates compare bounded batches of 200 rows. Event revision and request-key
uniqueness are enforced by the database. Successful response state is stored;
immutable history prefixes reconstruct retries without quadratic history copies.

Trash disallows review actions, while preserving state/history for restore.
Permanent deletion cascades to review state, events and successful-request data.
Raw SQL writes and `save_base()` bypass model/queryset hooks: custom extensions
must use normal document saves/updates or explicitly lock and invalidate reviews.

## Developer validation

```sh
# Backend: from src/
../.venv/bin/pytest documents/tests/test_review.py -n 2 --no-cov -q
../.venv/bin/pytest documents/tests -n 4 --no-cov -q

# Frontend: from src-ui/
pnpm exec jest --runInBand --coverage=false --testPathPatterns='document-review|review-queue'
pnpm exec jest --runInBand --coverage=false
pnpm exec tsc --noEmit -p tsconfig.app.json
pnpm ng lint
pnpm ng build
```

Do not set `NODE_OPTIONS=--experimental-vm-modules` for this repository's Jest
configuration: its zoneless setup uses CommonJS and fails with an ESM require
cycle under that flag. Production builds may warn about untranslated strings;
new review labels currently fall back to English. There is no `development`
build configuration in the existing Angular workspace.

Run pre-commit against changed/new source files. When invoking Prettier from the
repository root, set `NODE_PATH=$PWD/src-ui/node_modules` so its existing organize
imports plugin resolves correctly.

Database restart durability was validated using two independent Django processes
and a fresh migrated SQLite database: the second process read identical state and
history and replayed the first process's approval without another event.
Automated feature/concurrency tests also use SQLite; verify deployment-specific
PostgreSQL/MariaDB behavior in staging.
The handoff report records actual regression results and any untested gaps.
