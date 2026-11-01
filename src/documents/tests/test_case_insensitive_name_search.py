import unicodedata
from urllib.parse import urlencode

from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import UserFactory


class TestCaseInsensitiveNameSearch(DirectoriesMixin, APITestCase):
    """
    Regression: object-name search was case-sensitive for umlauts.

    DB i* lookups only case-fold ASCII (SQLite LIKE, Postgres UPPER on a
    C-locale database), so "süd" never matched "SÜDSTERN Real II GmbH".
    """

    def setUp(self) -> None:
        super().setUp()
        user = UserFactory(username="temp_admin", superuser=True)
        self.client.force_authenticate(user=user)
        self.upper = Correspondent.objects.create(name="SÜDSTERN Real II GmbH")
        self.lower = Correspondent.objects.create(name="südstern kleine gmbh")
        self.ascii = Correspondent.objects.create(name="ASDF Co")
        self.tag = Tag.objects.create(name="Äpfel und Birnen")
        self.doc_type = DocumentType.objects.create(name="Rechnung ÄÖÜ")
        self.storage_path = StoragePath.objects.create(
            name="Übrige Belege",
            path="Something/{title}",
        )

    def _get(self, url: str, params: dict):
        return self.client.get(f"{url}?{urlencode(params)}")

    def _search_correspondents(self, params: dict) -> set[str]:
        response = self._get("/api/correspondents/", params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {r["name"] for r in response.data["results"]}

    def test_icontains_folds_umlauts_both_directions(self) -> None:
        expected = {"SÜDSTERN Real II GmbH", "südstern kleine gmbh"}
        self.assertEqual(
            self._search_correspondents({"name__icontains": "süd"}),
            expected,
        )
        self.assertEqual(
            self._search_correspondents({"name__icontains": "SÜD"}),
            expected,
        )

    def test_iexact_folds_umlauts(self) -> None:
        self.assertEqual(
            self._search_correspondents({"name__iexact": "SÜDSTERN REAL II GMBH"}),
            {"SÜDSTERN Real II GmbH"},
        )

    def test_istartswith_and_iendswith_fold_umlauts(self) -> None:
        expected = {"SÜDSTERN Real II GmbH", "südstern kleine gmbh"}
        self.assertEqual(
            self._search_correspondents({"name__istartswith": "sÜd"}),
            expected,
        )
        self.assertEqual(
            self._search_correspondents({"name__iendswith": "GmbH"}),
            expected,
        )

    def test_ascii_search_unchanged(self) -> None:
        self.assertEqual(
            self._search_correspondents({"name__icontains": "asdf"}),
            {"ASDF Co"},
        )

    def test_umlaut_search_hits_nothing_without_umlaut(self) -> None:
        self.assertEqual(self._search_correspondents({"name__icontains": "sud"}), set())

    def test_sibling_object_screens_fold_umlauts(self) -> None:
        response = self._get("/api/tags/", {"name__icontains": "äpfel"})
        self.assertEqual(
            {r["name"] for r in response.data["results"]},
            {"Äpfel und Birnen"},
        )
        response = self._get("/api/document_types/", {"name__icontains": "äöü"})
        self.assertEqual(
            {r["name"] for r in response.data["results"]},
            {"Rechnung ÄÖÜ"},
        )
        response = self._get("/api/storage_paths/", {"name__icontains": "ÜBRIGE"})
        self.assertEqual(
            {r["name"] for r in response.data["results"]},
            {"Übrige Belege"},
        )

    def test_global_search_folds_umlauts(self) -> None:
        response = self._get(
            "/api/search/",
            {"query": "süd", "db_only": "true"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {r["name"] for r in response.data["correspondents"]},
            {"SÜDSTERN Real II GmbH", "südstern kleine gmbh"},
        )

    def test_nfc_query_matches_nfd_stored_name(self) -> None:
        # DB round-trips decomposed (NFD) names verbatim; the helper folds
        # both sides to NFC so a normally typed (NFC) query still matches.
        obj = Correspondent.objects.create(
            name=unicodedata.normalize("NFD", "Südufer 2 GmbH"),
        )
        self.assertEqual(
            self._search_correspondents({"name__icontains": "südufer 2"}),
            {obj.name},
        )
