# Unicode NFC Normalization for Filesystem Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure all filesystem paths stored in the database and written to disk use NFC Unicode normalization, preventing "file not found" failures caused by byte-level mismatches between visually identical filenames (e.g., NFD `ü` = `u + combining diaeresis` vs NFC `ü` = single codepoint U+00FC).

**Architecture:** The fix has two layers. The primary fix normalizes the output of `clean_filepath()` in `FilePathTemplate.render()` — this is the single choke point through which all template-rendered filenames pass. Defense-in-depth changes normalize input strings before `pathvalidate.sanitize_filename()` in the context builder functions. A separate fix normalizes mail attachment filenames at the entry point. Existing documents with NFD paths will be transparently migrated to NFC on their next save (the file move logic already handles the case where old and new paths differ).

**Tech Stack:** Python `unicodedata.normalize('NFC', ...)`, `pathvalidate`, Django, Jinja2, pytest

---

## Background: The Bug

`pathvalidate.sanitize_filename()` removes illegal filesystem characters but does **not** normalize Unicode. NFC `ü` (UTF-8: `c3 bc`) and NFD `ü` (UTF-8: `75 cc 88`) are visually identical but produce different byte sequences. On Linux filesystems with no normalization (default ZFS, ext4), these are treated as distinct filenames. If an LLM or OCR engine produces NFD text for a document title, the generated filesystem path contains NFD bytes. If the same title is later regenerated in NFC form (LLM output is non-deterministic), the path lookup fails: `old_source_path.is_file()` returns `False` even though a file with the same visual name exists on disk.

## File Structure

| File                                        | Change                                                                                                                                                                                    |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/documents/templating/filepath.py`      | Add NFC normalization in `clean_filepath()` (primary fix) + input normalization in `get_basic_metadata_context()`, `get_tags_context()`, `get_custom_fields_context()` (defense-in-depth) |
| `src/paperless_mail/mail.py`                | Normalize attachment filenames before `pathvalidate.sanitize_filename()`                                                                                                                  |
| `src/documents/tests/test_file_handling.py` | Tests for NFC normalization in `generate_filename()`                                                                                                                                      |
| `src/paperless_mail/tests/test_mail.py`     | Tests for NFC normalization in mail attachment handling                                                                                                                                   |

---

## Task 1: Normalize `clean_filepath()` output (primary fix)

This is the single choke point. ALL template-rendered paths pass through `clean_filepath()` before being stored in `document.filename`. Fixing this alone prevents the bug for every path generated via the filename format system — including `{{ title }}` (sanitized context), `{{ document.title }}` (raw context), `{{ correspondent }}`, and every other template variable.

**Files:**

- Modify: `src/documents/templating/filepath.py:36-48`
- Test: `src/documents/tests/test_file_handling.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `src/documents/tests/test_file_handling.py`, inside `class TestFileHandling`:

```python
import unicodedata

@override_settings(FILENAME_FORMAT="{{ title }}")
def test_generate_filename_nfc_normalizes_nfd_title(self) -> None:
    """NFD title (u + combining diaeresis) must produce NFC path bytes."""
    nfd_title = unicodedata.normalize("NFD", "Gemüse")
    nfc_title = unicodedata.normalize("NFC", "Gemüse")
    assert nfd_title != nfc_title  # confirm inputs differ at byte level

    doc = Document.objects.create(title=nfd_title, mime_type="application/pdf")
    result = generate_filename(doc)

    assert str(result) == f"{nfc_title}.pdf"
    assert str(result).encode() == f"{nfc_title}.pdf".encode()

@override_settings(FILENAME_FORMAT="{{ correspondent }}/{{ title }}")
def test_generate_filename_nfc_normalizes_nfd_correspondent(self) -> None:
    """NFD correspondent name must produce NFC path component."""
    nfd_name = unicodedata.normalize("NFD", "Müller")
    nfc_name = unicodedata.normalize("NFC", "Müller")

    correspondent = Correspondent.objects.create(name=nfd_name)
    doc = Document.objects.create(
        title="invoice",
        correspondent=correspondent,
        mime_type="application/pdf",
    )
    result = generate_filename(doc)

    assert str(result) == f"{nfc_name}/invoice.pdf"
    assert str(result).encode() == f"{nfc_name}/invoice.pdf".encode()

@override_settings(FILENAME_FORMAT="{{ document.title }}")
def test_generate_filename_nfc_normalizes_raw_document_title_in_template(self) -> None:
    """NFD title accessed via document.title (unsanitized context) must also be NFC."""
    nfd_title = unicodedata.normalize("NFD", "Café")
    nfc_title = unicodedata.normalize("NFC", "Café")

    doc = Document.objects.create(title=nfd_title, mime_type="application/pdf")
    result = generate_filename(doc)

    assert str(result) == f"{nfc_title}.pdf"
    assert str(result).encode() == f"{nfc_title}.pdf".encode()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest --override-ini="addopts=" src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_nfd_title src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_nfd_correspondent src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_raw_document_title_in_template -v
```

