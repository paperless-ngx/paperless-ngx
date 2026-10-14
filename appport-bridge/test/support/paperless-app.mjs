// Disposable Paperless-ngx instance for the consumer test: the real Django application, SQLite in a temp dir, synthetic
// users, permissions, tokens and documents (tiny placeholder files; no OCR, consumer, Celery or Redis). Test-only.
//
// PAPERLESS_PYTHON=/path/to/python   the interpreter of a synced environment (default: <repo>/.venv/bin/python,
//                                    as created by `uv sync`).

import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { randomBytes } from 'node:crypto'
import {
	startProcess,
	freePort,
	tempDir,
	openOracle,
} from '../../lib/harness.mjs'

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const SRC = join(REPO, 'src')

// Runs inside `manage.py shell`. Synthetic users, grants, tokens and documents through Django's ORM and guardian, exactly as
// Paperless-ngx's own code stores them. Prints one JSON line; no document text is printed.
const SEED = String.raw`
import hashlib, datetime, json
from django.conf import settings
from django.contrib.auth.models import User, Permission
from rest_framework.authtoken.models import Token
from guardian.shortcuts import assign_perm
from documents.models import Document
admin = User.objects.create_superuser("admin0", "admin0@example.invalid", "synthetic-admin-pw-0")
alice = User.objects.create_user("alice", password="synthetic-alice-pw-1")
bob = User.objects.create_user("bob", password="synthetic-bob-pw-2")
dave = User.objects.create_user("dave", password="synthetic-dave-pw-3")
view = Permission.objects.get(codename="view_document", content_type__app_label="documents")
alice.user_permissions.add(view); bob.user_permissions.add(view)
settings.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
def mk(title, owner, body, fname):
    data = b"%PDF-1.4\n% synthetic placeholder " + fname.encode() + b"\n%%EOF\n"
    (settings.ORIGINALS_DIR / fname).write_bytes(data)
    return Document.objects.create(title=title, owner=owner, content=body, mime_type="application/pdf", checksum=hashlib.sha256(data).hexdigest(),
        filename=fname, original_filename=fname, created=datetime.date(2026, 1, 15))
a = mk("Synthetic invoice alpha", admin, "zebrafruit alpha synthetic text", "syn_a.pdf")
b = mk("Synthetic invoice bravo", bob, "zebrafruit bravo synthetic text", "syn_b.pdf")
c = mk("Synthetic receipt charlie", dave, "zebrafruit charlie synthetic text", "syn_c.pdf")
assign_perm("view_document", alice, a)
print(json.dumps({"tokens": {u.username: Token.objects.create(user=u).key for u in (admin, alice, bob, dave)}, "docs": {"alpha": a.pk, "bravo": b.pk, "charlie": c.pk}}))
`

export async function startPaperless() {
	const work = tempDir('paperless-appport-')
	const data = join(work, 'data'),
		media = join(work, 'media'),
		consume = join(work, 'consume')
	for (const d of [join(data, 'index'), media, consume])
		mkdirSync(d, { recursive: true }) // index/ must exist (Docker's init does this)
	const python =
		process.env.PAPERLESS_PYTHON ?? join(REPO, '.venv', 'bin', 'python')
	const env = {
		...process.env,
		PAPERLESS_DATA_DIR: data,
		PAPERLESS_MEDIA_ROOT: media,
		PAPERLESS_CONSUMPTION_DIR: consume,
		PAPERLESS_SECRET_KEY: randomBytes(32).toString('hex'),
		PAPERLESS_CACHE_BACKEND: 'django.core.cache.backends.locmem.LocMemCache',
		PAPERLESS_CHANNELS_BACKEND: 'channels.layers.InMemoryChannelLayer',
		PAPERLESS_REDIS: 'redis://127.0.0.1:1',
		PAPERLESS_DISABLE_DBHANDLER: 'true',
		PAPERLESS_TOKEN_THROTTLE_RATE: '1000/min',
	}
	const manage = (...args) =>
		execFileSync(python, ['manage.py', ...args], {
			cwd: SRC,
			env,
			encoding: 'utf8',
			stdio: ['ignore', 'pipe', 'pipe'],
		})
	manage('migrate', '--no-input')
	const seed = JSON.parse(
		manage('shell', '--command', SEED).trim().split('\n').pop()
	)
	manage('document_index', 'reindex', '--no-progress-bar') // full-text index built before the server opens it

	const port = await freePort()
	const base = `http://127.0.0.1:${port}`
	const proc = await startProcess(
		python,
		['manage.py', 'runserver', `127.0.0.1:${port}`, '--noreload'],
		{
			cwd: SRC,
			env,
			readyUrl: `${base}/api/`,
			name: 'paperless',
			timeoutMs: 120_000,
		}
	)

	const credential = (u) => `Token ${seed.tokens[u]}`
	const oracle = await openOracle(join(data, 'db.sqlite3'))
	return {
		base,
		work,
		docs: seed.docs,
		credential,
		/** Independent observation: Paperless-ngx's own documents_document row, read directly (read-only). */
		observeDocument: (id) =>
			oracle.get(
				`SELECT d.id, d.title, d.checksum, d.created, d.mime_type, d.original_filename, d.owner_id, d.correspondent_id, d.deleted_at, u.username AS owner
      FROM documents_document d LEFT JOIN auth_user u ON u.id = d.owner_id WHERE d.id = ?`,
				id
			),
		/** Ids Paperless-ngx's rules let `username` view: global view permission AND (owner, unowned, or a guardian grant). */
		observeViewable: (username) =>
			oracle
				.all(
					`SELECT d.id FROM documents_document d, auth_user u WHERE u.username = ? AND d.deleted_at IS NULL
        AND (u.is_superuser = 1 OR EXISTS (SELECT 1 FROM auth_user_user_permissions up JOIN auth_permission p ON p.id = up.permission_id WHERE up.user_id = u.id AND p.codename = 'view_document'))
        AND (u.is_superuser = 1 OR d.owner_id = u.id OR d.owner_id IS NULL OR EXISTS (
          SELECT 1 FROM guardian_userobjectpermission g JOIN auth_permission p ON p.id = g.permission_id
          WHERE g.user_id = u.id AND p.codename = 'view_document' AND g.object_pk = CAST(d.id AS TEXT)))
      ORDER BY d.id`,
					username
				)
				.map((r) => r.id),
		async stop() {
			oracle.close()
			await proc.stop()
		},
	}
}
