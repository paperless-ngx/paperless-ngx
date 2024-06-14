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

    def test_invalid_ratio_lower_limit(self):
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
            self.assertIn("The ratio must be between 0 and 100", str(e))

    def test_invalid_ratio_upper_limit(self):
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
            self.assertIn("The ratio must be between 0 and 100", str(e))

    def test_invalid_process_count(self):
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
            self.assertIn("There must be at least 1 process", str(e))

    def test_no_matches(self):
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
        self.assertEqual(stdout, "No matches found\n")

    def test_with_matches(self):
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
        self.assertRegex(stdout, self.MSG_REGEX + "\n")

    def test_with_3_matches(self):
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
        lines = [x.strip() for x in stdout.split("\n") if len(x.strip())]
        self.assertEqual(len(lines), 3)
        self.assertRegex(lines[0], self.MSG_REGEX)
        self.assertRegex(lines[1], self.MSG_REGEX)
        self.assertRegex(lines[2], self.MSG_REGEX)

    def test_document_deletion(self):
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

        lines = [x.strip() for x in stdout.split("\n") if len(x.strip())]
        self.assertEqual(len(lines), 3)
        self.assertEqual(
            lines[0],
            "The command is configured to delete documents.  Use with caution",
        )
        self.assertRegex(lines[1], self.MSG_REGEX)
        self.assertEqual(lines[2], "Deleting 1 documents based on ratio matches")

        self.assertEqual(Document.objects.count(), 2)
        self.assertIsNotNone(Document.objects.get(pk=1))
        self.assertIsNotNone(Document.objects.get(pk=2))