Expected: all three FAIL (NFD title produces NFD path, assertion fails).

- [ ] **Step 3: Add NFC normalization to `clean_filepath()`**

In `src/documents/templating/filepath.py`, add `import unicodedata` at the top of the file and modify `clean_filepath()`:

```python
import unicodedata  # add to top-of-file imports

class FilePathTemplate(Template):
    def render(self, *args, **kwargs) -> str:
        def clean_filepath(value: str) -> str:
            """
            Clean up a filepath by:
            1. Normalizing to NFC Unicode form to prevent byte-level mismatches
               between visually identical filenames on case-sensitive filesystems
            2. Removing newlines and carriage returns
            3. Removing extra spaces before and after forward slashes
            4. Preserving spaces in other parts of the path
            """
            value = unicodedata.normalize("NFC", value)
            value = value.replace("\n", "").replace("\r", "")
            value = re.sub(r"\s*/\s*", "/", value)

            # We remove trailing and leading separators, as these are always relative paths, not absolute, even if the user
            # tries
            return value.strip().strip(os.sep)

        original_render = super().render(*args, **kwargs)

        return clean_filepath(original_render)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest --override-ini="addopts=" src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_nfd_title src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_nfd_correspondent src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_raw_document_title_in_template -v
```

Expected: all three PASS.

- [ ] **Step 5: Run the full file-handling test suite to check for regressions**

```bash
uv run pytest --override-ini="addopts=" src/documents/tests/test_file_handling.py -v
```

Expected: all existing tests continue to pass (ASCII titles are unaffected by NFC normalization).

- [ ] **Step 6: Commit**

```bash
git add src/documents/templating/filepath.py src/documents/tests/test_file_handling.py
git commit -m "Fix: normalize filesystem paths to NFC Unicode to prevent byte-level mismatches"
```

---

## Task 2: Defense-in-depth normalization in context builders

`clean_filepath()` (Task 1) fixes the rendered path. These changes normalize the input strings that go into `pathvalidate.sanitize_filename()` within the context builders — belt-and-suspenders so the sanitized shorthand variables (`{{ title }}`, `{{ correspondent }}`, `{{ tag_list }}`, `{{ custom_fields }}`) are also NFC before sanitization. This matters because the sanitized strings could theoretically be compared directly against DB-stored values in other contexts.

**Files:**

- Modify: `src/documents/templating/filepath.py:171-319`
- Test: `src/documents/tests/test_file_handling.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `TestFileHandling` in `src/documents/tests/test_file_handling.py`:

```python
@override_settings(FILENAME_FORMAT="{{ tag_list }}/{{ title }}")
def test_generate_filename_nfc_normalizes_nfd_tag_list(self) -> None:
    """NFD tag names must produce NFC path component in tag_list."""
    nfd_name = unicodedata.normalize("NFD", "Büro")
    nfc_name = unicodedata.normalize("NFC", "Büro")

    doc = Document.objects.create(title="doc", mime_type="application/pdf")
    doc.tags.create(name=nfd_name)
    result = generate_filename(doc)

    assert str(result) == f"{nfc_name}/doc.pdf"
    assert str(result).encode() == f"{nfc_name}/doc.pdf".encode()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest --override-ini="addopts=" src/documents/tests/test_file_handling.py::TestFileHandling::test_generate_filename_nfc_normalizes_nfd_tag_list -v
