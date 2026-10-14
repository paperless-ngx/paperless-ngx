// Independent AppPort consumer test for the Paperless-ngx bridge.
// Real Paperless-ngx (Django) server + real bridge process; the consumer uses only the published @appport/sdk. Every success
// is checked against Paperless-ngx's own database, read directly; nothing is accepted on the bridge's word.

import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'
import { startProcess, freePort, removeDir } from '../lib/harness.mjs'
import {
	discover,
	connect,
	invoke,
	verdict,
	losingFetch,
	isCallTo,
} from '../lib/consumer.mjs'
import { startPaperless } from './support/paperless-app.mjs'

const BRIDGE = join(
	dirname(fileURLToPath(import.meta.url)),
	'..',
	'bridge.mjs'
)
let app, bridge, origin
const startBridge = async (publish) =>
	startProcess(process.execPath, [BRIDGE], {
		env: {
			APPPORT_BRIDGE_UPSTREAM: app.base,
			APPPORT_BRIDGE_PORT: String(await freePort()),
			APPPORT_BRIDGE_PUBLIC: publish ? '1' : '',
		},
		readyLine: true,
		name: 'bridge',
	})

before(async () => {
	app = await startPaperless()
	bridge = await startBridge(true)
	origin = bridge.ready.url
})
after(async () => {
	await bridge?.stop()
	await app?.stop()
	if (app) removeDir(app.work)
})

const as = async (user, fn) => {
	const c = await connect(origin, user ? app.credential(user) : undefined)
	try {
		return await fn(c)
	} finally {
		await c.close()
	}
}

test('the bridge refuses to start unless explicitly configured', async () => {
	await assert.rejects(
		startProcess(process.execPath, [BRIDGE], {
			env: { APPPORT_BRIDGE_UPSTREAM: '' },
			readyLine: true,
			timeoutMs: 5000,
			name: 'unconfigured',
		}),
		/APPPORT_BRIDGE_UPSTREAM is not set/
	)
})

test('discovery is opt-in: without APPPORT_BRIDGE_PUBLIC nothing is published', async () => {
	const quiet = await startBridge(false)
	try {
		assert.equal((await discover(quiet.ready.url)).state, 'not-published')
	} finally {
		await quiet.stop()
	}
})

test('discovery: reference-verified, three read-only capabilities, nothing established', async () => {
	const found = await discover(origin)
	assert.equal(found.state, 'reference-verified', found.reasons.join())
	assert.deepEqual(
		found.capabilities
			.map((c) => `${c.name}:${c.status}:${c.declared.effect}`)
			.sort(),
		[
			'paperless.documents.get:verified:observation',
			'paperless.documents.metadata:verified:observation',
			'paperless.documents.search:verified:observation',
		]
	)
	assert.deepEqual(found.established, {
		publisherTrust: false,
		authorization: false,
		approval: false,
		invoked: false,
	})
})

test('title search returns exactly the documents Paperless-ngx lets each user view (independent DB check)', async () => {
	for (const user of ['alice', 'bob']) {
		const out = await as(user, (c) =>
			invoke(c, 'paperless.documents.search', { title: 'Synthetic' })
		)
		const got = out.output.documents.map((d) => d.id).sort((x, y) => x - y)
		const expected = app.observeViewable(user)
		assert.equal(
			verdict(
				out,
				JSON.stringify(got) === JSON.stringify(expected) &&
					out.output.count === expected.length
			),
			'confirmed',
			`${user}: ${got} vs ${expected}`
		)
	}
	const alice = await as('alice', (c) =>
		invoke(c, 'paperless.documents.search', { title: 'Synthetic' })
	)
	assert.deepEqual(
		alice.output.documents.map((d) => d.id),
		[app.docs.alpha],
		'alice sees only the document granted to her'
	)
})

test("full-text search goes through Paperless-ngx's index and its permission filter", async () => {
	const out = await as('bob', (c) =>
		invoke(c, 'paperless.documents.search', { query: 'zebrafruit' })
	)
	assert.deepEqual(
		out.output.documents.map((d) => d.id),
		[app.docs.bravo]
	)
	assert.equal(
		verdict(out, app.observeDocument(app.docs.bravo).owner === 'bob'),
		'confirmed'
	)
})

test('results carry metadata only: no content, notes or search highlights', async () => {
	const out = await as('bob', (c) =>
		invoke(c, 'paperless.documents.search', { query: 'zebrafruit' })
	)
	const text = JSON.stringify(out.output)
	assert.ok(!text.includes('zebrafruit'), 'document text must not be returned')
	for (const k of ['content', 'notes', '__search_hit__', 'highlights'])
		assert.ok(!text.includes(`"${k}"`), k)
})

