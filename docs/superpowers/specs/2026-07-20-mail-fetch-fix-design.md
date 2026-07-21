# Mail fetch fix: avoid re-downloading already-handled IMAP mail

## Problem

`paperless_mail`'s `_handle_mail_rule` (`src/paperless_mail/mail.py:641`) fetches
the full RFC822 body of every message an IMAP `SEARCH` matches (via
`M.fetch(criteria=criterias, ..., bulk=True)`), then does de-duplication in
Python afterward. Two things compound into a real bug (reported upstream in
[paperless-ngx#13175](https://github.com/paperless-ngx/paperless-ngx/issues/13175)):

1. **Full-body fetch happens before dedup.** The de-dup check against
   `ProcessedMail` (`mail.py:717-731`) happens per-message, after the body has
   already been downloaded for every matching message. Steady-state cost is
   _O(everything the search matches)_, not _O(new since last run)_.
2. **Attachment-less mail under an attachments-only rule is never recorded.**
   `_handle_message` (`mail.py:749`) returns early, before any attachment
   processing, when a message has no attachments and
   `rule.consumption_scope == ATTACHMENTS_ONLY`:

   ```python
   if (
       not message.attachments
       and rule.consumption_scope == MailRule.ConsumptionScope.ATTACHMENTS_ONLY
   ):
       return processed_elements  # 0, no ProcessedMail row, no mail action applied
   ```

   No `ProcessedMail` row is written and no mail action (mark-read/flag/tag)
   is applied, since both only happen via `queue_consumption_tasks`, which is
   only reached from the attachment/eml processing paths. The message keeps
   matching the search (e.g. `UNSEEN`) forever.

Combined: an inbox where most mail has no attachments gets fully re-downloaded
on every scheduled run (default every 10 minutes), indefinitely, for large
mailboxes -- confirmed against the current codebase, not user
misconfiguration.

## Goals

- Stop re-downloading full message bodies for mail that has already been
  handled (processed into a document, or determined to produce nothing).
- Record `ProcessedMail` for the no-attachment / attachments-only early-return
  case, so it participates in dedup like every other terminal outcome.
- No new required settings or DB migrations for existing installs.
- Graceful behavior on first run against a large existing mailbox (no single
  giant IMAP command, no giant in-memory batch).
- Preserve existing action/consumption semantics exactly for every path that
  currently produces a document or applies a mail action.

## Non-goals

- Changing what mail actions (mark-read/flag/tag/move/delete) get applied, or
  when.
- Applying a mail action to the no-attachment early-return case (explicitly
  out of scope -- see Decisions).
- Making batch size user-configurable.
- Touching EML_ONLY / EVERYTHING consumption scopes' semantics (they already
  don't hit the early-return branch described above).

## Decisions

These were settled during brainstorming and are load-bearing for the design
below:

- **Fix both halves together.** Recording `ProcessedMail` alone does not fix
  the bandwidth problem: without a mail action applied, an attachment-less
  message stays unseen and keeps matching the search criteria, so its body
  gets re-downloaded every run regardless of whether it gets reprocessed.
  Fixing only the bandwidth side without recording `ProcessedMail` would mean
  the UID-diff step never has anything to exclude for these messages. They
  must ship together.
- **No mailbox action for the no-attachment case.** Only a `ProcessedMail`
  row is written; the message is not marked read/flagged/moved/deleted. This
  matches the existing precedent for other no-consumption outcomes
  (`mail.py:960-977`, e.g. an attachment present but filtered out or an
  unsupported mime type) and avoids changing the user's mailbox state for
  mail paperless previously never touched.
- **UID-diff-before-fetch, not a BODYSTRUCTURE probe or SEARCH-side
  exclusion.** Considered and rejected:
  - BODYSTRUCTURE probing (fetch structure only, decide whether to fetch full
    body) only helps the attachments-only scope, not the general
    already-processed case, and `imap_tools` doesn't cleanly expose a
    structure-only fetch.
  - Excluding already-processed UIDs directly in the IMAP `SEARCH` criteria
    (`NOT UID (...)`) was rejected because for tens of thousands of
    already-processed UIDs the excluded-UID list itself blows up the command
    size -- worse than the two-step approach.
- **Batch size is a hardcoded constant**, not a new setting, per the
  "no new required settings" goal.

## Design

### `_handle_mail_rule` (`mail.py:641`)

Replace the single `M.fetch(criteria=criterias, ...)` call with:

1. `self._current_uid_validity` computed as today (unchanged, already first).
2. `criterias = make_criterias(...)` (unchanged).
3. `all_uids = set(M.uids(criteria=criterias, charset=rule.account.character_set))`
   -- a `UID SEARCH`, no bodies.
4. Query already-processed UIDs in one DB round trip, reusing the same
   uid_validity matching already used per-message:

   ```python
   processed_uids = set(
       ProcessedMail.objects.filter(
           rule=rule, folder=rule.folder, uid__in=all_uids,
       ).filter(
           Q(uid_validity=self._current_uid_validity) | Q(uid_validity__isnull=True),
       ).values_list("uid", flat=True)
   )
   ```

5. `new_uids = all_uids - processed_uids`. If empty: log at debug level and
   `return 0` -- no body fetch at all. This is the steady-state case.
6. Otherwise, iterate `new_uids` in fixed-size batches of
   `MAIL_FETCH_BATCH_SIZE = 500` (module-level constant), calling
   `M.fetch(criteria=AND(uid=batch), mark_seen=False, charset=rule.account.character_set, bulk=True)`
   per batch. Chain the resulting message iterators into the existing
   per-message loop (`mail.py:699+`) unchanged.
7. The existing per-message `already_processed` DB check
   (`mail.py:717-731`) stays in place unchanged, as a safety net against
   races (e.g. concurrent rule runs against the same folder in this pass) and
   to keep behavior identical if steps 3/4 ever disagree with it.

### New helper: `_record_processed_without_consumption`

Extract the existing dedup-and-create block at `mail.py:960-977` into a
method on the same class:

```python
def _record_processed_without_consumption(self, message, rule) -> None:
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
            received=make_aware(message.date) if is_naive(message.date) else message.date,
            status="PROCESSED_WO_CONSUMPTION",
        )
```

Call sites:

- `_process_attachments`'s existing no-consumables branch (replaces the
  inline block, same behavior).
- `_handle_message`'s early return (`mail.py:756-760`), newly, for the
  no-attachments-under-attachments-only-scope case.

### Data flow (steady state, nothing new)

search criteria (unchanged) -> `UID SEARCH` for matching UIDs (cheap) ->
subtract UIDs already in `ProcessedMail` (cheap, DB-only) -> zero new UIDs ->
no fetch, no body download.

### Data flow (new mail present)

... same as above -> some UIDs remain -> fetch bodies only for those,
batched -> existing per-message processing, action application, and
`ProcessedMail` recording, unchanged except the no-attachment early return
now also calls `_record_processed_without_consumption`.

## Error handling

- `M.uids(...)` raising is wrapped in the same `try/except` that currently
  wraps `M.fetch(...)` (`mail.py:683-693`), surfacing as `MailError`
  identically to today's search-failure behavior.
- A batch's `M.fetch(...)` raising mid-loop is caught by the same
  `try/except`, applied per-batch. One failing batch fails the whole rule
  run for this pass -- matching today's all-or-nothing semantics (currently
  a single failed fetch already fails the whole rule).