```

Expected: FAIL. (The tag_list is already caught by `clean_filepath()` from Task 1, but we want a test that directly validates input normalization through the sanitize call.)

Note: this test may already pass after Task 1 due to `clean_filepath()`. If so, keep the test as a regression guard and move straight to the implementation.

- [ ] **Step 3: Normalize inputs in `get_basic_metadata_context()`**

In `src/documents/templating/filepath.py`, update `get_basic_metadata_context()`. The `unicodedata` import was added in Task 1.

```python
def get_basic_metadata_context(
    document: Document,
    *,
    no_value_default: str = NO_VALUE_PLACEHOLDER,
) -> dict[str, str]:
    """
    Given a Document, constructs some basic information about it.  If certain values are not set,
    they will be replaced with the no_value_default.

    Regardless of set or not, the values will be sanitized
    """
    return {
        "title": pathvalidate.sanitize_filename(
            unicodedata.normalize("NFC", document.title),
            replacement_text="-",
        ),
        "correspondent": pathvalidate.sanitize_filename(
            unicodedata.normalize("NFC", document.correspondent.name),
            replacement_text="-",
        )
        if document.correspondent
        else no_value_default,
        "document_type": pathvalidate.sanitize_filename(
            unicodedata.normalize("NFC", document.document_type.name),
            replacement_text="-",
        )
        if document.document_type
        else no_value_default,
        "asn": str(document.archive_serial_number)
        if document.archive_serial_number
        else no_value_default,
        "owner_username": document.owner.username
        if document.owner
        else no_value_default,
        "original_name": PurePath(document.original_filename).with_suffix("").name
        if document.original_filename
        else no_value_default,
        "doc_pk": f"{document.pk:07}",
    }
```

- [ ] **Step 4: Normalize inputs in `get_tags_context()`**

Update `get_tags_context()` in the same file:

```python
def get_tags_context(tags: Iterable[Tag]) -> dict[str, str | list[str]]:
    """
    Given an Iterable of tags, constructs some context from them for usage
    """
    return {
        "tag_list": pathvalidate.sanitize_filename(
            ",".join(
                sorted(unicodedata.normalize("NFC", tag.name) for tag in tags),
            ),
            replacement_text="-",
        ),
        # Assumed to be ordered, but a template could loop through to find what they want
        "tag_name_list": [unicodedata.normalize("NFC", x.name) for x in tags],
    }
```

- [ ] **Step 5: Normalize string-type inputs in `get_custom_fields_context()`**

Update `get_custom_fields_context()` in the same file. Only string-type fields (MONETARY, STRING, URL, LONG_TEXT, SELECT) go through `sanitize_filename()`; the others (dates, numbers, booleans) cannot contain non-ASCII unicode. Also normalize the field name itself.

```python
def get_custom_fields_context(
    custom_fields: Iterable[CustomFieldInstance],
) -> dict[str, dict[str, dict[str, str]]]:
    """
    Given an Iterable of CustomFieldInstance, builds a dictionary mapping the field name
    to its type and value
    """
    field_data = {"custom_fields": {}}
    for field_instance in custom_fields:
        type_ = pathvalidate.sanitize_filename(
            field_instance.field.data_type,
            replacement_text="-",
        )
        if field_instance.value is None:
            value = None
        # String types need to be sanitized
        elif field_instance.field.data_type in {
            CustomField.FieldDataType.MONETARY,
            CustomField.FieldDataType.STRING,
            CustomField.FieldDataType.URL,
            CustomField.FieldDataType.LONG_TEXT,
        }:
            value = pathvalidate.sanitize_filename(
                unicodedata.normalize("NFC", field_instance.value),
                replacement_text="-",
            )
        elif (
            field_instance.field.data_type == CustomField.FieldDataType.SELECT
            and field_instance.field.extra_data["select_options"] is not None
        ):
            options = field_instance.field.extra_data["select_options"]
            value = pathvalidate.sanitize_filename(
                unicodedata.normalize(
                    "NFC",
                    next(
                        option["label"]
                        for option in options
                        if option["id"] == field_instance.value
                    ),
                ),
                replacement_text="-",
            )
        else:
            value = field_instance.value
        field_data["custom_fields"][
            pathvalidate.sanitize_filename(
                unicodedata.normalize("NFC", field_instance.field.name),
                replacement_text="-",
            )
        ] = {
            "type": type_,
            "value": value,
        }
    return field_data
