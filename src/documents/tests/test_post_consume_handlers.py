from unittest import mock

from django.test import TestCase, override_settings

from documents.models import Document, Tag, Correspondent
from documents.signals.handlers import run_post_consume_script


class PostConsumeTestCase(TestCase):

    @mock.patch("documents.signals.handlers.Popen")
    @override_settings(POST_CONSUME_SCRIPT=None)
    def test_no_post_consume_script(self, m):
        doc = Document.objects.create(title="Test", mime_type="application/pdf")
        tag1 = Tag.objects.create(name="a")
        tag2 = Tag.objects.create(name="b")
        doc.tags.add(tag1)
        doc.tags.add(tag2)

        run_post_consume_script(None, doc)

        m.assert_not_called()

    @mock.patch("documents.signals.handlers.Popen")
    @override_settings(POST_CONSUME_SCRIPT="script")
    def test_post_consume_script_simple(self, m):
        doc = Document.objects.create(title="Test", mime_type="application/pdf")

        run_post_consume_script(None, doc)

        m.assert_called_once()

    @mock.patch("documents.signals.handlers.Popen")
    @override_settings(POST_CONSUME_SCRIPT="script")
    def test_post_consume_script_with_correspondent(self, m):
        c = Correspondent.objects.create(name="my_bank")
        doc = Document.objects.create(title="Test", mime_type="application/pdf", correspondent=c)
        tag1 = Tag.objects.create(name="a")
        tag2 = Tag.objects.create(name="b")
        doc.tags.add(tag1)
        doc.tags.add(tag2)

        run_post_consume_script(None, doc)

        m.assert_called_once()

        args, kwargs = m.call_args

        command = args[0]

        self.assertEqual(command[0], "script")
        self.assertEqual(command[1], str(doc.pk))
        self.assertEqual(command[5], f"/api/documents/{doc.pk}/download/")
        self.assertEqual(command[6], f"/api/documents/{doc.pk}/thumb/")
        self.assertEqual(command[7], "my_bank")
        self.assertCountEqual(command[8].split(","), ["a", "b"])
