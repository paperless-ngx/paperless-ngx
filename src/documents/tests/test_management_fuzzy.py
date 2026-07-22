from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase

from documents.models import Document
from documents.tests.factories import DocumentFactory


@pytest.mark.management
class TestFuzzyMatchCommand(TestCase):
    def call_command(self, *args, **kwargs):
        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "document_fuzzy_match",
            "--no-progress-bar",
            *args,
            stdout=stdout,
            stderr=stderr,
            skip_checks=True,
            **kwargs,
        )
        return stdout.getvalue(), stderr.getvalue()

    def test_invalid_ratio_lower_limit(self) -> None:
        """
        GIVEN:
            - Invalid ratio below lower limit
        WHEN:
            - Command is called
        THEN:
            - Error is raised indicating issue
        """
        with self.assertRaises(CommandError) as e:
            self.call_command("--ratio", "-1")
        self.assertIn("The ratio must be between 0 and 100", str(e.exception))

    def test_invalid_ratio_upper_limit(self) -> None:
        """
        GIVEN:s
            - Invalid ratio above upper
        WHEN:
            - Command is called
        THEN:
            - Error is raised indicating issue
        """
        with self.assertRaises(CommandError) as e:
            self.call_command("--ratio", "101")
        self.assertIn("The ratio must be between 0 and 100", str(e.exception))

    def test_no_matches(self) -> None:
        """
        GIVEN:
            - 2 documents exist
            - Similarity between content is 82.32
        WHEN:
            - Command is called
        THEN:
            - No matches are found
        """
        Document.objects.create(
            checksum="BEEFCAFE",
            title="A",
            content="first document",
            mime_type="application/pdf",
            filename="test.pdf",
        )
        Document.objects.create(
            checksum="DEADBEAF",
            title="A",
            content="other first document",
            mime_type="application/pdf",
            filename="other_test.pdf",
        )
        stdout, _ = self.call_command()
        self.assertIn("No duplicate documents found", stdout)

    def test_with_matches(self) -> None:
        """
        GIVEN:
            - 2 documents exist
            - Similarity between content is 86.667
        WHEN:
            - Command is called
        THEN:
            - 1 match is returned from doc 1 to doc 2
            - No match from doc 2 to doc 1 reported
        """
        # Content similarity is 86.667
        Document.objects.create(
            checksum="BEEFCAFE",
            title="A",
            content="first document scanned by bob",
            mime_type="application/pdf",
            filename="test.pdf",
        )
        Document.objects.create(
            checksum="DEADBEAF",
            title="A",
            content="first document scanned by alice",
            mime_type="application/pdf",
            filename="other_test.pdf",
        )
        stdout, _ = self.call_command("--processes", "1")
        self.assertIn("Found 1 matching pair(s)", stdout)

    def test_with_3_matches(self) -> None:
        """
        GIVEN:
            - 3 documents exist
            - All documents have similarity over 85.0
        WHEN:
            - Command is called
        THEN:
            - 3 matches is returned from each document to the others
            - No duplication of matches returned
        """
        # Content similarity is 86.667
        Document.objects.create(
            checksum="BEEFCAFE",
            title="A",
            content="first document scanned by bob",
            mime_type="application/pdf",
            filename="test.pdf",
        )
        Document.objects.create(
            checksum="DEADBEAF",
            title="A",
            content="first document scanned by alice",
            mime_type="application/pdf",
            filename="other_test.pdf",
        )
        Document.objects.create(
            checksum="CATTLE",
            title="A",
            content="first document scanned by pete",
            mime_type="application/pdf",
            filename="final_test.pdf",
        )
        stdout, _ = self.call_command("--no-progress-bar", "--processes", "1")
        # 3 docs -> 3 unique pairs; summary confirms count and no duplication
        self.assertIn("Found 3 matching pair(s)", stdout)

    def test_document_deletion(self) -> None:
        """
        GIVEN:
            - 3 documents exist
            - Document 1 to document 3 has a similarity over 85.0
        WHEN:
            - Command is called with the --delete option
        THEN:
            - User is warned about the deletion flag
            - Document 3 is deleted
            - Documents 1 and 2 remain
        """
        # Content similarity is 86.667
        Document.objects.create(
            checksum="BEEFCAFE",
            title="A",
            content="first document scanned by bob",
            mime_type="application/pdf",
            filename="test.pdf",
        )
        Document.objects.create(
            checksum="DEADBEAF",
            title="A",
            content="second document scanned by alice",
            mime_type="application/pdf",
            filename="other_test.pdf",
        )
        Document.objects.create(
            checksum="CATTLE",
            title="A",
            content="first document scanned by pete",
            mime_type="application/pdf",
            filename="final_test.pdf",
        )

        self.assertEqual(Document.objects.count(), 3)

        stdout, _ = self.call_command(
            "--delete",
            "--yes",
            "--no-progress-bar",
            "--processes",
            "1",
        )

        self.assertIn("Delete Mode", stdout)
        self.assertIn("Found 1 matching pair(s)", stdout)
        self.assertIn("Deleting 1 document(s)", stdout)

        self.assertEqual(Document.objects.count(), 2)
        self.assertIsNotNone(Document.objects.get(pk=1))
        self.assertIsNotNone(Document.objects.get(pk=2))

    def test_document_deletion_cancelled(self) -> None:
        """
        GIVEN:
            - 3 documents exist
            - Document 1 to document 3 has a similarity over 85.0
        WHEN:
            - Command is called with --delete but user answers "n" at the prompt
        THEN:
            - No documents are deleted
        """
        DocumentFactory(content="first document scanned by bob")
        DocumentFactory(content="second document scanned by alice")
        DocumentFactory(content="first document scanned by pete")

        self.assertEqual(Document.objects.count(), 3)

        with patch("builtins.input", return_value="n"):
            stdout, _ = self.call_command(
                "--delete",
                "--no-progress-bar",
                "--processes",
                "1",
            )

        self.assertIn("Deletion cancelled", stdout)
        self.assertEqual(Document.objects.count(), 3)

    def test_empty_content(self) -> None:
        """
        GIVEN:
            - 2 documents exist, content is empty (pw-protected)
        WHEN:
            - Command is called
        THEN:
            - No matches are found
        """
        Document.objects.create(
            checksum="BEEFCAFE",
            title="A",
            content="",
            mime_type="application/pdf",
            filename="test.pdf",
        )
        Document.objects.create(
            checksum="DEADBEAF",
            title="A",
            content="",
            mime_type="application/pdf",
            filename="other_test.pdf",
        )
        stdout, _ = self.call_command()
        self.assertIn("No duplicate documents found", stdout)


@pytest.mark.management
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("content_a", "content_b"),
    [
        pytest.param("x" * 90 + "y" * 10, "x" * 100, id="yellow-90pct"),  # 88-92%
        pytest.param("x" * 94 + "y" * 6, "x" * 100, id="red-94pct"),  # 92-97%
        pytest.param("x" * 99 + "y", "x" * 100, id="bold-red-99pct"),  # ≥97%
    ],
)
def test_similarity_color_band(content_a: str, content_b: str) -> None:
    """Each parametrized case exercises one color branch in _render_results."""
    DocumentFactory(content=content_a)
    DocumentFactory(content=content_b)
    stdout = StringIO()
    call_command(
        "document_fuzzy_match",
        "--no-progress-bar",
        "--processes",
        "1",
        stdout=stdout,
        skip_checks=True,
    )
    assert "Found 1 matching pair(s)" in stdout.getvalue()