```

- [ ] **Step 6: Run the new test and full test suite**

```bash
uv run pytest --override-ini="addopts=" src/documents/tests/test_file_handling.py -v
```

Expected: all tests pass, including the new tag test.

- [ ] **Step 7: Commit**

```bash
git add src/documents/templating/filepath.py src/documents/tests/test_file_handling.py
git commit -m "Fix: normalize context builder inputs to NFC before sanitize_filename (defense-in-depth)"
```

---

## Task 3: Normalize mail attachment filenames

Email attachment filenames come from MIME headers and can be in any Unicode normalization depending on the sending client. These flow into `document.original_filename` and then into `{{ original_name }}` template context. They also become the temp file name created on disk.

**Files:**

- Modify: `src/paperless_mail/mail.py`
- Test: `src/paperless_mail/tests/test_mail.py`

- [ ] **Step 1: Find the exact lines in mail.py**

```bash
grep -n "sanitize_filename" src/paperless_mail/mail.py
```

Expected output (line numbers may vary):

```
NNN:                attachment_name = pathvalidate.sanitize_filename(att.filename)
NNN:                    filename=pathvalidate.sanitize_filename(att.filename),
NNN:            filename=pathvalidate.sanitize_filename(f"{message.subject}.eml"),
```

Note the line numbers for the next step.

- [ ] **Step 2: Write a failing test**

Find an existing test in `src/paperless_mail/tests/test_mail.py` that exercises attachment filename handling (search for `sanitize_filename` or `att.filename` in that file to find a good base test to copy). Add a new test that uses an NFD attachment filename.

The following test goes into the appropriate `TestCase` class in `src/paperless_mail/tests/test_mail.py`. Look at the file first to confirm the right class and mock patterns — the test below follows the existing pattern for mocking `MailMessage` and `Attachment` objects:

```python
def test_attachment_filename_nfd_normalized_to_nfc(self) -> None:
    """Mail attachment filenames with NFD encoding must be normalized to NFC."""
    import unicodedata
    nfd_name = unicodedata.normalize("NFD", "Rechnung März.pdf")
    nfc_name = unicodedata.normalize("NFC", "Rechnung März.pdf")
    assert nfd_name != nfc_name  # confirm inputs differ at byte level

    # Use whatever mock/factory pattern exists in this test file for creating
    # a fake attachment with a specific filename, then run the mail handler,
    # and assert that document.original_filename == nfc_name (not nfd_name).
    # Adapt the mock setup to match the test file's existing patterns exactly.
```

To find the right mock pattern: `grep -n "att.filename\|Attachment\|MailMessage\|MagicMock" src/paperless_mail/tests/test_mail.py | head -20`

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py -k "test_attachment_filename_nfd" -v
```

Expected: FAIL.

- [ ] **Step 4: Add `import unicodedata` to mail.py**

At the top of `src/paperless_mail/mail.py`, add:

```python
import unicodedata
```

- [ ] **Step 5: Normalize attachment filenames in mail.py**

At each of the three `pathvalidate.sanitize_filename` call sites found in Step 1, wrap the input string with `unicodedata.normalize("NFC", ...)`:

For the attachment temp file creation:

```python
attachment_name = pathvalidate.sanitize_filename(
    unicodedata.normalize("NFC", att.filename)
)
```

For the metadata override filename:

```python
filename=pathvalidate.sanitize_filename(
    unicodedata.normalize("NFC", att.filename)
),
```

For the EML subject filename:

```python
filename=pathvalidate.sanitize_filename(
    unicodedata.normalize("NFC", f"{message.subject}.eml")
),
```

- [ ] **Step 6: Run the mail test suite**

```bash
uv run pytest --override-ini="addopts=" src/paperless_mail/tests/test_mail.py -v
```

Expected: all tests pass, including the new NFD normalization test.

- [ ] **Step 7: Commit**

```bash
git add src/paperless_mail/mail.py src/paperless_mail/tests/test_mail.py
git commit -m "Fix: normalize mail attachment filenames to NFC Unicode"
```

---

## Self-Review Checklist

### Spec coverage

| Requirement                                               | Covered by                                            |
| --------------------------------------------------------- | ----------------------------------------------------- |
| `clean_filepath()` normalizes all template-rendered paths | Task 1 Step 3                                         |
| `{{ title }}` (sanitized context) produces NFC output     | Task 1 test + Task 2 Step 3                           |
| `{{ document.title }}` (raw context) produces NFC output  | Task 1 test                                           |
| `{{ correspondent }}` produces NFC output                 | Task 1 test + Task 2 Step 3                           |
| `{{ tag_list }}` and `tag_name_list` produce NFC output   | Task 2 Steps 1+4                                      |
| Custom field string values produce NFC output             | Task 2 Step 5                                         |
| Mail attachment filenames normalized at entry point       | Task 3                                                |
| Existing NFD files auto-migrate to NFC on next save       | Handled by existing move logic; no code change needed |

### Notes for implementer

- The `FILENAME_FORMAT` setting accepts old-style `{title}` format strings, which `convert_format_str_to_template_format()` converts to Jinja2 `{{ title }}` before rendering. Tests using `@override_settings(FILENAME_FORMAT="{{ title }}")` use Jinja2 syntax directly.
- Run tests with `--override-ini="addopts="` to disable coverage and parallelism for faster iteration.
- The `unicodedata` module is part of the Python standard library — no new dependency.
- NFC is the right normalization form for filenames: it is the default on macOS (HFS+/APFS) and the form most databases and text processing tools produce. NFD is what macOS HFS+ _internally_ normalizes to when writing (but presents as NFC), and what some OCR/LLM outputs occasionally produce.