test("get: metadata confirmed against Paperless-ngx's database", async () => {
	const out = await as('alice', (c) =>
		invoke(c, 'paperless.documents.get', { id: app.docs.alpha })
	)
	const row = app.observeDocument(app.docs.alpha)
	const agrees =
		out.output.id === row.id &&
		out.output.title === row.title &&
		out.output.created.startsWith(row.created) &&
		out.output.mimeType === row.mime_type &&
		out.output.owner === row.owner_id
	assert.equal(verdict(out, agrees), 'confirmed')
})

test('metadata: checksum and filename confirmed against the database row', async () => {
	const out = await as('bob', (c) =>
		invoke(c, 'paperless.documents.metadata', { id: app.docs.bravo })
	)
	const row = app.observeDocument(app.docs.bravo)
	assert.equal(
		verdict(
			out,
			out.output.originalChecksum === row.checksum &&
				out.output.originalFilename === row.original_filename &&
				out.output.originalMimeType === row.mime_type
		),
		'confirmed'
	)
})

test("authorization is Paperless-ngx's: alice cannot read bob's document (Paperless answers 404 / 403), although it exists", async () => {
	const get = await as('alice', (c) =>
		invoke(c, 'paperless.documents.get', { id: app.docs.bravo })
	)
	assert.notEqual(get.kind, 'response')
	assert.equal(
		get.code,
		'NOT_FOUND',
		'Paperless-ngx hides documents the caller may not view'
	)
	const meta = await as('alice', (c) =>
		invoke(c, 'paperless.documents.metadata', { id: app.docs.bravo })
	)
	assert.equal(meta.kind, 'denied')
	assert.equal(meta.code, 'FORBIDDEN')
	assert.equal(
		app.observeDocument(app.docs.bravo).owner,
		'bob',
		'the document exists: this is a real refusal'
	)
})

test("without Paperless-ngx's global view permission even an owner is refused (FORBIDDEN)", async () => {
	const out = await as('dave', (c) =>
		invoke(c, 'paperless.documents.get', { id: app.docs.charlie })
	)
	assert.equal(out.kind, 'denied')
	assert.equal(out.code, 'FORBIDDEN')
	assert.equal(app.observeDocument(app.docs.charlie).owner, 'dave')
})

test('no credential: refused by AppPort (UNAUTHORIZED); an invalid token is rejected by Paperless-ngx', async () => {
	assert.equal(
		(
			await as(undefined, (c) =>
				invoke(c, 'paperless.documents.search', { title: 'Synthetic' })
			)
		).code,
		'UNAUTHORIZED'
	)
	const c = await connect(
		origin,
		'Token 0000000000000000000000000000000000000000'
	)
	try {
		const out = await invoke(c, 'paperless.documents.search', {
			title: 'Synthetic',
		})
		assert.equal(out.kind, 'denied')
		assert.equal(out.code, 'UNAUTHORIZED')
	} finally {
		await c.close()
	}
})

test('application-level failure: a missing document is NOT_FOUND; malformed input is INVALID_INPUT', async () => {
	const missing = await as('bob', (c) =>
		invoke(c, 'paperless.documents.get', { id: 987654 })
	)
	assert.equal(verdict(missing), 'failed')
	assert.equal(missing.code, 'NOT_FOUND')
	assert.equal(app.observeDocument(987654), undefined)
	assert.equal(
		(await as('bob', (c) => invoke(c, 'paperless.documents.get', { id: 0 })))
			.code,
		'INVALID_INPUT'
	)
	assert.equal(
		(
			await as('bob', (c) =>
				invoke(c, 'paperless.documents.search', { pageSize: 1000 })
			)
		).code,
		'INVALID_INPUT'
	)
})

test('a lost response is indeterminate, never confirmed, and is not retried', async () => {
	let sends = 0
	const lose = losingFetch(isCallTo('paperless.documents.get'))
	const c = await connect(origin, app.credential('alice'), {
		fetch: async (u, i) => {
			if (isCallTo('paperless.documents.get')(String(u), i)) sends++
			return lose(u, i)
		},
	})
	try {
		const out = await invoke(c, 'paperless.documents.get', {
			id: app.docs.alpha,
		})
		assert.equal(out.kind, 'no-response')
		assert.equal(verdict(out, true), 'indeterminate')
		assert.equal(sends, 1)
	} finally {
		await c.close()
	}
})

test('cleanup: stopping removes the disposable Paperless-ngx data', async () => {
	const work = app.work
	await bridge.stop()
	await app.stop()
	removeDir(work)
	assert.equal(existsSync(work), false)
	bridge = null
	app = null
})
