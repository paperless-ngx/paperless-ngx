---
name: whoosh-compat-transition
description: Use when integrating the whoosh-compat library into paperless-ngx search, replacing src/documents/search/_translate.py or _dates.py, building the search FieldRegistry, or changing user query parsing during the whoosh-to-tantivy transition
---

# whoosh-compat transition

## Overview

whoosh-compat (github.com/stumpylog/whoosh-compat; local checkout usually at `../whoosh-compat`) replaces the hand-maintained translation layer (`src/documents/search/_translate.py`, `_dates.py`): it parses user queries with a faithful fork of whoosh's real grammar into a typed AST and emits programmatic tantivy queries. Read its README and ARCHITECTURE.md before wiring anything; its DIVERGENCES.md lists intended behavior differences and is the authority on "is this difference a bug".

## Decisions already made (do not re-derive)

- **Queries are user-typed free text.** The advanced search box passes whatever the user types straight to the parser (that is how the issue #13568 queries exist). Do NOT try to infer the supported field surface from frontend code; the frontend only generates a few date filter strings, everything else is typed by users.
- **The field surface is a policy decision, not `KNOWN_FIELDS`.** Today's `KNOWN_FIELDS` accepts internal ID fields (`tag_id`, `owner_id`, `viewer_id`, other `*_id`) that are undocumented in `docs/usage.md` and were ruled not user-searchable by the maintainer: exclude them from the `FieldRegistry` (they stay as programmatic permission/filter fields in `build_permission_filter`, which never touches user query text). The registry is built from documented syntax in `docs/usage.md` plus the v2-compat aliases (`type`, `path`, `type_id`-style aliases follow their canonical field's fate). Undocumented-but-working fields (`asn`, `page_count`, `num_notes`, `original_filename`, `checksum`) need an explicit maintainer yes/no; since users type freely, silently dropping one breaks any saved view using it, so a drop must be a visible, documented decision.
- **Analyzer seam:** `FieldSpec.analyzer` binds the live registered tantivy analyzer's `.analyze` (the same Rust analyzer used at index time; language-keyed, so rebuild the registry when `SEARCH_LANGUAGE` changes, on the same trigger as `register_tokenizers`). `pattern_normalizer` is `_tokenizer.ascii_fold`: character-level lowercase+fold only, NEVER stemming.
- **Diagnostics before emit:** `whoosh_compat.parse()` never raises on bad input. Check `ParseResult.diagnostics` and map to `SearchQueryError`/`InvalidDateQuery` (HTTP 400) BEFORE calling `emit()`; also catch the emitter's `UnsupportedQueryError` into a 400. Never carry forward the legacy raw-string fallback (`except Exception: query_str = raw_query`) into the new path; it masks integration bugs.
- **`notes` and `custom_fields` are JSON fields** with fixed subpaths (`notes.user`/`notes.note`, `custom_fields.name`/`custom_fields.value`); the registry stays a static, language-keyed singleton, never per-request.

## Mandatory before deleting old code

- Date-grammar parity audit, line by line: every keyword, relative unit, and abbreviation `_dates.py` and `_translate.py` accept today (including the whoosh-era abbreviations kept for old saved views) must have an accepted form in whoosh-compat's dateparse grammar. Silent keyword loss is the saved-view breakage class behind issue #13568.
- Acceptance corpus compared by matched-document-ID sets, not query strings: the #13568 queries verbatim, real saved-view strings, every date keyword, field aliases, comma lists, date and numeric ranges, wildcards with bracket classes, boosts, JSON subpaths.

## Tests: what goes, what comes

Removed with their modules (do not port their string-level assertions):

- `src/documents/tests/search/test_translate.py`: its subject is deleted; string-translation unit cases are whoosh-compat's own responsibility now. Cases that encode real user-visible behavior get reincarnated as result-level acceptance cases, not string assertions.
- Date-keyword unit tests tied to `_dates.py` internals: same treatment.
- `test_query.py` cases asserting `parse_user_query` internals or intermediate query strings: rewritten against the new pipeline, asserting on matched results.

Kept: `test_migration_fulltext_query_field_prefixes.py` (data migration, orthogonal), `test_schema.py`, `test_tokenizer.py`, permission-filter and simple-search tests.

Added:

- A result-level acceptance module (paperless's analogue of whoosh-compat's `test_acceptance_e2e.py`): the corpus above against a real index built from `build_schema()`, asserting document-ID sets. Use `pytest.param(..., id="...")` for every case.
- Registry unit tests: internal `*_id` names rejected, aliases resolve to canonical fields, JSON subpaths match `docs/usage.md`, construction deterministic per language.
- One `Multitoken` case nested inside a top-level `OR` (whoosh-compat DIVERGENCES entry on Multitoken.DEFAULT) to prove it does not matter for paperless's data.
- If acceptance work surfaces a new whoosh-compat divergence, that is a whoosh-compat-repo change (its `differential-triage` skill applies), not a silent paperless workaround.

## Coordination

- whoosh-compat is pre-1.0: pin an exact version or git SHA; upgrades are deliberate, reviewed changes.
- JSON subpath emission depends on the installed tantivy-py version (fallback until quickwit-oss/tantivy-py#716 ships). The whoosh-compat repo has a `carve-out-retirement` skill; coordinate tantivy pin bumps with it, in a separate PR from the parser migration.
- Rollout: settings flag defaulting to the legacy path plus shadow-compare logging (log when old and new paths return different ID sets; sample if cost matters) for one release; delete `_translate.py`/`_dates.py` only after the flag defaults to the new path with no material reports.

## Common mistakes

- Inferring the field surface from frontend code (users type queries directly).
- Copying `KNOWN_FIELDS` into the registry wholesale (resurfaces internal fields).
- Wiring stemming into `pattern_normalizer`.
- Calling `emit()` unconditionally, or porting the legacy raw-string fallback.
- Deleting `_dates.py` without the parity audit.
- Porting `test_translate.py`'s string assertions instead of writing result-level tests.
