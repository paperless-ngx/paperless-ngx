# AI Taxonomy Candidate Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject the user's existing taxonomy (tags, correspondents, document types, storage paths) as candidates into the LLM prompt so it prefers exact existing names over inventing new ones.

**Architecture:** A new `get_taxonomy_candidates(user)` helper fetches each category permission-filtered to the requesting user, annotated with document-count for frequency ordering, and capped at 200 per category. A private `_format_candidates_section` helper renders the candidate lists into a prompt appendix. `build_prompt_without_rag` and `build_prompt_with_rag` each gain an optional `candidates` parameter. `get_ai_document_classification` wires it all together — fetch candidates then pass them to the prompt builder. No changes to the view, matching layer, or response format.

**Tech Stack:** Django ORM (`annotate`, `Count`), `get_objects_for_user_owner_aware` (already used in `matching.py`), pytest + `unittest.mock`

---

## File Map

- **Modify:** `src/paperless_ai/ai_classifier.py`
  - Add constant `TAXONOMY_CANDIDATE_LIMIT = 200`
  - Add `get_taxonomy_candidates(user)` helper
  - Add `_format_candidates_section(candidates)` helper
  - Update `build_prompt_without_rag` signature and body
  - Update `build_prompt_with_rag` signature and body
  - Update `get_ai_document_classification` body
- **Create:** `src/paperless_ai/tests/test_taxonomy_candidates.py`
  - All new tests for the above

---

### Task 1: `get_taxonomy_candidates` — tests + implementation

**Files:**

- Modify: `src/paperless_ai/ai_classifier.py`
- Create: `src/paperless_ai/tests/test_taxonomy_candidates.py`

- [ ] **Step 1: Write the failing tests**

Create `src/paperless_ai/tests/test_taxonomy_candidates.py`:

```python
import pytest
from unittest.mock import patch

from django.contrib.auth.models import User

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from paperless_ai.ai_classifier import TAXONOMY_CANDIDATE_LIMIT
from paperless_ai.ai_classifier import get_taxonomy_candidates


def test_get_taxonomy_candidates_returns_none_for_none_user():
    assert get_taxonomy_candidates(None) is None


@pytest.mark.django_db
class TestGetTaxonomyCandidates:
    def test_returns_dict_with_four_keys(self):
        user = User.objects.create_user(username="tc_user1", password="x")
        with patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
        ) as mock_get:
            mock_get.side_effect = [
                Tag.objects.none(),
                Correspondent.objects.none(),
                DocumentType.objects.none(),
                StoragePath.objects.none(),
            ]
            result = get_taxonomy_candidates(user)
        assert result is not None
        assert set(result.keys()) == {
            "tags",
            "correspondents",
            "document_types",
            "storage_paths",
        }

    def test_returns_names_as_strings(self):
        user = User.objects.create_user(username="tc_user2", password="x")
        tag = Tag.objects.create(name="Bloodwork")
        with patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
        ) as mock_get:
            mock_get.side_effect = [
                Tag.objects.filter(pk=tag.pk),
                Correspondent.objects.none(),
                DocumentType.objects.none(),
                StoragePath.objects.none(),
            ]
            result = get_taxonomy_candidates(user)
        assert result["tags"] == ["Bloodwork"]

    def test_orders_tags_by_document_count_descending(self):
        user = User.objects.create_user(username="tc_user3", password="x")
        tag_low = Tag.objects.create(name="LowUse")
        tag_high = Tag.objects.create(name="HighUse")

        doc1 = Document.objects.create(mime_type="text/plain", checksum="tc_doc1")
        doc2 = Document.objects.create(mime_type="text/plain", checksum="tc_doc2")
        doc3 = Document.objects.create(mime_type="text/plain", checksum="tc_doc3")
        doc1.tags.add(tag_high)
        doc2.tags.add(tag_high)
        doc3.tags.add(tag_low)

        with patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
        ) as mock_get:
            mock_get.side_effect = [
                Tag.objects.filter(pk__in=[tag_low.pk, tag_high.pk]),
                Correspondent.objects.none(),
                DocumentType.objects.none(),
                StoragePath.objects.none(),
            ]
            result = get_taxonomy_candidates(user)

        assert result["tags"] == ["HighUse", "LowUse"]

    def test_caps_results_at_taxonomy_candidate_limit(self):
        user = User.objects.create_user(username="tc_user4", password="x")
        tags = [Tag.objects.create(name=f"Tag{i}") for i in range(5)]

        with (
            patch(
                "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
            ) as mock_get,
            patch("paperless_ai.ai_classifier.TAXONOMY_CANDIDATE_LIMIT", 3),
        ):
            mock_get.side_effect = [
                Tag.objects.filter(pk__in=[t.pk for t in tags]),
                Correspondent.objects.none(),
                DocumentType.objects.none(),
                StoragePath.objects.none(),
            ]
            result = get_taxonomy_candidates(user)

        assert len(result["tags"]) == 3

    def test_all_four_categories_are_fetched(self):
        user = User.objects.create_user(username="tc_user5", password="x")
        tag = Tag.objects.create(name="MyTag")
        corr = Correspondent.objects.create(name="MyCorr")
        dt = DocumentType.objects.create(name="MyType")
        sp = StoragePath.objects.create(name="MyPath", path="/my/path")

        with patch(
            "paperless_ai.ai_classifier.get_objects_for_user_owner_aware",
        ) as mock_get:
            mock_get.side_effect = [
                Tag.objects.filter(pk=tag.pk),
                Correspondent.objects.filter(pk=corr.pk),
                DocumentType.objects.filter(pk=dt.pk),
                StoragePath.objects.filter(pk=sp.pk),
            ]
            result = get_taxonomy_candidates(user)

        assert result["tags"] == ["MyTag"]
        assert result["correspondents"] == ["MyCorr"]
        assert result["document_types"] == ["MyType"]
        assert result["storage_paths"] == ["MyPath"]
```

