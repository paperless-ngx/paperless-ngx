from django.core.management.base import CommandError
from django.test import TestCase

from documents.settings import EXPORTER_FILE_NAME
from ..management.commands.document_importer import Command


class TestImporter(TestCase):

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)

    def test_check_manifest_exists(self):
        cmd = Command()
        self.assertRaises(
            CommandError, cmd._check_manifest_exists, "/tmp/manifest.json")

    def test_check_manifest(self):

        cmd = Command()
        cmd.source = "/tmp"

        cmd.manifest = [{"model": "documents.document"}]
        with self.assertRaises(CommandError) as cm:
            cmd._check_manifest()
        self.assertTrue(
            'The manifest file contains a record' in str(cm.exception))

        cmd.manifest = [{
            "model": "documents.document",
            EXPORTER_FILE_NAME: "noexist.pdf"
        }]
        # self.assertRaises(CommandError, cmd._check_manifest)
        with self.assertRaises(CommandError) as cm:
            cmd._check_manifest()
        self.assertTrue(
            'The manifest file refers to "noexist.pdf"' in str(cm.exception))
