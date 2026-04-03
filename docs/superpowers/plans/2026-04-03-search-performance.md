# Search Performance Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate wasted work in the Tantivy search pipeline — stop generating highlights for 10,000 hits when only 25 are displayed, delegate sorting to Tantivy instead of duplicating it in the ORM, and provide a lightweight ID-only query path.

**Architecture:** Modify `search()` so it still returns ALL matching hits (preserving DRF pagination compatibility) but only generates expensive highlights for a caller-specified page slice. The viewset passes the real DRF `page`/`page_size` as a `highlight_page` parameter so only ~25 hits pay the snippet cost instead of ~10,000. Push DRF `ordering` through to Tantivy's native `order_by_field` instead of re-sorting in Python. Add a lightweight `search_ids()` for cases where only IDs are needed. Keep the ORM intersection as a correctness backstop for filters Tantivy can't express (custom fields, content icontains).

**Key design constraint:** DRF's `PageNumberPagination` trusts `len(object_list)` for page count and slices `object_list[start:end]` for each page. We must NOT pass pre-sliced data with a mismatched length — that causes pages 2+ to return empty. Instead, `TantivyRelevanceList` always contains ALL hits; DRF slices it as usual.

**Tech Stack:** Python, Django REST Framework, tantivy-py, pytest

---

## File Map

| File                                           | Responsibility                                                    | Tasks   |
| ---------------------------------------------- | ----------------------------------------------------------------- | ------- |
| `src/documents/profiling.py`                   | `profile_block()` context manager — wall time, memory, DB queries | 0, 6    |
| `src/documents/search/_backend.py`             | Search backend — `search()`, `search_ids()`, `more_like_this()`   | 1, 2, 3 |
| `src/documents/search/__init__.py`             | Public re-exports                                                 | —       |
| `src/documents/views.py`                       | `UnifiedSearchViewSet.list()` — orchestrates search + pagination  | 4       |
| `src/paperless/views.py`                       | `StandardPagination` — DRF pagination                             | —       |
| `src/documents/tests/search/test_backend.py`   | Backend unit tests                                                | 1, 2, 3 |
| `src/documents/tests/test_api_search.py`       | API integration tests                                             | 4       |
| `src/documents/tests/test_search_profiling.py` | Profiling tests (temporary) — before/after baselines              | 0, 6    |

---

### Task 0: Baseline profiling

Capture performance baselines for the current implementation using `profile_block()` from `src/documents/profiling.py`. This data will be compared against post-implementation measurements in Task 6.

We profile three representative scenarios:

1. **Relevance search** (no ordering) — the default path, exercises highlights for all hits
2. **Sorted search** (ordering=created) — exercises the ORM re-sort path
3. **Paginated search** (page 2) — exercises the overfetch + DRF slice path

**Files:**

- Create: `src/documents/tests/test_search_profiling.py`
- Read: `src/documents/profiling.py`

- [ ] **Step 1: Create the profiling test file**

Create `src/documents/tests/test_search_profiling.py`:

```python
"""
Temporary profiling tests for search performance.

Run with: uv run pytest src/documents/tests/test_search_profiling.py -v -s
The -s flag is required to see profile_block() output on stdout.

Delete this file when profiling is complete.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from documents.models import Document
from documents.profiling import profile_block
from documents.search import get_backend
from documents.search import reset_backend
from documents.tests.utils import DirectoriesMixin

pytestmark = [pytest.mark.search, pytest.mark.django_db]

DOC_COUNT = 200  # Enough to exercise pagination and overfetch behavior


class TestSearchProfilingBaseline(DirectoriesMixin):
    """Baseline profiling of the CURRENT search implementation.

    Run BEFORE making changes, record the output, then compare with Task 6.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        reset_backend()
        self.user = User.objects.create_superuser(username="profiler")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        backend = get_backend()
        for i in range(DOC_COUNT):
            doc = Document.objects.create(
                title=f"Profiling document number {i}",
                content=f"This is searchable content for document {i} with keyword profiling",
                checksum=f"PROF{i:04d}",
                archive_serial_number=i + 1,
            )
            backend.add_or_update(doc)
        yield
        reset_backend()

    def test_profile_relevance_search(self):
        """Profile: relevance-ranked search, no ordering, page 1 default page_size."""
        with profile_block("BEFORE — relevance search (no ordering)"):
            response = self.client.get("/api/documents/?query=profiling")
        assert response.status_code == 200
        assert response.data["count"] == DOC_COUNT

    def test_profile_sorted_search(self):
        """Profile: search with ORM-based ordering (created field)."""
        with profile_block("BEFORE — sorted search (ordering=created)"):
            response = self.client.get(
                "/api/documents/?query=profiling&ordering=created"
            )
        assert response.status_code == 200
        assert response.data["count"] == DOC_COUNT

    def test_profile_paginated_search(self):
        """Profile: search requesting page 2 with explicit page_size."""
        with profile_block("BEFORE — paginated search (page=2, page_size=25)"):
            response = self.client.get(
                "/api/documents/?query=profiling&page=2&page_size=25"
            )
        assert response.status_code == 200
        assert len(response.data["results"]) == 25

    def test_profile_search_with_selection_data(self):
        """Profile: search with include_selection_data=true."""
        with profile_block("BEFORE — search with selection_data"):
            response = self.client.get(
                "/api/documents/?query=profiling&include_selection_data=true"
            )
        assert response.status_code == 200
        assert "selection_data" in response.data

    def test_profile_backend_search_only(self):
        """Profile: raw backend.search() call to isolate Tantivy cost from DRF."""
        backend = get_backend()
        with profile_block("BEFORE — backend.search(page_size=10000, all highlights)"):
            results = backend.search(
                "profiling",
                user=None,
                page=1,
                page_size=10000,
                sort_field=None,
                sort_reverse=False,
            )
        assert results.total == DOC_COUNT

    def test_profile_backend_search_single_page(self):
        """Profile: raw backend.search() with real page size to compare."""
        backend = get_backend()
        with profile_block("BEFORE — backend.search(page_size=25)"):
            results = backend.search(
                "profiling",
                user=None,
                page=1,
                page_size=25,
                sort_field=None,
                sort_reverse=False,
            )
        assert len(results.hits) == 25
```

