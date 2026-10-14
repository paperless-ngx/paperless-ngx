// Paperless-ngx AppPort bridge: read-only capabilities over Paperless-ngx's own REST API (/api/documents/), called with the
// caller's own Paperless-ngx API token (`Authorization: Token <key>`). Paperless-ngx's views, filters and document-level
// permissions (model permission + owner / django-guardian grants) decide everything; this process stores nothing.
//
// Document contents are treated as sensitive: the bridge always asks for an explicit field list, so OCR text, notes,
// search highlights and embedded file metadata are never requested, returned or logged.
//
//   APPPORT_BRIDGE_UPSTREAM=http://127.0.0.1:8000 [APPPORT_BRIDGE_PORT=4430] [APPPORT_BRIDGE_PUBLIC=1] node bridge.mjs

import { defineCapability, s } from '@appport/sdk'
import {
	startBridge,
	callApplication,
	runBridgeMain,
} from './lib/bridge-kit.mjs'

const SCOPE = 'paperless.documents.read'
const API_VERSION = '10' // Paperless-ngx AcceptHeaderVersioning
const FIELDS = [
	'id',
	'title',
	'created',
	'modified',
	'added',
	'owner',
	'correspondent',
	'document_type',
	'storage_path',
	'tags',
	'mime_type',
	'page_count',
	'archive_serial_number',
	'original_file_name',
]

const DocumentRef = {
	id: s.integer(),
	title: s.string(),
	created: s.string(),
	modified: s.nullable(s.string()),
	added: s.nullable(s.string()),
	owner: s.nullable(s.integer()),
	correspondent: s.nullable(s.integer()),
	documentType: s.nullable(s.integer()),
	storagePath: s.nullable(s.integer()),
	tags: s.array(s.integer()),
	mimeType: s.nullable(s.string()),
	pageCount: s.nullable(s.integer()),
	archiveSerialNumber: s.nullable(s.integer()),
	originalFileName: s.nullable(s.string()),
}
const doc = (d) => ({
	id: d.id,
	title: d.title ?? '',
	created: String(d.created ?? ''),
	modified: d.modified ?? null,
	added: d.added ?? null,
	owner: d.owner ?? null,
	correspondent: d.correspondent ?? null,
	documentType: d.document_type ?? null,
	storagePath: d.storage_path ?? null,
	tags: d.tags ?? [],
	mimeType: d.mime_type ?? null,
	pageCount: d.page_count ?? null,
	archiveSerialNumber: d.archive_serial_number ?? null,
	originalFileName: d.original_file_name ?? null,
})
const DocId = s.integer({ minimum: 1, maximum: 2147483647 })

export function capabilities(upstream) {
	const authority = 'urn:appport:paperless-ngx'
	const read = (purpose) => ({
		purpose,
		authority,
		approval: { required: false },
		access: [
			{ resource: 'urn:appport:paperless-ngx:documents', mode: 'reads' },
		],
	})

	const search = defineCapability({
		name: 'paperless.documents.search',
		version: 1,
		description:
			"Find documents the caller may view, by title (always current) or by full-text query (as current as Paperless-ngx's index). Returns metadata only.",
		input: s.object({
			title: s.optional(s.string({ minLength: 1, maxLength: 200 })),
			query: s.optional(s.string({ minLength: 1, maxLength: 500 })),
			pageSize: s.optional(s.integer({ minimum: 1, maximum: 100 })),
			page: s.optional(s.integer({ minimum: 1, maximum: 10000 })),
		}),
		output: s.object({
			count: s.integer(),
			documents: s.array(s.object(DocumentRef)),
		}),
		effect: 'observation',
		authorization: [SCOPE],
		authorizationContract: { required: true, scopes: [SCOPE] },
		integration: read(
			'Search documents visible to the caller (metadata only).'
		),
		handler: async ({ title, query, pageSize, page }, ctx) => {
			const body = await callApplication(ctx, upstream, {
				path: '/api/documents/',
				query: {
					title__icontains: title,
					query,
					page_size: pageSize ?? 25,
					page,
					fields: FIELDS.join(','),
				},
			})
			return {
				count: body?.count ?? 0,
				documents: (body?.results ?? []).map(doc),
			}
		},
	})

	const get = defineCapability({
		name: 'paperless.documents.get',
		version: 1,
		description:
			"Retrieve one document's metadata (no content, notes or file bytes) if Paperless-ngx lets the caller view it.",
		input: s.object({ id: DocId }),
		output: s.object(DocumentRef),
		effect: 'observation',
		authorization: [SCOPE],
		authorizationContract: { required: true, scopes: [SCOPE] },
		integration: read("Retrieve a permitted document's metadata."),
		handler: async ({ id }, ctx) =>
			doc(
				await callApplication(ctx, upstream, {
					path: `/api/documents/${id}/`,
					query: { fields: FIELDS.join(',') },
				})
			),
	})

	const metadata = defineCapability({
		name: 'paperless.documents.metadata',
		version: 1,
		description:
			'File-level details of a permitted document: checksums, sizes, MIME type and original filename. Embedded file metadata is not returned.',
		input: s.object({ id: DocId }),
		output: s.object({
			originalChecksum: s.string(),
			originalSize: s.nullable(s.integer()),
			originalMimeType: s.string(),
			originalFilename: s.string(),
			hasArchiveVersion: s.boolean(),
			archiveChecksum: s.nullable(s.string()),
			archiveSize: s.nullable(s.integer()),
		}),
		effect: 'observation',
		authorization: [SCOPE],
		authorizationContract: { required: true, scopes: [SCOPE] },
		integration: read("Read a permitted document's file-level details."),
		handler: async ({ id }, ctx) => {
			const m = await callApplication(ctx, upstream, {
				path: `/api/documents/${id}/metadata/`,
			})
			return {
				originalChecksum: m.original_checksum,
				originalSize: m.original_size ?? null,
				originalMimeType: m.original_mime_type,
				originalFilename: m.original_filename,
				hasArchiveVersion: Boolean(m.has_archive_version),
				archiveChecksum: m.archive_checksum ?? null,
				archiveSize: m.archive_size ?? null,
			}
		},
	})

	return [search, get, metadata]
}

export async function build(config) {
	const upstream = {
		baseUrl: config.upstream,
		headers: (credential) => ({
			authorization: credential,
			accept: `application/json; version=${API_VERSION}`,
		}),
	}
	return startBridge({
		application: {
			id: 'com.paperless-ngx',
			name: 'Paperless-ngx',
			version: 'appport-bridge-1',
			description:
				"Paperless-ngx document metadata, through Paperless-ngx's own REST API with the caller's own API token.",
		},
		capabilities: capabilities(upstream),
		resources: [
			{
				id: 'urn:appport:paperless-ngx:documents',
				kind: 'collection',
				owner: 'self',
				description: 'Documents managed by this Paperless-ngx instance.',
			},
		],
		scopes: [SCOPE],
		publish: config.publish,
		publishCapabilities: ['search', 'get', 'metadata'].map((op) => ({
			name: `paperless.documents.${op}`,
			version: 1,
			purpose: true,
		})),
		host: config.host,
		port: config.port,
	})
}

if (import.meta.url === `file://${process.argv[1]}`) await runBridgeMain(build)
