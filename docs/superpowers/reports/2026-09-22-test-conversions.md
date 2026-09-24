# Pytest conversion plan: what to convert, in what order

Survey date: 2026-09-22, branch `fix-outbound-connect-guard`. Line numbers are as of that tree.
Companion report: `2026-09-22-test-bugs.md` (fix those first; several are touched below).

## Progress

One file per branch, each branched fresh off `dev`. Bug fixes for the companion report are
tracked separately in PR #14244 (`fix-test-suite-bugs`, open as of this writing) — Phase 1
items touching the same files should wait for that to merge, or rebase after.

All branches below have been rebased onto `origin/dev` (post-#14244 merge, `091ddf7c4`) and
re-verified on the VM; commit hashes reflect the post-rebase state.

| #    | File                                                                                                                                                                        | Branch                                     | Commit(s)                | Status                                                          |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------ | --------------------------------------------------------------- |
| 1    | `paperless/tests/test_signals.py`                                                                                                                                           | `test-convert-signals`                     | `929355291`              | done                                                            |
| 2    | `paperless/tests/parsers/test_tesseract_custom_settings.py`                                                                                                                 | `test-convert-tesseract-custom-settings`   | `306adaaaf`              | done                                                            |
| 5    | `documents/tests/test_api_app_config.py`                                                                                                                                    | `test-convert-api-app-config`              | `f5e138d90`, `4044fe875` | done                                                            |
| 11   | `paperless/tests/settings/test_settings.py`                                                                                                                                 | `test-convert-settings`                    | `7b7e889f9`              | done                                                            |
| 9    | `documents/tests/test_api_schema.py`                                                                                                                                        | `test-convert-api-schema`                  | `1e534d9f3`              | done                                                            |
| 7    | `paperless_ai/tests/test_matching.py`                                                                                                                                       | `test-convert-ai-matching`                 | `05690997f`              | done                                                            |
| 8    | `documents/tests/test_api_chat.py`                                                                                                                                          | `test-convert-api-chat`                    | `2744361f3`              | done                                                            |
| 16   | `test_api_documents.py:3361-3412` regex matching → `test_api_object_regex_matching.py`                                                                                      | `test-convert-api-documents-slices`        | `cc669257e`              | done (branch reused for further `test_api_documents.py` slices) |
| 17   | `test_api_documents.py:3309-3360` logs → `test_api_logs.py`                                                                                                                 | `test-convert-api-documents-slices`        | `624118b6a`              | done                                                            |
| 18   | `test_api_documents.py:4440-4698` `TestDocumentApiTagColors` → `test_api_tag_colors.py`, `TestDocumentApiCustomFieldsSorting` → `test_api_document_custom_field_sorting.py` | `test-convert-api-documents-slices`        | `b607174b0`, `871524377` | done                                                            |
| 6    | `documents/tests/test_merge_documents_as_versions.py`                                                                                                                       | `test-convert-merge-documents-as-versions` | `ab2af7ba2`              | done                                                            |
| 19   | `test_management_exporter.py:1060-1275` CLI argument validation → `TestExporterCliValidation`                                                                               | `test-convert-management-exporter`         | `ddcc3595d`              | done                                                            |
| 10   | `documents/tests/test_document_model.py`                                                                                                                                    | `test-convert-document-model`              | `ae20342f8`              | done                                                            |
| 12   | `documents/tests/test_admin.py`                                                                                                                                             | `test-convert-admin`                       | `3d2813dd8`              | done                                                            |
| 20   | `test_api_permissions.py:28-91, 1488-1562, 1665-1693` → `TestAuthRequired`, `TestBulkEditSetPermissionsValidation`, `TestFullPermissionsFlag`                               | `test-convert-api-permissions`             | `8defe169d`              | done                                                            |
| 3    | `documents/tests/test_management_superuser.py`                                                                                                                              | `test-convert-management-superuser`        | `0272366ea`              | done                                                            |
| 4    | `documents/tests/test_management_fuzzy.py`                                                                                                                                  | `test-convert-management-fuzzy`            | `a976bb504`              | done                                                            |
| P2-1 | `paperless_testing/factories.py`: `CustomFieldFactory`, `CustomFieldInstanceFactory`, `WorkflowTriggerFactory`, `WorkflowActionFactory`, `WorkflowFactory`                  | `test-add-custom-field-workflow-factories` | `79a802293`              | done                                                            |
| 29   | `documents/tests/test_api_filter_by_custom_fields.py`, whole file                                                                                                           | `test-add-custom-field-workflow-factories` | `32dd7df43`              | done                                                            |
| 30   | `test_workflows.py` DOCUMENT_ADDED filters → `TestDocumentAddedTriggerFilters`                                                                                              | `test-add-custom-field-workflow-factories` | `8c2615e71`              | done                                                            |

## Where things stand

- 48 test files still contain `TestCase` / `APITestCase` classes (about 36k lines); 114 test
  files are already pytest-style.
- `DirectoriesMixin` is no longer a blocker: `paperless_testing/dirs.py:135` is an autouse
  bridge to `paperless_dirs` and works on plain classes too.
- The real blocker is the `TestCase` base itself. `@pytest.mark.parametrize` and `mocker`
  don't work on its methods, so every "parametrize this cluster" item means moving that
  cluster into a plain `@pytest.mark.django_db` class.
- pytest 9.1 reports `self.subTest` failures natively. For files not being converted yet,
  adding `subTest` to a bare loop is a real fix, not a stopgap.

## Conventions for the conversions

- **Build users with `UserFactory`.** Use plain `UserFactory()` plus `grant_global` /
  `grant_object` for permissioned users, and `UserFactory(superuser=True)` where the test
  cares about the user. `admin_client` (and so `admin_user`) is fine where a test just needs
  an authenticated superuser; the autouse MD5 hasher makes it cheap. Use it where it fits,
  not by default.
- **Staff and superuser are different gates.** `admin_user` (pytest-django,
  `create_superuser`) and `UserFactory(superuser=True)` set both flags, so tests using them
  can't tell which flag a code path checks. Paperless gates several things on `is_staff`
  alone: `PaperlessAdminPermissions`, the task queryset (`documents/views.py:4518`) and
  duplicate visibility (`documents/serialisers.py:2778`). Tests for those should use
  `UserFactory(staff=True)` and say which flag they mean.
- Hand-rolled `Model.objects.create` becomes the factory where one exists. Keep explicit
  `pk=`, `checksum=`, `title=` or `content=` where the test asserts on them:
  `DocumentFactory` fills title and content with Faker text, which matters for the
  content-matching workflow tests.
- `@override_settings` becomes the `settings` fixture. A class-level `@override_settings`
  can't decorate a plain pytest class, so it becomes an autouse fixture.
- `assertLogs` becomes `caplog`; `mock.patch` becomes `mocker`; `patch.dict(os.environ)`
  becomes `monkeypatch`.
- Drop the redundant setup the shared layer already does: `cache.clear()` (autouse
  `_clear_django_caches`), `reset_backend()` in search setUp/tearDown (`paperless_dirs` /
  `_search_index`), and `force_login` right after `force_authenticate`.
- `strict_parametrization_ids` is on, so every `pytest.param` needs an `id=`.

---

## Phase 1: mechanical wins, no new infra (S effort each)

Batch 2 to 4 files per PR. Start with `test_signals.py` as the reference conversion.

### Whole-file (or last-class) conversions

| #   | File                                                                                                                                                                                                                         | What collapses                                                                                                                                                                                                          | Value    |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1   | `paperless/tests/test_signals.py`                                                                                                                                                                                            | Failed-login 4→1; group sync 5→1; role sync 9 plus the 3 inline cases in `test_sync_both_groups` → 1. About 700 lines to about 300. No mixins, no setUp state. Add `GroupFactory` here (8 hand-rolled `Group` creates). | high     |
| 2   | `paperless/tests/parsers/test_tesseract_custom_settings.py`                                                                                                                                                                  | 9 near-identical "settings plus DB config → parser params" tests become 1 or 2. The existing tesseract fixtures mock out the DB config, so they don't fit; use an `app_config` DB fixture.                              | high     |
| 3   | `documents/tests/test_management_superuser.py`                                                                                                                                                                               | `test_no_user` and `test_no_password` are duplicates; create/email/username 3→1; "exists" pair 2→1. DirectoriesMixin not needed. Fixes the `patch.dict` env leak.                                                       | high     |
| 4   | `documents/tests/test_management_fuzzy.py`                                                                                                                                                                                   | Ratio limits 2→1; no-match/matches/3-matches/empty 4→1. No mixins. Use `DocumentFactory` (14 hand-rolled creates).                                                                                                      | high     |
| 5   | `documents/tests/test_api_app_config.py`                                                                                                                                                                                     | 12 SVG-rejection tests → 1; 2 SVG accepts → 1; 5 internal-endpoint tests → 1; subTest at L226 → parametrize. No mocks, trivial setUp.                                                                                   | high     |
| 6   | `documents/tests/test_merge_documents_as_versions.py`                                                                                                                                                                        | The same 3 `@mock.patch` on 7 methods become one autouse `mocker` fixture; about 6 serializer rejection tests → 1 or 2; permission pair → 1.                                                                            | med      |
| 7   | `paperless_ai/tests/test_matching.py`                                                                                                                                                                                        | Last `TestCase` class; `test_match_*_by_name` 4→1. The file already imports all four factories.                                                                                                                         | med-high |
| 8   | `documents/tests/test_api_chat.py`                                                                                                                                                                                           | Last `APITestCase` class; reuse the existing `mocked_stream_chat` fixture; oversized/missing question 2→1.                                                                                                              | med-high |
| 9   | `documents/tests/test_api_schema.py`                                                                                                                                                                                         | Last `APITestCase` class; reuse the session-scoped `api_schema` fixture (faster); set-subset asserts in place of loops.                                                                                                 | med-high |
| 10  | `documents/tests/test_document_model.py`                                                                                                                                                                                     | Manual tempdir plus `override_settings.enable()` becomes `paperless_dirs`; 4 `test_file_name*` → 1.                                                                                                                     | med-high |
| 11  | `paperless/tests/settings/test_settings.py`                                                                                                                                                                                  | Last two `unittest.TestCase` classes; the 63-case loop at L28 becomes parametrize.                                                                                                                                      | med      |
| 12  | `documents/tests/test_admin.py`                                                                                                                                                                                              | Last class; redundant `reset_backend` in setUp/tearDown; `grant_global` at L193.                                                                                                                                        | med      |
| 13  | `documents/tests/test_tag_hierarchy.py`                                                                                                                                                                                      | Already plain `assert`; two 2→1 pairs; `TagFactory` for 25 creates.                                                                                                                                                     | med      |
| 14  | `documents/tests/test_management_retagger.py`                                                                                                                                                                                | Replace `DirectoriesMixin` on 6 classes with `pytestmark = pytest.mark.usefixtures("paperless_dirs")`. Five minutes.                                                                                                    | low      |
| 15  | `test_api_uisettings.py`, `settings/test_remote_user.py`, `test_management.py`, `test_version_conditionals.py`, `test_config_precedence.py`, `test_compression_middleware.py`, `test_auth_middleware.py`, `test_api_auth.py` | Small files; mostly base-class removal. Batch them together.                                                                                                                                                            | low-med  |

### Slices of big files

Carve these out into new plain classes, or new files where they don't belong in the host file.

| #   | Slice                                                                                                                                                                                                                         | Collapse                                                                                                                                                                                                | Value    |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 16  | `test_api_documents.py:3361-3412` regex matching → new file (it tests the objects endpoints)                                                                                                                                  | 4 tests × 3 endpoints → 1 test, 12 params                                                                                                                                                               | high     |
| 17  | `test_api_documents.py:3309-3360` logs → `test_api_logs.py`                                                                                                                                                                   | 7 tests → about 3                                                                                                                                                                                       | med-high |
| 18  | `test_api_documents.py:4440-4698` `TestDocumentApiTagColors`, `TestDocumentApiCustomFieldsSorting`                                                                                                                            | color validation → params; the unguarded `data_type` loop → about 8 params                                                                                                                              | med-high |
| 19  | `test_management_exporter.py:1060-1275` CLI argument validation → lightweight class (`tmp_path` only)                                                                                                                         | 4 tests (3 are subTest loops) → 1 with 7 ids, plus the zstd pair. They stop paying for the heavy setUp. Also turn `test_exporter` / `_with_filename_format` (a test calling a test) into a parametrize. | high     |
| 20  | `test_api_search.py:2103-2175` `search_by_*`                                                                                                                                                                                  | 4 → 1, on `_search_index`                                                                                                                                                                               | med      |
| 21  | `test_api_document_versions.py:886-1024` two pure ORM filter classes                                                                                                                                                          | direct conversion; one 2→1 pair                                                                                                                                                                         | med      |
| 22  | `test_api_custom_fields.py:705-993` value validation plus the L28 create loop                                                                                                                                                 | 6 → 1 (about 10 params); create loop → params                                                                                                                                                           | med-high |
| 23  | `test_api_permissions.py:28-91, 1488-1562, 1665-1693`                                                                                                                                                                         | 14-URL auth-required list → params; set_permissions rejection 3→1; full-permissions flag → params                                                                                                       | med      |
| 24  | `test_api_objects.py:540-606` storage-path render and hidden-field loops                                                                                                                                                      | 1 test → 2 tests, 5 params (security-relevant)                                                                                                                                                          | med      |
| 25  | `test_workflows.py:4427-4490` password removal pair                                                                                                                                                                           | 2 → 1; fixes bug 4                                                                                                                                                                                      | med      |
| 26  | `test_tasks.py`                                                                                                                                                                                                               | auto-match trio 3→1; RemoteOCR trio 3→1; last `TestCase` classes                                                                                                                                        | med      |
| 27  | `paperless_mail/tests/test_mail.py` small classes: `TestPostConsumeAction` (bug 2), `TestManagementCommand`, `TestTasks`, `TestGetMailboxHostPinning`, `TestMailAccountProcess` (its MailMocker is unused), `TestMailRuleAPI` | mostly mechanical; use `MailAccountFactory` / `MailRuleFactory`                                                                                                                                         | med      |
| 28  | `test_consumer.py` `TestMetadataOverrides`, `TestBarcodeApplyDetectedASN`                                                                                                                                                     | plain `TestCase`, no mixins                                                                                                                                                                             | low-med  |

## Phase 1b: `subTest` fixes in files not being converted soon

One PR. Each fix is a few lines and makes failures report which case broke.

- `test_api_documents.py:4622` custom-field sorting (8 types; skip if item 18 lands first)
- `test_api_documents.py:2415` upload custom-field errors (5 payloads)
- `test_views.py:59` `test_index` (7 languages; cookie state carries between iterations)
- `test_barcodes.py:208` (3 files)
- `test_api_workflows.py:1211, 1335` (webhook URLs, password payloads)
- `test_api_bulk_edit.py:2113-2197`: fold about 7 inline POST+assert blocks into the
  `(operation, expected)` subTest table that follows them
- `test_api_bulk_edit.py:1102` `test_api_selection_data_empty`
- `test_mail.py:1826` label fix (bug 3)
- Already pytest-style, so parametrize instead: `paperless/tests/parsers/test_mail_parser.py:826`
  (a nested helper called 4 times), `paperless/tests/test_celery.py:17`

Every other existing `subTest` use in the suite was reviewed and is fine.

Lower-value DRY merges in files that are already pytest-style (they fail independently
today, so there's no reporting gain): `test_parser_utils.py:23-46`,
`test_migration_replace_skip_archive_file.py:48-78`, the paired tests in
`test_tesseract_parser.py`, `test_text_parser.py`, `test_ocr_config.py`,
`search/test_backend.py`, `search/test_query.py`, and the management command tests. Pick
these up opportunistically.

## Phase 2: shared infra PR(s)

This unblocks the high-value Phase 3 work. Four surveys converged on the same list, ordered
by how much each item unblocks:

1. **Factories** in `paperless_testing/factories.py`:
   - `GroupFactory`, if not already added in item 1 (about 25 hand-rolled creates suite-wide)
   - `CustomFieldFactory` and `CustomFieldInstanceFactory`, used by custom_fields,
     filter_by_custom_fields, bulk_edit, documents sorting and the exporter
   - `WorkflowFactory`, `WorkflowTriggerFactory` and `WorkflowActionFactory`, with
     post-generation `triggers` / `actions` hooks. `test_workflows.py` alone hand-rolls
     about 100 of each, plus about 90 `triggers.add` / `actions.add` sequences.
   - Optional: `ShareLinkFactory`, `ShareLinkBundleFactory`, `NoteFactory`, `SavedViewFactory`
2. **`consume_task_mock` fixture** to replace `ConsumeTaskMixin` (`documents/tests/utils.py:126`):
   a `mocker.patch` on the consume task, with the call-args helpers as free functions. It
   unblocks about 20 upload tests in `test_api_documents.py` (L1850-2503) and
   `TestBarcodeNewConsume`.
3. **`samples_dir` and `barcode_samples_dir` fixtures.** `document_samples_dir` points at
   `samples/documents/`, not the `samples/` root that `SampleDirMixin.SAMPLE_DIR` uses.
   Needed by email, bulk_download, thumbnails, barcodes and exporter.
4. **`progress_manager` fixture** for the `documents.tasks.ProgressManager` →
   `DummyProgressManager` patch: 14 times in workflows, plus barcodes, consumer and
   double_sided.
5. **Mail mock support module.** Move `BogusMailBox`, `BogusClient`, `MessageBuilder`,
   `fake_magic_from_buffer` and `reset_bogus_mailbox` out of `test_mail.py` (L53-440).
   `test_api.py` and `test_mail_nfc.py` currently import them from a test file. Add
   `bogus_mailbox`, `message_builder` and `mail_mocker` fixtures to
   `paperless_mail/tests/conftest.py`, and promote the local ones in `test_mail_nfc.py`.
6. **`make_client` factory fixture** returning an authenticated `APIClient` (v10 header) for
   any given user. It covers:
   - about 115 mid-test `self.client.force_authenticate(...)` user switches across the API
     tests
   - the "non-superuser with `grant_all_global`" client built by hand in `test_api_trash.py`,
     in all three classes of `paperless_mail/tests/test_api.py`, and locally as
     `viewer_client` in `test_api_chat.py`
7. **Smaller items:**
   - an `app_config` fixture (if not already added in item 2)
   - `assert_file` / `assert_file_count` helpers to replace `FileSystemAssertsMixin`
   - a `consumer_factory` fixture to replace `GetConsumerMixin`
   - a `barcode_reader` fixture to replace `GetReaderPluginMixin` (`get_reader` is also
     duplicated at `test_barcodes.py:658` and `:817`)
   - a "documents with real files on disk" helper on `paperless_dirs`, for email,
     bulk_download, thumbnails and document_model

Items 1-3 could be one PR; 4-6 another.

## Phase 3: high value once Phase 2 lands (M effort, one file per PR)

| #   | Target                                                                                                                                                                                     | Collapse                                                                                                                    | Needs                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 29  | `test_api_filter_by_custom_fields.py`, whole file                                                                                                                                          | About 25 predicate tests → 1; 10 invalid-query tests → 1. About 35 tests to about 3, the best ratio in the suite.           | CustomField factory (or inline creates); setUp → fixture |
| 30  | `test_workflows.py` DOCUMENT_ADDED filters, L813-1895, as `TestDocumentAddedTriggerFilters`                                                                                                | 11 "did not match" tests → 1 (about 330 lines)                                                                              | Workflow factories                                       |
| 31  | `test_api_bulk_edit.py` validation class                                                                                                                                                   | 11 invalid-parameter tests (L916-1094) → 1; 10 subTest loops → parametrize (the 2×8 legacy-method one at L1985 is the best) | one setUp fixture (local)                                |
| 32  | `test_classifier.py` `TestClassifier`                                                                                                                                                      | predict trio and `_manydocs` trio 6→2; corrupt-file loaders 4→1; `load_classifier_raise_exception` 4 blocks → params        | setUp → fixture                                          |
| 33  | `test_barcodes.py` `TestBarcode` first                                                                                                                                                     | "scan → separation pages" repeated about 14 times → 1; about 30 tests to about 8 across the file                            | samples fixtures, `barcode_reader`, `consume_task_mock`  |
| 34  | `test_api_status.py`                                                                                                                                                                       | classifier/sanity 6→1; celery, redis and AI groups; manual patchers → autouse `mocker`                                      | none                                                     |
| 35  | `test_api_email.py`                                                                                                                                                                        | about 8 "payload → 400" cases → 1; `mailoutbox`                                                                             | `samples_dir`, file-backed docs                          |
| 36  | `test_file_handling.py` `TestFilenameGeneration` first, then `TestFileHandlingWithArchive`                                                                                                 | about 25 tests to about 10 across the file; 59 `@override_settings`                                                         | none                                                     |
| 37  | `test_share_link_bundles.py`                                                                                                                                                               | about 9 tests collapse; FilterSet and Model classes first                                                                   | bug 1 fixed; optional factories                          |
| 38  | `test_views.py`                                                                                                                                                                            | AI error quartet 4→1; chat permission pair 2→1; `grant_global` in place of `codename__contains` grants                      | none                                                     |
| 39  | `test_api_search.py:431-753` relative-date / timezone                                                                                                                                      | 6 → 1                                                                                                                       | care with `timezone.now()` and `settings.TIME_ZONE`      |
| 40  | `test_api_documents.py` upload cluster, L2055-2213                                                                                                                                         | 9 → 2                                                                                                                       | `consume_task_mock`                                      |
| 41  | `paperless_mail/tests/test_api.py`                                                                                                                                                         | subTest → params; test-endpoint 2→1 and 3→1; merge the overlapping `TestMailAccountTestView` from `test_mail.py`            | mail fixtures, `make_client`                             |
| 42  | `test_api_bulk_download.py`, `test_api_trash.py`, `test_api_profile.py`, `test_management_thumbnails.py`, `test_api_workflows.py`, `test_api_objects.py`, `test_api_permissions.py` (rest) | moderate dedup each                                                                                                         | Phase 0 and Phase 2 items                                |

## Phase 4: large; do class by class or defer (L)

- The rest of `test_workflows.py`: split the 6k-line `TestWorkflows` into about 9 topic
  classes (consumption, document added, updated, scheduled, email, webhook, password,
  trash). It has 43 `assertLogs`, 51 `mock.patch` and 17 `override_settings`.
- `test_mail.py` `TestMail`: 2 subTest loops → params (9 and 8), 2 groups of mail-action
  tests 4→1 each. Several tests carry `flaky(reruns=4)`.
- `test_consumer.py`: about 17 tests to about 7, once `consumer_factory` exists.
- `test_bulk_edit.py`: 99 stacked `@mock.patch`, modest dedup. `TestBulkEditReprocess` and
  `TestBulkEdit` can go first.
- The rest of `test_api_documents.py` and the `TestExportImport` core of
  `test_management_exporter.py`. `test_import_db_transaction_failed` may need
  `django_db(transaction=True)`.

## Suggested PR order

1. Bug fixes (companion report); bug 1 is the important one.
2. Phase 1 in batches: `test_signals.py` first, then items 2-5, then the rest.
3. Phase 1b: one `subTest` PR.
4. Phase 2 infra, in one or two PRs.
5. Phase 3, one file per PR, in table order.
6. Phase 4 opportunistically.