- [ ] **Step 2: Run the profiling tests and record the output**

```bash
cd /home/trenton/Documents/projects/paperless-ngx
uv run pytest src/documents/tests/test_search_profiling.py -v -s 2>&1 | tee docs/superpowers/plans/profiling-baseline.txt
```

Record the output. The key metrics to compare later:

- **Wall time** for each scenario
- **DB query count** (especially for sorted search — expect extra queries for ORM re-sort)
- **Memory delta** (highlight generation for 200 docs vs 25)
- **Peak memory**

- [ ] **Step 3: Commit the profiling test (temporary)**

```bash
git add src/documents/tests/test_search_profiling.py docs/superpowers/plans/profiling-baseline.txt
git commit -m "test: add baseline profiling tests for search performance"
```

---

### Task 1: Add `highlight_page` parameter to `search()` — generate highlights only for one page

The core performance fix. `search()` still returns ALL matching hits (IDs + scores + ranks), but only generates expensive snippet highlights for a single page slice. Hits outside that page get `highlights={}`.

This preserves DRF compatibility: `TantivyRelevanceList` still has all hits, DRF slices as usual, but only the page being displayed pays the snippet cost.

**Files:**

- Modify: `src/documents/search/_backend.py:428-591` (the `search()` method)
- Test: `src/documents/tests/search/test_backend.py`

- [ ] **Step 1: Write tests for the new highlight_page behavior**

Add to `TestSearch` in `src/documents/tests/search/test_backend.py`:

```python
def test_highlight_page_only_highlights_requested_slice(self, backend: TantivyBackend):
    """Only hits in the highlight_page slice should have non-empty highlights."""
    for i in range(6):
        doc = Document.objects.create(
            title=f"highlight doc {i}",
            content=f"searchable highlight content number {i}",
            checksum=f"HP{i}",
            archive_serial_number=i + 1,
        )
        backend.add_or_update(doc)

    r = backend.search(
        "searchable",
        user=None,
        page=1,
        page_size=10000,
        sort_field="archive_serial_number",
        sort_reverse=False,
        highlight_page=1,
        highlight_page_size=3,
    )
    assert r.total == 6
    assert len(r.hits) == 6
    # First 3 hits (the highlight page) should have highlights
    for hit in r.hits[:3]:
        assert hit["highlights"], f"Hit {hit['id']} should have highlights"
    # Last 3 hits should NOT have highlights
    for hit in r.hits[3:]:
        assert hit["highlights"] == {}, f"Hit {hit['id']} should not have highlights"

def test_highlight_page_2_highlights_correct_slice(self, backend: TantivyBackend):
    """highlight_page=2 should highlight only the second page of results."""
    for i in range(6):
        doc = Document.objects.create(
            title=f"page2 doc {i}",
            content=f"searchable page2 content number {i}",
            checksum=f"HP2{i}",
            archive_serial_number=i + 1,
        )
        backend.add_or_update(doc)

    r = backend.search(
        "searchable",
        user=None,
        page=1,
        page_size=10000,
        sort_field="archive_serial_number",
        sort_reverse=False,
        highlight_page=2,
        highlight_page_size=2,
    )
    assert r.total == 6
    assert len(r.hits) == 6
    # Hits 0-1: no highlights (page 1)
    assert r.hits[0]["highlights"] == {}
    assert r.hits[1]["highlights"] == {}
    # Hits 2-3: highlighted (page 2)
    assert r.hits[2]["highlights"] != {}
    assert r.hits[3]["highlights"] != {}
    # Hits 4-5: no highlights (page 3)
    assert r.hits[4]["highlights"] == {}
    assert r.hits[5]["highlights"] == {}

def test_no_highlight_page_highlights_all(self, backend: TantivyBackend):
    """When highlight_page is not specified, all hits get highlights (backward compat)."""
    for i in range(3):
        doc = Document.objects.create(
            title=f"compat doc {i}",
            content=f"searchable compat content {i}",
            checksum=f"HC{i}",
        )
        backend.add_or_update(doc)

    r = backend.search(
        "searchable",
        user=None,
        page=1,
        page_size=10000,
        sort_field=None,
        sort_reverse=False,
    )
    assert len(r.hits) == 3
    for hit in r.hits:
        assert "content" in hit["highlights"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/trenton/Documents/projects/paperless-ngx
uv run pytest src/documents/tests/search/test_backend.py::TestSearch::test_highlight_page_only_highlights_requested_slice src/documents/tests/search/test_backend.py::TestSearch::test_highlight_page_2_highlights_correct_slice src/documents/tests/search/test_backend.py::TestSearch::test_no_highlight_page_highlights_all -v
```

