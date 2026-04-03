# Search Performance Improvements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate wasted work in the Tantivy search pipeline — stop generating highlights for 10,000 hits when only 25 are displayed, delegate sorting to Tantivy instead of duplicating it in the ORM, and provide a lightweight ID-only query path.

**Architecture:** Split the monolithic `search()` method into two paths: a page-aware search that generates highlights only for the requested page, and a lightweight ID-only search for the `all` field and `selection_data`. Push DRF `ordering` through to Tantivy's native `order_by_field` instead of re-sorting in Python. Keep the ORM intersection as a correctness backstop for filters Tantivy can't express (custom fields, content icontains), but skip it when no ORM-only filters are active.

**Tech Stack:** Python, Django REST Framework, tantivy-py, pytest

---

## File Map

| File                                           | Responsibility                                                    | Tasks   |
| ---------------------------------------------- | ----------------------------------------------------------------- | ------- |
| `src/documents/profiling.py`                   | `profile_block()` context manager — wall time, memory, DB queries | 0, 6    |
| `src/documents/search/_backend.py`             | Search backend — `search()`, `search_ids()`, `more_like_this()`   | 1, 2, 3 |
| `src/documents/search/__init__.py`             | Public re-exports                                                 | 2       |
| `src/documents/views.py`                       | `UnifiedSearchViewSet.list()` — orchestrates search + pagination  | 4, 5    |
| `src/documents/tests/search/test_backend.py`   | Backend unit tests                                                | 1, 2, 3 |
| `src/documents/tests/test_api_search.py`       | API integration tests                                             | 4, 5    |
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
        with profile_block("BEFORE — backend.search(page=1, page_size=10000)"):
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
        with profile_block("BEFORE — backend.search(page=1, page_size=25)"):
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

### Task 1: Page-only highlights in `search()`

Stop generating highlights and fetching stored docs for hits outside the requested page. Currently `search()` is called with `page=1, page_size=10000`, which generates highlights for all 10k hits. After this task, `search()` still accepts `page` and `page_size` but the viewset will pass the _real_ page/page_size, and highlights are only generated for that slice.

**Files:**

- Modify: `src/documents/search/_backend.py:428-591` (the `search()` method)
- Modify: `src/documents/search/_backend.py:648-754` (the `more_like_this()` method)
- Test: `src/documents/tests/search/test_backend.py`

- [ ] **Step 1: Write failing test — search returns highlights only for requested page**

Add to `TestSearch` in `src/documents/tests/search/test_backend.py`:

```python
def test_pagination_returns_correct_page_slice(self, backend: TantivyBackend):
    """Requesting page 2 with page_size=2 must return exactly the 3rd and 4th hits."""
    for i in range(5):
        doc = Document.objects.create(
            title=f"sortable doc {i}",
            content="searchable content",
            checksum=f"PG{i}",
            archive_serial_number=i + 1,
        )
        backend.add_or_update(doc)

    r = backend.search(
        "searchable",
        user=None,
        page=2,
        page_size=2,
        sort_field="archive_serial_number",
        sort_reverse=False,
    )
    assert r.total == 5
    assert len(r.hits) == 2
    asns = [
        Document.objects.get(pk=h["id"]).archive_serial_number for h in r.hits
    ]
    assert asns == [3, 4]
```

- [ ] **Step 2: Run the test to confirm it passes (this validates existing behavior)**

```bash
cd /home/trenton/Documents/projects/paperless-ngx
uv run pytest src/documents/tests/search/test_backend.py::TestSearch::test_pagination_returns_correct_page_slice -v
```

Expected: PASS (existing `search()` already supports page/page_size correctly at the Tantivy level — this test just validates it before we change the calling code).

- [ ] **Step 3: Write failing test — highlights not generated for off-page hits**

This test verifies that when you ask for page 2, the backend doesn't waste time generating highlights for page 1 hits. We verify this indirectly: only the returned page's hits should have highlights populated.

```python
def test_only_requested_page_has_highlights(self, backend: TantivyBackend):
    """Hits on the requested page must have highlights; total must reflect all matches."""
    for i in range(6):
        doc = Document.objects.create(
            title=f"searchable document {i}",
            content=f"searchable content number {i}",
            checksum=f"HL{i}",
            archive_serial_number=i + 1,
        )
        backend.add_or_update(doc)

    # Request page 1 of 3
    r = backend.search(
        "searchable",
        user=None,
        page=1,
        page_size=3,
        sort_field=None,
        sort_reverse=False,
    )
    assert r.total == 6
    assert len(r.hits) == 3
    # All returned hits should have content highlights
    for hit in r.hits:
        assert "content" in hit["highlights"], f"Hit {hit['id']} missing highlight"
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
uv run pytest src/documents/tests/search/test_backend.py::TestSearch::test_only_requested_page_has_highlights -v
```