- [ ] **Step 2: Run to confirm they all fail**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: `ImportError` or `FAILED` — `get_taxonomy_candidates` does not exist yet.

- [ ] **Step 3: Add the implementation to `ai_classifier.py`**

At the top of `src/paperless_ai/ai_classifier.py`, add new imports after the existing ones:

```python
from django.db.models import Count

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import get_objects_for_user_owner_aware
```

Add the constant and helper right after the `logger` line:

```python
TAXONOMY_CANDIDATE_LIMIT = 200


def get_taxonomy_candidates(user: User | None) -> dict[str, list[str]] | None:
    if user is None:
        return None

    tags = (
        get_objects_for_user_owner_aware(user, ["view_tag"], Tag)
        .annotate(doc_count=Count("documents"))
        .order_by("-doc_count")[:TAXONOMY_CANDIDATE_LIMIT]
    )
    correspondents = (
        get_objects_for_user_owner_aware(user, ["view_correspondent"], Correspondent)
        .annotate(doc_count=Count("documents"))
        .order_by("-doc_count")[:TAXONOMY_CANDIDATE_LIMIT]
    )
    document_types = (
        get_objects_for_user_owner_aware(user, ["view_documenttype"], DocumentType)
        .annotate(doc_count=Count("documents"))
        .order_by("-doc_count")[:TAXONOMY_CANDIDATE_LIMIT]
    )
    storage_paths = (
        get_objects_for_user_owner_aware(user, ["view_storagepath"], StoragePath)
        .annotate(doc_count=Count("documents"))
        .order_by("-doc_count")[:TAXONOMY_CANDIDATE_LIMIT]
    )

    return {
        "tags": [t.name for t in tags],
        "correspondents": [c.name for c in correspondents],
        "document_types": [d.name for d in document_types],
        "storage_paths": [s.name for s in storage_paths],
    }
```

- [ ] **Step 4: Run to confirm Task 1 tests pass**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: all 6 tests `PASSED`.

- [ ] **Step 5: Confirm existing AI classifier tests still pass**

```bash
cd src && uv run pytest paperless_ai/tests/test_ai_classifier.py --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: all tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/ai_classifier.py src/paperless_ai/tests/test_taxonomy_candidates.py
git commit -m "feat: add get_taxonomy_candidates helper with frequency ordering and cap"
```

---

### Task 2: Prompt injection — `_format_candidates_section` + `build_prompt_without_rag`

**Files:**