Expected: FAIL — `search()` doesn't accept `highlight_page` or `highlight_page_size` yet.

- [ ] **Step 3: Implement highlight_page in `search()`**

Modify `search()` in `src/documents/search/_backend.py`. Add `highlight_page` and `highlight_page_size` parameters. The key change is in the hit-building loop: only generate snippets for hits whose index falls within the highlight page.

Change the signature from:

```python
def search(
    self,
    query: str,
    user: AbstractBaseUser | None,
    page: int,
    page_size: int,
    sort_field: str | None,
    *,
    sort_reverse: bool,
    search_mode: SearchMode = SearchMode.QUERY,
) -> SearchResults:
```

To:

```python
def search(
    self,
    query: str,
    user: AbstractBaseUser | None,
    page: int,
    page_size: int,
    sort_field: str | None,
    *,
    sort_reverse: bool,
    search_mode: SearchMode = SearchMode.QUERY,
    highlight_page: int | None = None,
    highlight_page_size: int | None = None,
) -> SearchResults:
```

Then replace the hit-building loop (lines 532-585) with:

```python
        # Build result hits — only generate highlights for the highlight page
        hits: list[SearchHit] = []
        snippet_generator = None

        # Determine which hits need highlights
        if highlight_page is not None and highlight_page_size is not None:
            hl_start = (highlight_page - 1) * highlight_page_size
            hl_end = hl_start + highlight_page_size
        else:
            # Highlight all hits (backward-compatible default)
            hl_start = 0
            hl_end = len(page_hits)

        for rank, (doc_address, score) in enumerate(page_hits, start=offset + 1):
            actual_doc = searcher.doc(doc_address)
            doc_dict = actual_doc.to_dict()
            doc_id = doc_dict["id"][0]

            highlights: dict[str, str] = {}

            # Only generate highlights for hits in the highlight window
            hit_index = rank - offset - 1  # 0-based index within page_hits
            if score > 0 and hl_start <= hit_index < hl_end:
                try:
                    if snippet_generator is None:
                        snippet_generator = tantivy.SnippetGenerator.create(
                            searcher,
                            final_query,
                            self._schema,
                            "content",
                        )

                    content_snippet = snippet_generator.snippet_from_doc(actual_doc)
                    if content_snippet:
                        highlights["content"] = str(content_snippet)

                    if "notes" in doc_dict:
                        notes_generator = tantivy.SnippetGenerator.create(
                            searcher,
                            final_query,
                            self._schema,
                            "notes",
                        )
                        notes_snippet = notes_generator.snippet_from_doc(actual_doc)
                        if notes_snippet:
                            highlights["notes"] = str(notes_snippet)

                except Exception:  # pragma: no cover
                    logger.debug("Failed to generate highlights for doc %s", doc_id)

            hits.append(
                SearchHit(
                    id=doc_id,
                    score=score,
                    rank=rank,
                    highlights=highlights,
                ),
            )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest src/documents/tests/search/test_backend.py::TestSearch -v
```

