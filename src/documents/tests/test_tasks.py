from datetime import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from documents import tasks
from documents.models import Document
from documents.sanity_checker import SanityError, SanityFailedError
from documents.tests.utils import DirectoriesMixin


class TestTasks(DirectoriesMixin, TestCase):

    def test_index_reindex(self):
        Document.objects.create(title="test", content="my document", checksum="wow", added=timezone.now(), created=timezone.now(), modified=timezone.now())

        tasks.index_reindex()

    def test_index_optimize(self):
        Document.objects.create(title="test", content="my document", checksum="wow", added=timezone.now(), created=timezone.now(), modified=timezone.now())

        tasks.index_optimize()

    def test_train_classifier(self):
        tasks.train_classifier()

    @mock.patch("documents.tasks.sanity_checker.check_sanity")
    def test_sanity_check(self, m):
        m.return_value = []
        tasks.sanity_check()
        m.assert_called_once()
        m.reset_mock()
        m.return_value = [SanityError("")]
        self.assertRaises(SanityFailedError, tasks.sanity_check)
        m.assert_called_once()

    def test_culk_update_documents(self):
        doc1 = Document.objects.create(title="test", content="my document", checksum="wow", added=timezone.now(),
                                created=timezone.now(), modified=timezone.now())

        tasks.bulk_update_documents([doc1.pk])
