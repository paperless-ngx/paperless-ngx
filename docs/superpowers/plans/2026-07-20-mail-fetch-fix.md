# Mail Fetch Re-download Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `paperless_mail` from re-downloading full IMAP message bodies for mail it has already handled, and make sure attachment-less mail under attachments-only rules is recorded so it stops matching the search forever.

**Architecture:** In `_handle_mail_rule`, replace the single "fetch every matching message's full body" call with a cheap `UID SEARCH` first, subtract UIDs already in `ProcessedMail`, and fetch bodies only for the remainder (batched). Separately, extract the existing "record `PROCESSED_WO_CONSUMPTION`" block into a shared helper and call it from the no-attachments-under-attachments-only-scope early return in `_handle_message`, which currently skips it entirely.

**Tech Stack:** Django (pytest-django), `imap_tools` (`MailBox.uids()`, `AND` query builder), existing `ProcessedMail` model — no new dependencies, no migrations.

## Global Constraints

- No new required settings and no DB migrations for existing installs (spec: "No new required settings/migrations for existing installs").
- Batch size for body fetches is a hardcoded module constant (`MAIL_FETCH_BATCH_SIZE = 500`), not user-configurable.
- No mailbox action (mark-read/flag/tag/move/delete) is applied for the no-attachment/no-consumption case — only a `ProcessedMail` row is written, matching the existing precedent for other no-consumption outcomes.
- Every path that currently produces a document or applies a mail action must behave exactly as before (no change to `_process_attachments`'/`_process_eml`'s consuming behavior, action application, or the existing per-message `already_processed` dedup check, which stays in place as a safety net).
- Follow the existing per-message `uid_validity` matching semantics exactly: when `self._current_uid_validity is not None`, only match `ProcessedMail` rows with the same `uid_validity` or `uid_validity IS NULL`; when it is `None` (server didn't report UIDVALIDITY), fall back to matching on `(rule, uid, folder)` alone, ignoring `uid_validity`. (This exact conditional already exists at `mail.py:722-726` for the per-message check — the new UID-diff query must replicate it or several existing uidvalidity tests will break.)

---

### Task 1: Add UID search support to the `BogusMailBox` test double

**Files:**

- Modify: `src/paperless_mail/tests/test_mail.py:137-171` (`BogusMailBox.fetch`)
- Test: `src/paperless_mail/tests/test_mail.py` (new test in `class TestMail`)

**Interfaces:**

- Produces: `BogusMailBox.uids(self, criteria, charset="") -> list[str]`, filtering with the same rules as `fetch()`, returning only UIDs (no message bodies). `BogusMailBox.fetch()` gains support for a `UID <comma-list>` criteria token (used by real code's `AND(uid=[...])` queries).
- Consumes: nothing new — this is test infrastructure only, no production code changes in this task.

- [ ] **Step 1: Write the failing test**

Add to `class TestMail` in `src/paperless_mail/tests/test_mail.py` (near the other `BogusMailBox`-adjacent tests, e.g. after `test_handle_message`):

```python
    def test_bogus_mailbox_uids_and_uid_criteria(self) -> None:
        mailbox = self.mailMocker.bogus_mailbox
        all_messages = list(mailbox.messages)

        # uids() returns the UIDs of unseen messages, no bodies needed to call it
        unseen_uids = mailbox.uids("(UNSEEN)")
        self.assertEqual(
            set(unseen_uids),
            {m.uid for m in all_messages if not m.seen},
        )

        # fetch() with an explicit UID criteria returns only the matching messages
        target_uid = all_messages[0].uid
        from imap_tools import AND

        fetched = mailbox.fetch(AND(uid=[target_uid]), mark_seen=False)
        self.assertEqual([m.uid for m in fetched], [target_uid])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_bogus_mailbox_uids_and_uid_criteria -v`
Expected: FAIL with `AttributeError: 'BogusMailBox' object has no attribute 'uids'` (and/or the UID-criteria fetch returning all 3 default messages instead of 1, since `fetch()` doesn't understand a `UID` token yet).

- [ ] **Step 3: Implement `uids()` and `UID` criteria support**

Replace `src/paperless_mail/tests/test_mail.py:137-171`:

```python
    def fetch(self, criteria, mark_seen, charset="", *, bulk=True):
        return self._filter_messages(criteria)

    def uids(self, criteria, charset="") -> list[str]:
        return [m.uid for m in self._filter_messages(criteria)]

    def _filter_messages(self, criteria):
        msg = self.messages

        criteria = str(criteria).strip("()").split(" ")

        if "UNSEEN" in criteria:
            msg = filter(lambda m: not m.seen, msg)

        if "SUBJECT" in criteria:
            subject = criteria[criteria.index("SUBJECT") + 1].strip('"')
            msg = filter(lambda m: subject in m.subject, msg)

        if "BODY" in criteria:
            body = criteria[criteria.index("BODY") + 1].strip('"')
            msg = filter(lambda m: body in m.text, msg)

        if "FROM" in criteria:
            from_ = criteria[criteria.index("FROM") + 1].strip('"')
            msg = filter(lambda m: from_ in m.from_, msg)

        if "TO" in criteria:
            to_ = criteria[criteria.index("TO") + 1].strip('"')
            msg = filter(lambda m: any(to_ in to_addr for to_addr in m.to), msg)

        if "UNFLAGGED" in criteria:
            msg = filter(lambda m: not m.flagged, msg)

        if "UNKEYWORD" in criteria:
            tag = criteria[criteria.index("UNKEYWORD") + 1].strip("'")
            msg = filter(lambda m: tag not in m.flags, msg)

        if "(X-GM-LABELS" in criteria:  # ['NOT', '(X-GM-LABELS', '"processed"']
            msg = filter(lambda m: "processed" not in m.flags, msg)

        if "UID" in criteria:
            uid_list = criteria[criteria.index("UID") + 1].split(",")
            msg = filter(lambda m: m.uid in uid_list, msg)

        return list(msg)
```

This is a pure refactor of the existing filtering logic into `_filter_messages`, reused by both `fetch()` (unchanged behavior) and the new `uids()`, plus one new `if "UID" in criteria` branch.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_bogus_mailbox_uids_and_uid_criteria -v`
Expected: PASS

- [ ] **Step 5: Run the full existing `test_mail.py` suite to confirm the refactor didn't change `fetch()` behavior**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py -v`
Expected: all tests PASS (same pass count as before this task)

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mail/tests/test_mail.py
git commit -m "test: add BogusMailBox.uids() and UID criteria support"
```

---

### Task 2: Record `ProcessedMail` for attachment-less mail under attachments-only rules

**Files:**

- Modify: `src/paperless_mail/mail.py:749-793` (`_handle_message`)
- Modify: `src/paperless_mail/mail.py:952-979` (`_process_attachments`, tail)
- Test: `src/paperless_mail/tests/test_mail.py:540-548` (`test_handle_empty_message`, rewritten)

**Interfaces:**

- Produces: `MailAccountHandler._record_processed_without_consumption(self, message: MailMessage, rule: MailRule) -> None` — idempotently writes a `ProcessedMail(status="PROCESSED_WO_CONSUMPTION")` row for `(rule, message.uid, rule.folder)` if one doesn't already exist for the current `self._current_uid_validity`. No mailbox action is applied.
- Consumes: `self._current_uid_validity` (already set by `_handle_mail_rule` before `_handle_message` is called; `None` when called directly, e.g. in unit tests).

- [ ] **Step 1: Write the failing test**

Replace `src/paperless_mail/tests/test_mail.py:540-548` (`test_handle_empty_message`):

```python
    def test_handle_empty_message(self) -> None:
        message = self.mailMocker.messageBuilder.create_message(
            subject="No attachments here",
            attachments=[],
        )

        account = MailAccount.objects.create()
        rule = MailRule.objects.create(
            account=account,
            consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        )

        result = self.mail_account_handler._handle_message(message, rule)

        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()
        self.assertEqual(result, 0)

        processed = ProcessedMail.objects.get(
            rule=rule,
            uid=message.uid,
            folder=rule.folder,
        )
        self.assertEqual(processed.status, "PROCESSED_WO_CONSUMPTION")

        # Calling it again must not create a second row
        self.mail_account_handler._handle_message(message, rule)
        self.assertEqual(
            ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
            ).count(),
            1,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_handle_empty_message -v`
Expected: FAIL — `ProcessedMail.DoesNotExist` (no row is created by the current early return).

- [ ] **Step 3: Add the shared helper and call it from both places**

Insert a new method right after `_handle_message` ends, i.e. after `src/paperless_mail/mail.py:793` (`return processed_elements`), before `def filename_inclusion_matches`:

```python
    def _record_processed_without_consumption(
        self,
        message: MailMessage,
        rule: MailRule,
    ) -> None:
        if not ProcessedMail.objects.filter(
            rule=rule,
            uid=message.uid,
            folder=rule.folder,
            uid_validity=self._current_uid_validity,
        ).exists():
            ProcessedMail.objects.create(
                rule=rule,
                folder=rule.folder,
                uid=message.uid,
                uid_validity=self._current_uid_validity,
                subject=message.subject,
                received=make_aware(message.date)
                if is_naive(message.date)
                else message.date,
                status="PROCESSED_WO_CONSUMPTION",
            )
```

Then modify `_handle_message`'s early return at `src/paperless_mail/mail.py:756-760`:

```python
        # Skip Message handling when only attachments are to be processed but
        # message doesn't have any.
        if (
            not message.attachments
            and rule.consumption_scope == MailRule.ConsumptionScope.ATTACHMENTS_ONLY
        ):
            return processed_elements
```

becomes:

```python
        # Skip Message handling when only attachments are to be processed but
        # message doesn't have any.
        if (
            not message.attachments
            and rule.consumption_scope == MailRule.ConsumptionScope.ATTACHMENTS_ONLY
        ):
            self._record_processed_without_consumption(message, rule)
            return processed_elements
```

Then replace the tail of `_process_attachments` at `src/paperless_mail/mail.py:952-979`:

```python
        if len(consume_tasks) > 0:
            queue_consumption_tasks(
                consume_tasks=consume_tasks,
                rule=rule,
                message=message,
                uid_validity=self._current_uid_validity,
            )
        else:
            # No files to consume, just mark as processed if it wasn't by .eml processing
            if not ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
                uid_validity=self._current_uid_validity,
            ).exists():
                ProcessedMail.objects.create(
                    rule=rule,
                    folder=rule.folder,
                    uid=message.uid,
                    uid_validity=self._current_uid_validity,
                    subject=message.subject,
                    received=make_aware(message.date)
                    if is_naive(message.date)
                    else message.date,
                    status="PROCESSED_WO_CONSUMPTION",
                )

        return processed_attachments
```

with:

```python
        if len(consume_tasks) > 0:
            queue_consumption_tasks(
                consume_tasks=consume_tasks,
                rule=rule,
                message=message,
                uid_validity=self._current_uid_validity,
            )
        else:
            # No files to consume, just mark as processed if it wasn't by .eml processing
            self._record_processed_without_consumption(message, rule)

        return processed_attachments
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_handle_empty_message -v`
Expected: PASS

- [ ] **Step 5: Run the full `test_mail.py` suite (regression check for the `_process_attachments` refactor)**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
git commit -m "fix: record ProcessedMail for attachment-less mail under attachments-only rules"
```

---

### Task 3: Diff UIDs against `ProcessedMail` before fetching message bodies

**Files:**

- Modify: `src/paperless_mail/mail.py:641-693` (`_handle_mail_rule`, the fetch section)
- Test: `src/paperless_mail/tests/test_mail.py` (new test in `class TestMail`)

**Interfaces:**

- Consumes: `MailAccountHandler._record_processed_without_consumption` (Task 2), `ProcessedMail` model, `imap_tools.AND`, `M.uids()` (Task 1's `BogusMailBox.uids()` in tests; `imap_tools.MailBox.uids()` in production).
- Produces: no new public interface — `_handle_mail_rule`'s external behavior (return value, exceptions raised) is unchanged; only its internal fetch strategy changes. `_handle_mail_rule` now returns `0` immediately, without calling `M.fetch()` at all, when every UID matching the search criteria already has a `ProcessedMail` row.

- [ ] **Step 1: Write the failing test**

Add to `class TestMail` in `src/paperless_mail/tests/test_mail.py`:

```python
    def test_handle_mail_account_skips_body_fetch_for_already_processed_mail(
        self,
    ) -> None:
        """
        GIVEN:
            - An attachment-less mail under an attachments-only mark-read rule,
              already recorded as PROCESSED_WO_CONSUMPTION
        WHEN:
            - The mail account is processed again and the mail still matches the
              search criteria (it was never marked read, since no mail action is
              applied for the no-consumption case)
        THEN:
            - No IMAP body fetch happens for that mail; only the cheap UID search runs.
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
            consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        )

        message = self.mailMocker.messageBuilder.create_message(
            subject="No attachment",
            attachments=[],
        )
        self.mailMocker.bogus_mailbox.messages = [message]
        self.mailMocker.bogus_mailbox.updateClient()

        # First run: records ProcessedMail without consuming anything.
        self.mail_account_handler.handle_mail_account(account)
        self.assertTrue(
            ProcessedMail.objects.filter(
                rule=rule,
                uid=message.uid,
                folder=rule.folder,
            ).exists(),
        )
        self.mailMocker._queue_consumption_tasks_mock.assert_not_called()

        # Second run: message still matches UNSEEN (mark-read action never ran),
        # but its body must not be downloaded again.
        with mock.patch.object(
            self.mailMocker.bogus_mailbox,
            "fetch",
            wraps=self.mailMocker.bogus_mailbox.fetch,
        ) as fetch_spy:
            self.mail_account_handler.handle_mail_account(account)

        fetch_spy.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_handle_mail_account_skips_body_fetch_for_already_processed_mail -v`
Expected: FAIL — `fetch_spy.assert_not_called()` fails because the current code always calls `M.fetch()` for every message matching the search criteria, regardless of `ProcessedMail`.

- [ ] **Step 3: Implement the UID diff**

Replace `src/paperless_mail/mail.py:683-693`:

```python
        try:
            messages = M.fetch(
                criteria=criterias,
                mark_seen=False,
                charset=rule.account.character_set,
                bulk=True,
            )
        except Exception as err:
            raise MailError(
                f"Rule {rule}: Error while fetching folder {rule.folder}",
            ) from err
```

with:

```python
        try:
            all_uids = set(
                M.uids(criteria=criterias, charset=rule.account.character_set),
            )
        except Exception as err:
            raise MailError(
                f"Rule {rule}: Error while searching folder {rule.folder}",
            ) from err

        processed_uids_qs = ProcessedMail.objects.filter(
            rule=rule,
            folder=rule.folder,
            uid__in=all_uids,
        )
        if self._current_uid_validity is not None:
            processed_uids_qs = processed_uids_qs.filter(
                Q(uid_validity=self._current_uid_validity)
                | Q(uid_validity__isnull=True),
            )
        processed_uids = set(processed_uids_qs.values_list("uid", flat=True))

        new_uids = all_uids - processed_uids

        if not new_uids:
            self.log.debug(
                f"Rule {rule}: No new mail matching criteria {criterias}",
            )
            return 0

        try:
            messages = M.fetch(
                criteria=AND(uid=list(new_uids)),
                mark_seen=False,
                charset=rule.account.character_set,
                bulk=True,
            )
        except Exception as err:
            raise MailError(
                f"Rule {rule}: Error while fetching folder {rule.folder}",
            ) from err
```

Note the `uid_validity` handling here deliberately mirrors the existing per-message check at `mail.py:722-726` exactly (see Global Constraints) — the extra `Q(...)` filter is applied only when `self._current_uid_validity is not None`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_handle_mail_account_skips_body_fetch_for_already_processed_mail -v`
Expected: PASS

- [ ] **Step 5: Run the full `test_mail.py` suite (regression check, especially the uidvalidity tests)**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py -v`
Expected: all PASS, including:

- `test_handle_mail_account_skip_duplicate_uids_from_fetch`
- `test_handle_mail_account_skips_mail_already_processed_in_same_uidvalidity`
- `test_handle_mail_account_processes_mail_after_uidvalidity_change`
- `test_handle_mail_account_skips_mail_processed_before_uidvalidity_tracking`
- `test_handle_mail_account_processes_mail_when_uidvalidity_unavailable`
- `test_handle_mail_account_skips_mail_when_uidvalidity_unavailable_but_prior_record_exists`
- `test_handle_mail_account_overlapping_rules_only_first_consumes`

If any of these fail, the `uid_validity` branching in Step 3 does not match `mail.py:722-726` closely enough — re-check against the Global Constraints note before changing test expectations.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
git commit -m "fix: diff UIDs against ProcessedMail before fetching message bodies"
```

---

### Task 4: Batch the body fetch for large backlogs

**Files:**

- Modify: `src/paperless_mail/mail.py:74-76` (module-level constant)
- Modify: `src/paperless_mail/mail.py` (the `M.fetch(...)` block added in Task 3)
- Test: `src/paperless_mail/tests/test_mail.py` (new test in `class TestMail`)

**Interfaces:**

- Produces: module-level constant `paperless_mail.mail.MAIL_FETCH_BATCH_SIZE: int = 500`.
- Consumes: `itertools` (already imported at `mail.py:2`), `sorted_new_uids` derived from Task 3's `new_uids` set.

- [ ] **Step 1: Write the failing test**

Add to `class TestMail` in `src/paperless_mail/tests/test_mail.py`. Add `from paperless_mail.mail import MAIL_FETCH_BATCH_SIZE` to the imports at the top of the file (alongside the other `from paperless_mail.mail import ...` lines at `test_mail.py:35-38`).

```python
    @mock.patch("paperless_mail.mail.MAIL_FETCH_BATCH_SIZE", 5)
    def test_handle_mail_account_batches_body_fetch_for_large_backlog(self) -> None:
        """
        GIVEN:
            - More new/unprocessed mail than MAIL_FETCH_BATCH_SIZE
        WHEN:
            - The mail account is processed
        THEN:
            - The body fetch is issued in multiple batches
            - Every message is still processed (none dropped at a batch boundary)
        """
        account = MailAccount.objects.create(
            name="test",
            imap_server="",
            username="admin",
            password="secret",
        )
        rule = MailRule.objects.create(
            name="testrule",
            account=account,
            action=MailRule.MailAction.MARK_READ,
            consumption_scope=MailRule.ConsumptionScope.ATTACHMENTS_ONLY,
        )

        message_count = 12  # more than the patched batch size of 5
        self.mailMocker.bogus_mailbox.messages = [
            self.mailMocker.messageBuilder.create_message(
                subject=f"No attachment {i}",
                attachments=[],
            )
            for i in range(message_count)
        ]
        self.mailMocker.bogus_mailbox.updateClient()

        with mock.patch.object(
            self.mailMocker.bogus_mailbox,
            "fetch",
            wraps=self.mailMocker.bogus_mailbox.fetch,
        ) as fetch_spy:
            self.mail_account_handler.handle_mail_account(account)

        # ceil(12 / 5) == 3 batches
        self.assertEqual(fetch_spy.call_count, 3)
        self.assertEqual(
            ProcessedMail.objects.filter(rule=rule).count(),
            message_count,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_handle_mail_account_batches_body_fetch_for_large_backlog -v`
Expected: FAIL — either an `ImportError` for `MAIL_FETCH_BATCH_SIZE` (doesn't exist yet) or, once that import is stubbed out, `fetch_spy.call_count == 1` instead of `3` (Task 3's implementation fetches all new UIDs in one call).

- [ ] **Step 3: Add the constant and batch the fetch**

Insert after `src/paperless_mail/mail.py:74` (right after the `APPLE_MAIL_TAG_COLORS` dict closes, before `class MailError`):

```python
MAIL_FETCH_BATCH_SIZE = 500
```

Replace the `M.fetch(...)` block added in Task 3 (Task 3 Step 3's final `try/except`):

```python
        try:
            messages = M.fetch(
                criteria=AND(uid=list(new_uids)),
                mark_seen=False,
                charset=rule.account.character_set,
                bulk=True,
            )
        except Exception as err:
            raise MailError(
                f"Rule {rule}: Error while fetching folder {rule.folder}",
            ) from err
```

with:

```python
        sorted_new_uids = sorted(new_uids, key=int)
        message_batches = []
        for batch_start in range(0, len(sorted_new_uids), MAIL_FETCH_BATCH_SIZE):
            batch = sorted_new_uids[batch_start : batch_start + MAIL_FETCH_BATCH_SIZE]
            try:
                message_batches.append(
                    M.fetch(
                        criteria=AND(uid=batch),
                        mark_seen=False,
                        charset=rule.account.character_set,
                        bulk=True,
                    ),
                )
            except Exception as err:
                raise MailError(
                    f"Rule {rule}: Error while fetching folder {rule.folder}",
                ) from err

        messages = itertools.chain(*message_batches)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py::TestMail::test_handle_mail_account_batches_body_fetch_for_large_backlog -v`
Expected: PASS

- [ ] **Step 5: Run the full `test_mail.py` suite**

Run: `uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
git commit -m "perf: batch body fetches when many new UIDs are pending"
```

---

### Task 5: Full regression pass and lint

**Files:** none (verification only, plus any fixups this step surfaces)

- [ ] **Step 1: Run the full backend test suite with coverage/parallelism as configured**

Run: `uv run pytest src/paperless_mail/`
Expected: all `paperless_mail` tests PASS

- [ ] **Step 2: Run the full project test suite**

Run: `uv run pytest`
Expected: all tests PASS (no regressions outside `paperless_mail`)

- [ ] **Step 3: Lint and format**

Run: `uv run ruff check src/paperless_mail/` and `uv run ruff format --check src/paperless_mail/`
Expected: no errors. If `ruff format --check` reports files needing formatting, run `uv run ruff format src/paperless_mail/` and re-check.

- [ ] **Step 4: Type check against the frozen baselines**

Run: `uv run mypy src/paperless_mail/mail.py` (or the project's standard mypy invocation) and confirm no new violations beyond `.mypy-baseline.txt`.
Expected: no new errors introduced by this change.

- [ ] **Step 5: Commit any fixups**

If Steps 1-4 required changes:

```bash
git add -u
git commit -m "chore: fix lint/type fallout from mail fetch fix"
```

If no changes were needed, skip this step — nothing to commit.