Expected: ALL tests PASS — both new and existing. The existing tests don't pass `highlight_page`, so they use the backward-compatible default (highlight all).

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_backend.py src/documents/tests/search/test_backend.py
git commit -m "feat: add highlight_page parameter to search() for page-only highlights"
```

---

### Task 2: Add `search_ids()` lightweight method

Add a method that returns only document IDs matching a query — no `searcher.doc()` calls, no snippet generation. This is even lighter than `search()` with `highlight_page` because it skips building `SearchHit` objects entirely. Used by the viewset for `selection_data` when the full hit list isn't needed.

**Files:**

- Modify: `src/documents/search/_backend.py` (add `search_ids()` method after `search()`)
- Test: `src/documents/tests/search/test_backend.py`

- [ ] **Step 1: Write failing tests for search_ids**

Add a new test class in `src/documents/tests/search/test_backend.py`:

```python
class TestSearchIds:
    """Test lightweight ID-only search."""

    def test_returns_matching_ids(self, backend: TantivyBackend):
        """search_ids must return IDs of all matching documents."""
        docs = []
        for i in range(5):
            doc = Document.objects.create(
                title=f"findable doc {i}",
                content="common keyword",
                checksum=f"SI{i}",
            )
            backend.add_or_update(doc)
            docs.append(doc)
        other = Document.objects.create(
            title="unrelated",
            content="nothing here",
            checksum="SI_other",
        )
        backend.add_or_update(other)

        ids = backend.search_ids(
            "common keyword",
            user=None,
            search_mode=SearchMode.QUERY,
        )
        assert set(ids) == {d.pk for d in docs}
        assert other.pk not in ids

    def test_respects_permission_filter(self, backend: TantivyBackend):
        """search_ids must respect user permission filtering."""
        owner = User.objects.create_user("ids_owner")
        other = User.objects.create_user("ids_other")
        doc = Document.objects.create(
            title="private doc",
            content="secret keyword",
            checksum="SIP1",
            owner=owner,
        )
        backend.add_or_update(doc)

        assert backend.search_ids("secret", user=owner, search_mode=SearchMode.QUERY) == [doc.pk]
        assert backend.search_ids("secret", user=other, search_mode=SearchMode.QUERY) == []

    def test_respects_fuzzy_threshold(self, backend: TantivyBackend, settings):
        """search_ids must apply the same fuzzy threshold as search()."""
        doc = Document.objects.create(
            title="threshold test",
            content="unique term",
            checksum="SIT1",
        )
        backend.add_or_update(doc)

        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 1.1
        ids = backend.search_ids("unique", user=None, search_mode=SearchMode.QUERY)
        assert ids == []

    def test_returns_ids_for_text_mode(self, backend: TantivyBackend):
        """search_ids must work with TEXT search mode."""
        doc = Document.objects.create(
            title="text mode doc",
            content="findable phrase",
            checksum="SIM1",
        )
        backend.add_or_update(doc)

        ids = backend.search_ids("findable", user=None, search_mode=SearchMode.TEXT)
        assert ids == [doc.pk]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest src/documents/tests/search/test_backend.py::TestSearchIds -v
```

Expected: FAIL with `AttributeError: 'TantivyBackend' object has no attribute 'search_ids'`

- [ ] **Step 3: Implement `search_ids()`**

Add after the `search()` method in `src/documents/search/_backend.py`:

```python
def search_ids(
    self,
    query: str,
    user: AbstractBaseUser | None,
    *,
    search_mode: SearchMode = SearchMode.QUERY,
    limit: int = 10000,
) -> list[int]:
    """
    Return document IDs matching a query — no highlights, no stored doc fetches.

    This is the lightweight companion to search(). Use it when you need the
    full set of matching IDs (e.g. for ``selection_data``) but don't need
    scores, ranks, or highlights.

    Args:
        query: User's search query
        user: User for permission filtering (None for superuser/no filtering)
        search_mode: Query parsing mode (QUERY, TEXT, or TITLE)
        limit: Maximum number of IDs to return

    Returns:
        List of document IDs in relevance order
    """
    self._ensure_open()
    tz = get_current_timezone()
    if search_mode is SearchMode.TEXT:
        user_query = parse_simple_text_query(self._index, query)
    elif search_mode is SearchMode.TITLE:
        user_query = parse_simple_title_query(self._index, query)
    else:
        user_query = parse_user_query(self._index, query, tz)

    if user is not None:
        permission_filter = build_permission_filter(self._schema, user)
        final_query = tantivy.Query.boolean_query(
            [
                (tantivy.Occur.Must, user_query),
                (tantivy.Occur.Must, permission_filter),
            ],
        )
    else:
        final_query = user_query

    searcher = self._index.searcher()
    results = searcher.search(final_query, limit=limit)

    all_hits = [(hit[1], hit[0]) for hit in results.hits]

    # Normalize scores and apply threshold (same logic as search())
    if all_hits:
        max_score = max(hit[1] for hit in all_hits) or 1.0
        all_hits = [(hit[0], hit[1] / max_score) for hit in all_hits]

    threshold = settings.ADVANCED_FUZZY_SEARCH_THRESHOLD
    if threshold is not None:
        all_hits = [hit for hit in all_hits if hit[1] >= threshold]

    return [searcher.doc(doc_addr).to_dict()["id"][0] for doc_addr, _score in all_hits]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest src/documents/tests/search/test_backend.py::TestSearchIds -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Run existing backend tests to check for regressions**

```bash
uv run pytest src/documents/tests/search/test_backend.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_backend.py src/documents/tests/search/test_backend.py
git commit -m "feat: add search_ids() lightweight ID-only query method"
```

---

### Task 3: Add `more_like_this_ids()` lightweight method

Same pattern as Task 2, but for the more-like-this code path.

**Files:**

- Modify: `src/documents/search/_backend.py` (add `more_like_this_ids()` after `more_like_this()`)
- Test: `src/documents/tests/search/test_backend.py`

