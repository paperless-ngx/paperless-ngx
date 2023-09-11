from io import StringIO

from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase

from documents.models import Document


class TestFuzzyMatchCommand(TestCase):
    def call_command(self, *args, **kwargs):
        stdout = StringIO()
        stderr = StringIO()
        call_command(
            "document_fuzzy_match",
            *args,
            stdout=stdout,
            stderr=stderr,
            **kwargs,
        )
        return stdout.getvalue(), stderr.getvalue()

    def test_invalid_ratio_lower_limit(self):
        with self.assertRaises(CommandError):
            self.call_command("--ratio", "-1")

    def test_invalid_ratio_upper_limit(self):
        with self.assertRaises(CommandError):
            self.call_command("--ratio", "101")

    def test_no_matches(self):
        # Content similarity is 82.35
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
        stdout, _ = self.call_command()
        self.assertEqual(stdout, "Document 1 fuzzy match to 2 (confidence 86.667)\n")

    def test_with_3_matches(self):
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
        self.assertEqual(lines[0], "Document 1 fuzzy match to 2 (confidence 86.667)")
        self.assertEqual(lines[1], "Document 1 fuzzy match to 3 (confidence 88.136)")
        self.assertEqual(lines[2], "Document 2 fuzzy match to 3 (confidence 88.525)")
