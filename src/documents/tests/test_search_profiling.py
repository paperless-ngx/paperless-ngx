"""
Temporary profiling tests for search performance.

Run with: uv run pytest src/documents/tests/test_search_profiling.py -v -s -p no:xdist
The -s flag is required to see profile_block() output on stdout.
The -p no:xdist flag disables parallel execution so profiling data is accurate.

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
                "/api/documents/?query=profiling&ordering=created",
            )
        assert response.status_code == 200
        assert response.data["count"] == DOC_COUNT

    def test_profile_paginated_search(self):
        """Profile: search requesting page 2 with explicit page_size."""
        with profile_block("BEFORE — paginated search (page=2, page_size=25)"):
            response = self.client.get(
                "/api/documents/?query=profiling&page=2&page_size=25",
            )
        assert response.status_code == 200
        assert len(response.data["results"]) == 25

    def test_profile_search_with_selection_data(self):
        """Profile: search with include_selection_data=true."""
        with profile_block("BEFORE — search with selection_data"):
            response = self.client.get(
                "/api/documents/?query=profiling&include_selection_data=true",
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