- [ ] **Step 1: Write failing test**

Add to `TestMoreLikeThis` in `src/documents/tests/search/test_backend.py`:

```python
def test_more_like_this_ids_excludes_original(self, backend: TantivyBackend):
    """more_like_this_ids must return IDs of similar documents, excluding the original."""
    doc1 = Document.objects.create(
        title="Important document",
        content="financial information report",
        checksum="MLTI1",
        pk=150,
    )
    doc2 = Document.objects.create(
        title="Another document",
        content="financial information report",
        checksum="MLTI2",
        pk=151,
    )
    backend.add_or_update(doc1)
    backend.add_or_update(doc2)

    ids = backend.more_like_this_ids(doc_id=150, user=None)
    assert 150 not in ids
    assert 151 in ids
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest src/documents/tests/search/test_backend.py::TestMoreLikeThis::test_more_like_this_ids_excludes_original -v
```

Expected: FAIL with `AttributeError: 'TantivyBackend' object has no attribute 'more_like_this_ids'`

- [ ] **Step 3: Implement `more_like_this_ids()`**

Add after `more_like_this()` in `src/documents/search/_backend.py`:

```python
def more_like_this_ids(
    self,
    doc_id: int,
    user: AbstractBaseUser | None,
    *,
    limit: int = 10000,
) -> list[int]:
    """
    Return IDs of documents similar to the given document — no highlights.

    Lightweight companion to more_like_this(). The original document is
    excluded from results.

    Args:
        doc_id: Primary key of the reference document
        user: User for permission filtering (None for no filtering)
        limit: Maximum number of IDs to return

    Returns:
        List of similar document IDs (excluding the original)
    """
    self._ensure_open()
    searcher = self._index.searcher()

    id_query = tantivy.Query.range_query(
        self._schema,
        "id",
        tantivy.FieldType.Unsigned,
        doc_id,
        doc_id,
    )
    results = searcher.search(id_query, limit=1)

    if not results.hits:
        return []

    doc_address = results.hits[0][1]
    mlt_query = tantivy.Query.more_like_this_query(
        doc_address,
        min_doc_frequency=1,
        max_doc_frequency=None,
        min_term_frequency=1,
        max_query_terms=12,
        min_word_length=None,
        max_word_length=None,
        boost_factor=None,
    )

    if user is not None:
        permission_filter = build_permission_filter(self._schema, user)
        final_query = tantivy.Query.boolean_query(
            [
                (tantivy.Occur.Must, mlt_query),
                (tantivy.Occur.Must, permission_filter),
            ],
        )
    else:
        final_query = mlt_query

    results = searcher.search(final_query, limit=limit)

    ids = []
    for _score, doc_address in results.hits:
        result_doc_id = searcher.doc(doc_address).to_dict()["id"][0]
        if result_doc_id != doc_id:
            ids.append(result_doc_id)
    return ids
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest src/documents/tests/search/test_backend.py::TestMoreLikeThis -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/documents/search/_backend.py src/documents/tests/search/test_backend.py
git commit -m "feat: add more_like_this_ids() lightweight ID-only method"
```

---

### Task 4: Refactor `UnifiedSearchViewSet.list()` — delegate sorting + page-only highlights

The core viewset refactor. Three changes:

1. **Pass `highlight_page`/`highlight_page_size`** so only the DRF page gets highlights
2. **Pass `sort_field`** through to Tantivy when the field is Tantivy-sortable, eliminating the ORM re-sort query
3. **Fall back to ORM sort** only for custom fields (not in Tantivy's `sort_field_map`)

Critical DRF compatibility note: `TantivyRelevanceList` continues to hold ALL hits. DRF's `PageNumberPagination` slices it as before. The only difference is that hits outside the displayed page have `highlights={}`.

**Files:**

- Modify: `src/documents/views.py:2057-2183` (`UnifiedSearchViewSet.list()`)
- Test: `src/documents/tests/test_api_search.py`

- [ ] **Step 1: Write regression tests before refactoring**

Add to `TestDocumentSearchApi` in `src/documents/tests/test_api_search.py`:

```python
def test_search_with_tantivy_native_sort(self) -> None:
    """When ordering by a Tantivy-sortable field, results must be correctly sorted."""
    backend = get_backend()
    for i, asn in enumerate([30, 10, 20]):
        doc = Document.objects.create(
            title=f"sortable doc {i}",
            content="searchable content",
            checksum=f"TNS{i}",
            archive_serial_number=asn,
        )
        backend.add_or_update(doc)

    response = self.client.get(
        "/api/documents/?query=searchable&ordering=archive_serial_number",
    )
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    asns = [doc["archive_serial_number"] for doc in response.data["results"]]
    self.assertEqual(asns, [10, 20, 30])

    response = self.client.get(
        "/api/documents/?query=searchable&ordering=-archive_serial_number",
    )
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    asns = [doc["archive_serial_number"] for doc in response.data["results"]]
    self.assertEqual(asns, [30, 20, 10])

def test_search_page_2_returns_correct_slice(self) -> None:
    """Page 2 must return the second slice, not overlap with page 1."""
    backend = get_backend()
    for i in range(10):
        doc = Document.objects.create(
            title=f"doc {i}",
            content="paginated content",
            checksum=f"PG2{i}",
            archive_serial_number=i + 1,
        )
        backend.add_or_update(doc)

    response = self.client.get(
        "/api/documents/?query=paginated&ordering=archive_serial_number&page=1&page_size=3",
    )
    page1_ids = [r["id"] for r in response.data["results"]]
    self.assertEqual(len(page1_ids), 3)

    response = self.client.get(
        "/api/documents/?query=paginated&ordering=archive_serial_number&page=2&page_size=3",
    )
    page2_ids = [r["id"] for r in response.data["results"]]
    self.assertEqual(len(page2_ids), 3)

    # No overlap between pages
    self.assertEqual(set(page1_ids) & set(page2_ids), set())
    # Page 2 ASNs are higher than page 1
    page1_asns = [Document.objects.get(pk=pk).archive_serial_number for pk in page1_ids]
    page2_asns = [Document.objects.get(pk=pk).archive_serial_number for pk in page2_ids]
    self.assertTrue(max(page1_asns) < min(page2_asns))

def test_search_all_field_contains_all_ids_when_paginated(self) -> None:
    """The 'all' field must contain every matching ID, even when paginated."""
    backend = get_backend()
    doc_ids = []
    for i in range(10):
        doc = Document.objects.create(
            title=f"all field doc {i}",
            content="allfield content",
            checksum=f"AF{i}",
        )
        backend.add_or_update(doc)
        doc_ids.append(doc.pk)

    response = self.client.get(
        "/api/documents/?query=allfield&page=1&page_size=3",
        headers={"Accept": "application/json; version=9"},
    )
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(len(response.data["results"]), 3)
    # "all" must contain ALL 10 matching IDs
    self.assertCountEqual(response.data["all"], doc_ids)
```

- [ ] **Step 2: Run regression tests against current code to confirm they pass**

```bash
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_with_tantivy_native_sort src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_page_2_returns_correct_slice src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_all_field_contains_all_ids_when_paginated -v
```

Expected: PASS (validates current behavior before refactoring).

- [ ] **Step 3: Refactor `UnifiedSearchViewSet.list()`**

Replace the search section of `list()` in `src/documents/views.py` (lines 2057-2183):

```python
def list(self, request, *args, **kwargs):
    if not self._is_search_request():
        return super().list(request)

    from documents.search import SearchMode
    from documents.search import TantivyRelevanceList
    from documents.search import get_backend

    try:
        backend = get_backend()
        filtered_qs = self.filter_queryset(self.get_queryset())

        user = None if request.user.is_superuser else request.user
        active_search_params = self._get_active_search_params(request)

        if len(active_search_params) > 1:
            raise ValidationError(
                {
                    "detail": _(
                        "Specify only one of text, title_search, query, or more_like_id.",
                    ),
                },
            )

        # Parse ordering param
        ordering_param = request.query_params.get("ordering", "")
        sort_reverse = ordering_param.startswith("-")
        sort_field_name = ordering_param.lstrip("-") if ordering_param else None

        # Fields Tantivy can sort natively (must match sort_field_map in _backend.py)
        tantivy_sortable = {
            "title", "correspondent__name", "document_type__name",
            "created", "added", "modified",
            "archive_serial_number", "page_count", "num_notes",
        }
        use_tantivy_sort = sort_field_name in tantivy_sortable or sort_field_name is None

        # Compute the DRF page so we can tell Tantivy which slice to highlight
        try:
            requested_page = int(request.query_params.get("page", 1))
        except (TypeError, ValueError):
            requested_page = 1
        try:
            requested_page_size = int(
                request.query_params.get("page_size", self.paginator.page_size),
            )
        except (TypeError, ValueError):
            requested_page_size = self.paginator.page_size

        if (
            "text" in request.query_params
            or "title_search" in request.query_params
            or "query" in request.query_params
        ):
            if "text" in request.query_params:
                search_mode = SearchMode.TEXT
                query_str = request.query_params["text"]
            elif "title_search" in request.query_params:
                search_mode = SearchMode.TITLE
                query_str = request.query_params["title_search"]
            else:
                search_mode = SearchMode.QUERY
                query_str = request.query_params["query"]

            if use_tantivy_sort:
                # Fast path: Tantivy sorts, highlights only for DRF page
                results = backend.search(
                    query_str,
                    user=user,
                    page=1,
                    page_size=10000,
                    sort_field=sort_field_name,
                    sort_reverse=sort_reverse,
                    search_mode=search_mode,
                    highlight_page=requested_page,
                    highlight_page_size=requested_page_size,
                )

                # Intersect with ORM-visible IDs (field filters)
                orm_ids = set(filtered_qs.values_list("pk", flat=True))
                ordered_hits = [h for h in results.hits if h["id"] in orm_ids]
            else:
                # Slow path: custom field ordering — ORM must sort
                results = backend.search(
                    query_str,
                    user=user,
                    page=1,
                    page_size=10000,
                    sort_field=None,
                    sort_reverse=False,
                    search_mode=search_mode,
                    highlight_page=requested_page,
                    highlight_page_size=requested_page_size,
                )
                hits_by_id = {h["id"]: h for h in results.hits}
                hit_ids = set(hits_by_id.keys())
                orm_ordered_ids = filtered_qs.filter(id__in=hit_ids).values_list(
                    "pk",
                    flat=True,
                )
                ordered_hits = [
                    hits_by_id[pk] for pk in orm_ordered_ids if pk in hits_by_id
                ]
        else:
            # more_like_id path
            try:
                more_like_doc_id = int(request.query_params["more_like_id"])
                more_like_doc = Document.objects.select_related("owner").get(
                    pk=more_like_doc_id,
                )
            except (TypeError, ValueError, Document.DoesNotExist):
                raise PermissionDenied(_("Invalid more_like_id"))

            if not has_perms_owner_aware(
                request.user,
                "view_document",
                more_like_doc,
            ):
                raise PermissionDenied(_("Insufficient permissions."))

            results = backend.more_like_this(
                more_like_doc_id,
                user=user,
                page=1,
                page_size=10000,
            )
            orm_ids = set(filtered_qs.values_list("pk", flat=True))
            ordered_hits = [h for h in results.hits if h["id"] in orm_ids]

        rl = TantivyRelevanceList(ordered_hits)
        page = self.paginate_queryset(rl)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data["corrected_query"] = None
            if get_boolean(
                str(request.query_params.get("include_selection_data", "false")),
            ):
                all_ids = [h["id"] for h in ordered_hits]
                response.data["selection_data"] = (
                    self._get_selection_data_for_queryset(
                        filtered_qs.filter(pk__in=all_ids),
                    )
                )
            return response

        serializer = self.get_serializer(ordered_hits, many=True)
        return Response(serializer.data)

    except NotFound:
        raise
    except PermissionDenied as e:
        invalid_more_like_id_message = _("Invalid more_like_id")
        if str(e.detail) == str(invalid_more_like_id_message):
            return HttpResponseForbidden(invalid_more_like_id_message)
        return HttpResponseForbidden(_("Insufficient permissions."))
    except ValidationError:
        raise
    except Exception as e:
        logger.warning(f"An error occurred listing search results: {e!s}")
        return HttpResponseBadRequest(
            "Error listing search results, check logs for more detail.",
        )
```

Key changes from current code:

- **`sort_field`** is derived from the `ordering` query param and passed to Tantivy (fast path)
- **`sort_reverse`** is derived from the `-` prefix
- **`highlight_page`/`highlight_page_size`** tell Tantivy which slice to highlight
- **Slow path** (custom field ordering): still uses `sort_field=None` + ORM re-sort, but still benefits from `highlight_page`
- **DRF compatibility**: `TantivyRelevanceList` always contains ALL hits. `__len__()` returns the correct total. DRF slices as usual.
- **`all` field**: unchanged — `get_all_result_ids()` still extracts IDs from the full hit list
- **`selection_data`**: unchanged — still uses `ordered_hits` for all IDs

- [ ] **Step 4: Run the new tests**

```bash
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_with_tantivy_native_sort src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_page_2_returns_correct_slice src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_all_field_contains_all_ids_when_paginated -v
```

Expected: PASS

- [ ] **Step 5: Run ALL existing search tests to check for regressions**

```bash
uv run pytest src/documents/tests/test_api_search.py src/documents/tests/search/test_backend.py -v
```

Expected: All tests PASS. Watch especially for:

- `test_search_multi_page` — pagination correctness across 6 pages
- `test_search_custom_field_ordering` — custom field sort still uses ORM fallback
- `test_search_returns_all_for_api_version_9` — `all` field still works
- `test_search_with_include_selection_data` — selection data still works
- `test_search_invalid_page` — 404 on out-of-bounds pages

- [ ] **Step 6: Commit**

```bash
git add src/documents/views.py src/documents/tests/test_api_search.py
git commit -m "feat: delegate sorting to Tantivy and use page-only highlights in viewset"
```

---

### Task 5: Post-implementation profiling and comparison

Run the same profiling tests from Task 0 against the new implementation and compare results.

**Files:**

- Modify: `src/documents/tests/test_search_profiling.py` (update labels from BEFORE to AFTER)
- Read: `docs/superpowers/plans/profiling-baseline.txt`

- [ ] **Step 1: Update profiling test labels**

In `src/documents/tests/test_search_profiling.py`, rename the class and update all `profile_block()` labels from `"BEFORE —"` to `"AFTER —"`:

```python
class TestSearchProfilingAfter(DirectoriesMixin):
    """Post-implementation profiling of the IMPROVED search implementation.

    Compare output with profiling-baseline.txt.
    """
```

Change every `profile_block("BEFORE —` to `profile_block("AFTER —` throughout the file.

Also add a new test for the `search_ids()` method:

```python
def test_profile_backend_search_ids(self):
    """Profile: raw backend.search_ids() call — lightweight ID-only path."""
    backend = get_backend()
    with profile_block("AFTER — backend.search_ids()"):
        ids = backend.search_ids(
            "profiling",
            user=None,
        )
    assert len(ids) == DOC_COUNT
```

- [ ] **Step 2: Run the profiling tests and record output**

```bash
cd /home/trenton/Documents/projects/paperless-ngx
uv run pytest src/documents/tests/test_search_profiling.py -v -s 2>&1 | tee docs/superpowers/plans/profiling-after.txt
```

- [ ] **Step 3: Compare results**

```bash
diff docs/superpowers/plans/profiling-baseline.txt docs/superpowers/plans/profiling-after.txt
```

Expected improvements:

- **Relevance search**: Fewer snippet generations (25 vs 200), lower memory delta
- **Sorted search**: Fewer DB queries (Tantivy sorts instead of ORM), lower wall time
- **Paginated search**: Only page 2's 25 results get highlights instead of all 200
- **Backend search**: Direct comparison of highlight-all vs highlight-page

- [ ] **Step 4: Record comparison in the plan**

Update this section with the actual numbers once profiling is complete:

| Scenario                  | Metric       | Before | After | Improvement |
| ------------------------- | ------------ | ------ | ----- | ----------- |
| Relevance search          | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Relevance search          | Queries      | _TBD_  | _TBD_ | _TBD_       |
| Relevance search          | Memory delta | _TBD_  | _TBD_ | _TBD_       |
| Sorted search             | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Sorted search             | Queries      | _TBD_  | _TBD_ | _TBD_       |
| Paginated search          | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Backend 10k→25 highlights | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Backend 10k→25 highlights | Memory delta | _TBD_  | _TBD_ | _TBD_       |

- [ ] **Step 5: Commit**

```bash
git add src/documents/tests/test_search_profiling.py docs/superpowers/plans/profiling-after.txt
git commit -m "test: add post-implementation profiling results"
```

- [ ] **Step 6: Clean up profiling artifacts**

The profiling test file and `profiling.py` are temporary. Remove them:

```bash
git rm src/documents/tests/test_search_profiling.py src/documents/profiling.py
git commit -m "chore: remove temporary profiling tests"
```

---

## Post-Implementation Notes

### What these changes accomplish

- **Task 1**: `search()` accepts `highlight_page`/`highlight_page_size` — only the displayed page pays the snippet cost. All hits still returned (DRF pagination works unchanged).
- **Task 2-3**: `search_ids()` and `more_like_this_ids()` provide an even lighter path when only IDs are needed.
- **Task 4**: Viewset passes `sort_field` through to Tantivy for natively-sortable fields, eliminating the ORM re-sort query. Passes `highlight_page` so only 25 hits get snippets instead of 10,000.

### DRF compatibility preserved

| Concern                                   | Status                                                        |
| ----------------------------------------- | ------------------------------------------------------------- |
| `TantivyRelevanceList.__len__()`          | Returns `len(self._hits)` — ALL hits, correct count           |
| `TantivyRelevanceList.__getitem__(slice)` | Slices the full hit list — DRF pagination works               |
| `get_all_result_ids()`                    | Extracts IDs from full hit list — unchanged                   |
| `count` in response                       | Correct — reflects all matching documents after ORM filtering |
| `next`/`previous` links                   | Correct — DRF computes from accurate count                    |
| Page N requests                           | Correct — DRF slices full list at `[(N-1)*size : N*size]`     |

### Performance impact

| Operation                                | Before                 | After                                     |
| ---------------------------------------- | ---------------------- | ----------------------------------------- |
| Snippet generations per search           | Up to 10,000           | ~25 (page size)                           |
| Notes SnippetGenerator creations         | Up to 10,000 (per hit) | ~25 (page size)                           |
| ORM sort query (Tantivy-sortable fields) | Always                 | Never (Tantivy sorts)                     |
| ORM sort query (custom fields)           | Always                 | Still always (fallback)                   |
| `searcher.doc()` calls                   | Up to 10,000           | Up to 10,000 (unchanged — needed for IDs) |
| Tantivy searches per request             | 1                      | 1                                         |

### What's NOT in this plan (future work)

- **Push ORM filters into Tantivy queries**: Would eliminate the ORM intersection (`filtered_qs.values_list`) and potentially reduce the 10k hit fetch. High effort, deferred.
- **Tantivy fast-field ID extraction**: `searcher.doc()` loads the full stored document to get the ID. Tantivy's fast fields could provide IDs without loading stored docs. Depends on tantivy-py API support.
- **Adaptive overfetch limit**: The 10,000 limit is still fixed. Could be made smaller when ORM filters are absent, or adaptive based on historical filter rates.
