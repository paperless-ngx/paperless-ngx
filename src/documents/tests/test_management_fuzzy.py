from io import StringIO

from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase

from documents.models import Document


class TestFuzzyMatchCommand(TestCase):
    MSG_REGEX = r"Document \d fuzzy match to \d \(confidence \d\d\.\d\d\d\)"

    def call_command(self, *args, **kwargs):
        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "document_fuzzy_match",
            "--no-progress-bar",
            *args,
            stdout=stdout,
            stderr=stderr,
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

    def test_invalid_process_count(self) -> None:
        """
        GIVEN:
            - Invalid process count less than 0 above upper
        WHEN:
            - Command is called
        THEN:
            - Error is raised indicating issue
        """
        with self.assertRaises(CommandError) as e:
            self.call_command("--processes", "0")
        self.assertIn("There must be at least 1 process", str(e.exception))

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
        self.assertIn("No matches found", stdout)

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
        self.assertRegex(stdout, self.MSG_REGEX)

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
        stdout, _ = self.call_command()
        lines = [x.strip() for x in stdout.splitlines() if x.strip()]
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertRegex(line, self.MSG_REGEX)

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

        stdout, _ = self.call_command("--delete")

        self.assertIn(
            "The command is configured to delete documents.  Use with caution",
            stdout,
        )
        self.assertRegex(stdout, self.MSG_REGEX)
        self.assertIn("Deleting 1 documents based on ratio matches", stdout)

        self.assertEqual(Document.objects.count(), 2)
        self.assertIsNotNone(Document.objects.get(pk=1))
        self.assertIsNotNone(Document.objects.get(pk=2))

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
        self.assertIn("No matches found", stdout)