- Empty `new_uids` short-circuits before any fetch, so it can't hit fetch
  error paths at all for the common case.
- `_record_processed_without_consumption` reuses the existing
  `ProcessedMail.objects.create` call already in production use; no new
  failure mode introduced.

## Testing

In `src/paperless_mail/tests/test_mail.py`:

- Extend the `BogusMailBox` test double with a `uids()` method that mirrors
  its existing `fetch()` criteria matching but returns only UIDs.
- New test: an attachment-less message under an attachments-only mark-read
  rule is recorded as `PROCESSED_WO_CONSUMPTION` on the first run. On a
  second run, with the same message still unseen server-side, assert no
  body fetch happens (only `M.uids()` is called) -- i.e. steady state costs
  one search and zero body downloads.
- New test: a folder with more new UIDs than `MAIL_FETCH_BATCH_SIZE` results
  in multiple batched `fetch` calls, and all messages are still processed
  (no messages dropped at a batch boundary).
- Update existing `test_handle_empty_message` to assert a
  `PROCESSED_WO_CONSUMPTION` row now exists for the no-attachment case.
- Regression: existing tests for `EML_ONLY`/`EVERYTHING` scopes and the
  multi-rule-same-folder dedup (`consumed_messages` set) should pass
  unchanged, since neither the per-message `already_processed` check nor the
  `consumed_messages` set logic is touched by this design.

## Open questions / risks

- `imap_tools`'s `AND(uid=batch)` criteria builder needs to be confirmed to
  produce a valid `UID FETCH <list>` command at the batch sizes used here;
  covered by the batching test above.
- If a mail server doesn't support `UID SEARCH` the same way it supports the
  existing `fetch`'s implicit search, `M.uids()` could behave differently
  from today's `M.fetch()` on some edge-case server. Existing project test
  coverage (via `BogusMailBox`) won't catch server-specific quirks; this is
  the same class of risk as any IMAP-behavior assumption already baked into
  this module.