- Modify: `src/paperless_ai/ai_classifier.py`
- Modify: `src/paperless_ai/tests/test_taxonomy_candidates.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless_ai/tests/test_taxonomy_candidates.py`:

```python
from unittest.mock import MagicMock

from paperless_ai.ai_classifier import build_prompt_without_rag


@pytest.fixture
def mock_doc():
    doc = MagicMock(spec=Document)
    doc.filename = "invoice.pdf"
    doc.content = "Some document content."
    return doc


class TestBuildPromptWithoutRag:
    def test_no_candidates_section_when_candidates_is_none(self, mock_doc):
        prompt = build_prompt_without_rag(mock_doc, candidates=None)
        assert "Existing metadata" not in prompt

    def test_no_candidates_section_when_candidates_is_empty_dict(self, mock_doc):
        prompt = build_prompt_without_rag(mock_doc, candidates={})
        assert "Existing metadata" not in prompt

    def test_candidates_section_present_when_provided(self, mock_doc):
        candidates = {
            "tags": ["Bloodwork", "Insurance"],
            "correspondents": ["Dr. Smith"],
            "document_types": [],
            "storage_paths": [],
        }
        prompt = build_prompt_without_rag(mock_doc, candidates=candidates)
        assert "Existing metadata" in prompt
        assert "Bloodwork" in prompt
        assert "Dr. Smith" in prompt

    def test_empty_categories_omitted_from_section(self, mock_doc):
        candidates = {
            "tags": ["Bloodwork"],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
        }
        prompt = build_prompt_without_rag(mock_doc, candidates=candidates)
        assert "Correspondents:" not in prompt
        assert "Document types:" not in prompt
        assert "Storage paths:" not in prompt

    def test_existing_prompt_content_preserved(self, mock_doc):
        prompt = build_prompt_without_rag(mock_doc, candidates=None)
        assert "invoice.pdf" in prompt
        assert "Some document content." in prompt
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py::TestBuildPromptWithoutRag --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: `FAILED` — `build_prompt_without_rag` doesn't accept `candidates` yet.

- [ ] **Step 3: Add `_format_candidates_section` and update `build_prompt_without_rag` in `ai_classifier.py`**

Add `_format_candidates_section` immediately after `get_taxonomy_candidates`:

```python
def _format_candidates_section(candidates: dict[str, list[str]]) -> str:
    lines = [
        "Existing metadata (use exact names where they fit; suggest new ones only if nothing matches):",
    ]
    for key, label in [
        ("tags", "Tags"),
        ("correspondents", "Correspondents"),
        ("document_types", "Document types"),
        ("storage_paths", "Storage paths"),
    ]:
        names = candidates.get(key, [])
        if names:
            lines.append(f"{label}: {', '.join(names)}")
    return "\n".join(lines)
```

Replace the existing `build_prompt_without_rag`:

```python
def build_prompt_without_rag(
    document: Document,
    candidates: dict[str, list[str]] | None = None,
) -> str:
    filename = document.filename or ""
    content = truncate_content(document.content[:4000] or "")

    prompt = f"""
    You are a document classification assistant.

    Analyze the following document and extract the following information:
    - A short descriptive title
    - Tags that reflect the content
    - Names of people or organizations mentioned
    - The type or category of the document
    - Suggested folder paths for storing the document
    - Up to 3 relevant dates in YYYY-MM-DD format

    Filename:
    {filename}

    Content:
    {content}
    """.strip()

    if candidates:
        prompt += "\n\n" + _format_candidates_section(candidates)

    return prompt
```

- [ ] **Step 4: Run to confirm Task 2 tests pass**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py::TestBuildPromptWithoutRag --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: all 5 tests `PASSED`.

- [ ] **Step 5: Run full test file to check no regressions**

```bash
cd src && uv run pytest paperless_ai/tests/ --override-ini="addopts=" -v 2>&1 | tail -30
```

Expected: all tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/ai_classifier.py src/paperless_ai/tests/test_taxonomy_candidates.py
git commit -m "feat: inject taxonomy candidates into build_prompt_without_rag"
```

---

### Task 3: Update `build_prompt_with_rag`

**Files:**

- Modify: `src/paperless_ai/ai_classifier.py`
- Modify: `src/paperless_ai/tests/test_taxonomy_candidates.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless_ai/tests/test_taxonomy_candidates.py`:

```python
from paperless_ai.ai_classifier import build_prompt_with_rag


class TestBuildPromptWithRag:
    def test_no_candidates_section_when_candidates_is_none(self, mock_doc):
        with patch(
            "paperless_ai.ai_classifier.get_context_for_document",
            return_value="similar doc context",
        ):
            prompt = build_prompt_with_rag(mock_doc, candidates=None)
        assert "Existing metadata" not in prompt

    def test_candidates_section_present_when_provided(self, mock_doc):
        candidates = {
            "tags": ["Insurance"],
            "correspondents": [],
            "document_types": ["Invoice"],
            "storage_paths": [],
        }
        with patch(
            "paperless_ai.ai_classifier.get_context_for_document",
            return_value="similar doc context",
        ):
            prompt = build_prompt_with_rag(mock_doc, candidates=candidates)
        assert "Existing metadata" in prompt
        assert "Insurance" in prompt
        assert "Invoice" in prompt

    def test_rag_context_still_present(self, mock_doc):
        with patch(
            "paperless_ai.ai_classifier.get_context_for_document",
            return_value="similar doc context",
        ):
            prompt = build_prompt_with_rag(mock_doc, candidates=None)
        assert "similar doc context" in prompt
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py::TestBuildPromptWithRag --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: `FAILED` — `build_prompt_with_rag` doesn't accept `candidates` yet.

- [ ] **Step 3: Update `build_prompt_with_rag` in `ai_classifier.py`**

Replace the existing `build_prompt_with_rag`:

```python
def build_prompt_with_rag(
    document: Document,
    user: User | None = None,
    candidates: dict[str, list[str]] | None = None,
) -> str:
    base_prompt = build_prompt_without_rag(document, candidates)
    context = truncate_content(get_context_for_document(document, user))

    return f"""{base_prompt}

    Additional context from similar documents:
    {context}
    """.strip()
```

- [ ] **Step 4: Run to confirm Task 3 tests pass**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py::TestBuildPromptWithRag --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: all 3 tests `PASSED`.

- [ ] **Step 5: Run full test file to check no regressions**

```bash
cd src && uv run pytest paperless_ai/tests/ --override-ini="addopts=" -v 2>&1 | tail -30
```

Expected: all tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/ai_classifier.py src/paperless_ai/tests/test_taxonomy_candidates.py
git commit -m "feat: pass taxonomy candidates through build_prompt_with_rag"
```

---

### Task 4: Wire `get_ai_document_classification`

**Files:**

- Modify: `src/paperless_ai/ai_classifier.py`
- Modify: `src/paperless_ai/tests/test_taxonomy_candidates.py`

- [ ] **Step 1: Write the failing tests**

Append to `src/paperless_ai/tests/test_taxonomy_candidates.py`:

```python
from django.test import override_settings

from paperless_ai.ai_classifier import get_ai_document_classification


@pytest.mark.django_db
class TestGetAiDocumentClassificationCandidateWiring:
    @override_settings(LLM_BACKEND="ollama", LLM_MODEL="some_model")
    def test_candidates_fetched_and_passed_when_user_provided(self, mock_doc):
        user = User.objects.create_user(username="tc_wire_user1", password="x")
        fake_candidates = {
            "tags": ["Bloodwork"],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
        }
        with (
            patch(
                "paperless_ai.ai_classifier.get_taxonomy_candidates",
                return_value=fake_candidates,
            ) as mock_candidates,
            patch(
                "paperless_ai.ai_classifier.build_prompt_without_rag",
                return_value="prompt",
            ) as mock_build,
            patch("paperless_ai.client.AIClient.run_llm_query") as mock_llm,
        ):
            mock_llm.return_value = {
                "title": "",
                "tags": [],
                "correspondents": [],
                "document_types": [],
                "storage_paths": [],
                "dates": [],
            }
            get_ai_document_classification(mock_doc, user)

        mock_candidates.assert_called_once_with(user)
        mock_build.assert_called_once_with(mock_doc, fake_candidates)

    @override_settings(LLM_BACKEND="ollama", LLM_MODEL="some_model")
    def test_no_candidates_when_user_is_none(self, mock_doc):
        with (
            patch(
                "paperless_ai.ai_classifier.get_taxonomy_candidates",
            ) as mock_candidates,
            patch(
                "paperless_ai.ai_classifier.build_prompt_without_rag",
                return_value="prompt",
            ) as mock_build,
            patch("paperless_ai.client.AIClient.run_llm_query") as mock_llm,
        ):
            mock_llm.return_value = {
                "title": "",
                "tags": [],
                "correspondents": [],
                "document_types": [],
                "storage_paths": [],
                "dates": [],
            }
            get_ai_document_classification(mock_doc, user=None)

        mock_candidates.assert_not_called()
        mock_build.assert_called_once_with(mock_doc, None)

    @override_settings(
        LLM_BACKEND="ollama",
        LLM_MODEL="some_model",
        LLM_EMBEDDING_BACKEND="huggingface",
        LLM_EMBEDDING_MODEL="some_model",
    )
    def test_candidates_passed_to_rag_prompt_when_embedding_configured(self, mock_doc):
        user = User.objects.create_user(username="tc_wire_user2", password="x")
        fake_candidates = {
            "tags": ["Tax"],
            "correspondents": [],
            "document_types": [],
            "storage_paths": [],
        }
        with (
            patch(
                "paperless_ai.ai_classifier.get_taxonomy_candidates",
                return_value=fake_candidates,
            ),
            patch(
                "paperless_ai.ai_classifier.build_prompt_with_rag",
                return_value="rag_prompt",
            ) as mock_rag,
            patch("paperless_ai.client.AIClient.run_llm_query") as mock_llm,
        ):
            mock_llm.return_value = {
                "title": "",
                "tags": [],
                "correspondents": [],
                "document_types": [],
                "storage_paths": [],
                "dates": [],
            }
            get_ai_document_classification(mock_doc, user)

        mock_rag.assert_called_once_with(mock_doc, user, fake_candidates)
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py::TestGetAiDocumentClassificationCandidateWiring --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: `FAILED` — `get_ai_document_classification` doesn't pass candidates yet.

- [ ] **Step 3: Update `get_ai_document_classification` in `ai_classifier.py`**

Replace the existing `get_ai_document_classification`:

```python
def get_ai_document_classification(
    document: Document,
    user: User | None = None,
) -> dict:
    ai_config = AIConfig()
    candidates = get_taxonomy_candidates(user) if user is not None else None

    prompt = (
        build_prompt_with_rag(document, user, candidates)
        if ai_config.llm_embedding_backend
        else build_prompt_without_rag(document, candidates)
    )

    client = AIClient()
    result = client.run_llm_query(prompt)
    return parse_ai_response(result)
```

- [ ] **Step 4: Run Task 4 tests**

```bash
cd src && uv run pytest paperless_ai/tests/test_taxonomy_candidates.py::TestGetAiDocumentClassificationCandidateWiring --override-ini="addopts=" -v 2>&1 | tail -20
```

Expected: all 3 tests `PASSED`.

- [ ] **Step 5: Run the full `paperless_ai` test suite**

```bash
cd src && uv run pytest paperless_ai/tests/ --override-ini="addopts=" -v 2>&1 | tail -40
```

Expected: all tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/paperless_ai/ai_classifier.py src/paperless_ai/tests/test_taxonomy_candidates.py
git commit -m "feat: wire taxonomy candidates into get_ai_document_classification"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run the broader backend test suite to catch any regressions**

```bash
cd src && uv run pytest documents/tests/test_api_documents.py documents/tests/test_views.py paperless_ai/tests/ --override-ini="addopts=" -q 2>&1 | tail -20
```

Expected: all `PASSED`, no errors.

- [ ] **Step 2: Verify `ai_classifier.py` import order follows project conventions**

Project convention: stdlib → Django → third-party → local, alphabetical within each group. Open `src/paperless_ai/ai_classifier.py` and confirm the new imports (`Count`, model imports, `get_objects_for_user_owner_aware`) are placed in the correct groups in alphabetical order.

- [ ] **Step 3: Final commit if any formatting fixes were needed**

If Step 2 required changes:

```bash
git add src/paperless_ai/ai_classifier.py
git commit -m "chore: fix import ordering in ai_classifier.py"
```