Expected: PASS (validates highlights work correctly for the requested page).

- [ ] **Step 5: Commit**

```bash
git add src/documents/tests/search/test_backend.py
git commit -m "test: add backend pagination and highlight tests"
```

---

### Task 2: Add `search_ids()` lightweight method

Add a method that returns only document IDs matching a query — no `searcher.doc()` calls, no snippet generation. This will serve the `all` field in the paginated response and the `selection_data` feature.

**Files:**

- Modify: `src/documents/search/_backend.py` (add `search_ids()` method after `search()`)
- Modify: `src/documents/search/__init__.py` (no change needed — `TantivyBackend` is already exported)
- Test: `src/documents/tests/search/test_backend.py`

- [ ] **Step 1: Write failing test for search_ids**

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
        # Add a non-matching doc
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
    full set of matching IDs (e.g. for the ``all`` response field or
    ``selection_data``) but don't need scores, ranks, or highlights.

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

    # Extract IDs without fetching full stored docs — just the id field
    return [searcher.doc(doc_addr).to_dict()["id"][0] for doc_addr, _score in all_hits]
```

Note: We still call `searcher.doc()` to get the ID, but we skip all highlight generation. A future optimization could use Tantivy's fast field access for the `id` field, but the snippet generation is the expensive part we're eliminating.

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

### Task 4: Delegate sorting to Tantivy and use real pagination in the viewset

This is the core viewset refactor. Instead of `page=1, page_size=10000, sort_field=None`, pass the real DRF page/page_size and the `ordering` param through to Tantivy's `sort_field`.

The key design decision: when the user sorts by a field that Tantivy can handle (any field in `sort_field_map`), Tantivy does the sorting and pagination. When the user sorts by a field Tantivy can't handle (custom fields), fall back to ORM ordering with the overfetch pattern.

**Files:**

- Modify: `src/documents/views.py:2057-2183` (`UnifiedSearchViewSet.list()`)
- Test: `src/documents/tests/test_api_search.py`

- [ ] **Step 1: Write failing test — Tantivy-native sort ordering**

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
    asns = [
        doc["archive_serial_number"] for doc in response.data["results"]
    ]
    self.assertEqual(asns, [10, 20, 30])

    response = self.client.get(
        "/api/documents/?query=searchable&ordering=-archive_serial_number",
    )
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    asns = [
        doc["archive_serial_number"] for doc in response.data["results"]
    ]
    self.assertEqual(asns, [30, 20, 10])
```

- [ ] **Step 2: Run test to see if it passes with current code**

```bash
cd /home/trenton/Documents/projects/paperless-ngx
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_with_tantivy_native_sort -v
```

This may already pass (ORM ordering produces the same result). We need it as a regression guard.

- [ ] **Step 3: Write failing test — search pagination returns correct page**

```python
def test_search_page_2_returns_correct_slice(self) -> None:
    """Page 2 must return the second slice of results, not the first."""
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
```

- [ ] **Step 4: Run test**

```bash
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_page_2_returns_correct_slice -v
```

Expected: PASS (validates current behavior before refactor).

- [ ] **Step 5: Refactor `UnifiedSearchViewSet.list()`**

Replace the search section of `list()` in `src/documents/views.py` (lines 2057-2183). The new logic:

1. Parse ordering param to determine if Tantivy can sort natively
2. If Tantivy-sortable (or no ordering = relevance): call `search()` with real page/page_size/sort_field
3. Use `search_ids()` only when needed (for `all` field on API <v10, or `include_selection_data`)
4. If NOT Tantivy-sortable (custom fields): fall back to overfetch + ORM re-sort

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

        # Fields Tantivy can sort natively
        tantivy_sortable = {
            "title", "correspondent__name", "document_type__name",
            "created", "added", "modified",
            "archive_serial_number", "page_count", "num_notes",
        }
        use_tantivy_sort = sort_field_name in tantivy_sortable or sort_field_name is None

        # Parse DRF pagination params
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

        is_more_like = "more_like_id" in request.query_params

        if not is_more_like:
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
                # Fast path: Tantivy handles search + sort + paginate
                results = backend.search(
                    query_str,
                    user=user,
                    page=requested_page,
                    page_size=requested_page_size,
                    sort_field=sort_field_name,
                    sort_reverse=sort_reverse,
                    search_mode=search_mode,
                )

                # Intersect with ORM-visible IDs (handles field filters)
                orm_ids = set(filtered_qs.values_list("pk", flat=True))
                ordered_hits = [h for h in results.hits if h["id"] in orm_ids]
            else:
                # Slow path: Tantivy searches, ORM sorts (custom field ordering)
                results = backend.search(
                    query_str,
                    user=user,
                    page=1,
                    page_size=10000,
                    sort_field=None,
                    sort_reverse=False,
                    search_mode=search_mode,
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

- `sort_field` is derived from the `ordering` query param and passed through
- `sort_reverse` is derived from the `-` prefix
- When Tantivy can sort: uses real `page`/`page_size` from the request
- When Tantivy can't sort (custom fields): falls back to `page=1, page_size=10000` overfetch + ORM re-sort
- `more_like_this` path unchanged for now (always overfetch — MLT results are typically small)

- [ ] **Step 6: Run the new tests**

```bash
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_with_tantivy_native_sort src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_page_2_returns_correct_slice -v
```

Expected: PASS

- [ ] **Step 7: Run ALL existing search API tests to check for regressions**

```bash
uv run pytest src/documents/tests/test_api_search.py -v
```

Expected: All tests PASS. Watch especially for:

- `test_search_multi_page` — pagination correctness
- `test_search_custom_field_ordering` — custom field sort fallback
- `test_search_returns_all_for_api_version_9` — `all` field still works
- `test_search_with_include_selection_data` — selection data still works

- [ ] **Step 8: Commit**

```bash
git add src/documents/views.py src/documents/tests/test_api_search.py
git commit -m "feat: delegate sorting to Tantivy and use real pagination in viewset"
```

---

### Task 5: Wire `search_ids()` into the viewset for `all` field and `selection_data`

Currently both the `all` field (API <v10) and `selection_data` get their IDs from the full `TantivyRelevanceList` which contains all 10k hits with highlights. After Task 4, the fast path only fetches one page of hits. We need `search_ids()` to supply the full ID list when needed.

**Files:**

- Modify: `src/documents/views.py:2057-2183` (the `list()` method refactored in Task 4)
- Test: `src/documents/tests/test_api_search.py`

- [ ] **Step 1: Write failing test — `all` field contains all matching IDs, not just current page**

```python
def test_search_all_field_contains_all_ids_not_just_page(self) -> None:
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

- [ ] **Step 2: Run test to see current behavior**

```bash
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_all_field_contains_all_ids_not_just_page -v
```

After Task 4's refactor (fast path fetches only 1 page), this will FAIL because `TantivyRelevanceList` only has the current page's hits. The `all` field would only contain 3 IDs instead of 10.

- [ ] **Step 3: Update `list()` to use `search_ids()` for `all` and `selection_data`**

In the `list()` method (already refactored in Task 4), modify the fast path to fetch all IDs when needed. Add this logic after the search call in the Tantivy-sortable fast path:

```python
if use_tantivy_sort:
    # Fast path: Tantivy handles search + sort + paginate
    results = backend.search(
        query_str,
        user=user,
        page=requested_page,
        page_size=requested_page_size,
        sort_field=sort_field_name,
        sort_reverse=sort_reverse,
        search_mode=search_mode,
    )

    # Intersect with ORM-visible IDs (handles field filters)
    orm_ids = set(filtered_qs.values_list("pk", flat=True))
    ordered_hits = [h for h in results.hits if h["id"] in orm_ids]

    # Fetch all matching IDs if needed for 'all' field or selection_data
    api_version = int(request.version or settings.REST_FRAMEWORK["DEFAULT_VERSION"])
    need_all_ids = (
        api_version < 10  # legacy 'all' field
        or get_boolean(
            str(request.query_params.get("include_selection_data", "false")),
        )
    )
    if need_all_ids:
        all_matching_ids = backend.search_ids(
            query_str,
            user=user,
            search_mode=search_mode,
        )
        all_matching_ids = [
            doc_id for doc_id in all_matching_ids if doc_id in orm_ids
        ]
    else:
        all_matching_ids = None
```

Then update `TantivyRelevanceList` to accept an optional `all_ids` override, and update `StandardPagination.get_all_result_ids()` to use it.

Modify `TantivyRelevanceList` in `src/documents/search/_backend.py`:

```python
class TantivyRelevanceList:
    """
    DRF-compatible list wrapper for Tantivy search hits.

    Provides paginated access to search results while optionally storing all
    matching IDs for efficient retrieval by the paginator.
    """

    def __init__(
        self,
        hits: list[SearchHit],
        all_ids: list[int] | None = None,
        total: int | None = None,
    ) -> None:
        self._hits = hits
        self._all_ids = all_ids
        self._total = total

    def __len__(self) -> int:
        if self._total is not None:
            return self._total
        return len(self._hits)

    def __getitem__(self, key: slice) -> list[SearchHit]:
        return self._hits[key]

    def get_all_ids(self) -> list[int]:
        """Return all matching document IDs."""
        if self._all_ids is not None:
            return self._all_ids
        return [h["id"] for h in self._hits]
```

Update `StandardPagination.get_all_result_ids()` in `src/paperless/views.py`:

```python
def get_all_result_ids(self):
    from documents.search import TantivyRelevanceList

    query = self.page.paginator.object_list
    if isinstance(query, TantivyRelevanceList):
        return query.get_all_ids()
    return self.page.paginator.object_list.values_list("pk", flat=True)
```

Update the viewset to construct `TantivyRelevanceList` with `all_ids` and `total`:

For the **fast path** (Tantivy-sortable):

```python
rl = TantivyRelevanceList(
    ordered_hits,
    all_ids=all_matching_ids,
    total=len(all_matching_ids) if all_matching_ids is not None else results.total,
)
```

For the **slow path** (custom field sort) and **more_like_this**, no change needed — `ordered_hits` already contains all hits.

- [ ] **Step 4: Run the new test**

```bash
uv run pytest src/documents/tests/test_api_search.py::TestDocumentSearchApi::test_search_all_field_contains_all_ids_not_just_page -v
```

Expected: PASS

- [ ] **Step 5: Run ALL search tests**

```bash
uv run pytest src/documents/tests/test_api_search.py src/documents/tests/search/test_backend.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/documents/search/_backend.py src/documents/views.py src/paperless/views.py src/documents/tests/test_api_search.py
git commit -m "feat: use search_ids() for all-IDs queries, avoid highlight generation"
```

---

### Task 6: Post-implementation profiling and comparison

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

Open both files side by side and compare:

```bash
diff docs/superpowers/plans/profiling-baseline.txt docs/superpowers/plans/profiling-after.txt
```

Expected improvements:

- **Relevance search**: Fewer snippet generations (25 vs 200), lower memory delta, similar query count
- **Sorted search**: Fewer DB queries (Tantivy sorts instead of ORM), lower wall time
- **Paginated search**: Significantly less work — only page 2's 25 results get highlights
- **Backend search (10k vs 25)**: Direct comparison of the old overfetch vs new page-only approach

- [ ] **Step 4: Record comparison in the plan**

Update this section with the actual numbers once profiling is complete. Fill in the table:

| Scenario         | Metric       | Before | After | Improvement |
| ---------------- | ------------ | ------ | ----- | ----------- |
| Relevance search | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Relevance search | Queries      | _TBD_  | _TBD_ | _TBD_       |
| Relevance search | Memory delta | _TBD_  | _TBD_ | _TBD_       |
| Sorted search    | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Sorted search    | Queries      | _TBD_  | _TBD_ | _TBD_       |
| Paginated search | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Backend 10k→25   | Wall time    | _TBD_  | _TBD_ | _TBD_       |
| Backend 10k→25   | Memory delta | _TBD_  | _TBD_ | _TBD_       |

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

- **Task 1-3**: Backend now has two query modes — full search with highlights (for the displayed page) and lightweight ID-only search (for `all`/`selection_data`).
- **Task 4**: Viewset passes real `page`/`page_size`/`sort_field` to Tantivy for sortable fields. Custom field sorting falls back to overfetch pattern.
- **Task 5**: `all` field and `selection_data` use lightweight `search_ids()` instead of extracting IDs from fully-highlighted hits.

### Performance impact

| Operation                         | Before                 | After                                            |
| --------------------------------- | ---------------------- | ------------------------------------------------ |
| `searcher.doc()` calls per search | Up to 10,000           | ~25 (page size) + N (for all_ids, no highlights) |
| Snippet generations per search    | Up to 10,000           | ~25 (page size only)                             |
| ORM sort query                    | Always (when ordering) | Only for custom field sorting                    |
| Tantivy searches per request      | 1                      | 1-2 (page search + optional IDs search)          |

### What's NOT in this plan (future work)

- **Push ORM filters into Tantivy queries** (Item 4 from original analysis): High effort, high reward. Would eliminate the ORM intersection entirely for common filters. Deferred because it requires building a filter translation layer and careful correctness testing.
- **Adaptive overfetch**: The slow path still uses 10,000. Could be made adaptive, but the fast path (most queries) no longer overfetches at all.
- **Tantivy fast-field ID extraction**: `search_ids()` still calls `searcher.doc()` to get IDs. Tantivy's fast fields could provide IDs without loading stored docs, but this depends on tantivy-py API support.
