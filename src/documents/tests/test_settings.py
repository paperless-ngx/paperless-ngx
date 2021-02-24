import logging
from unittest import mock

from django.test import TestCase

from paperless.settings import default_task_workers, default_threads_per_worker


class TestSettings(TestCase):

    @mock.patch("paperless.settings.multiprocessing.cpu_count")
    def test_single_core(self, cpu_count):
        cpu_count.return_value = 1

        default_workers = default_task_workers()

        default_threads = default_threads_per_worker(default_workers)

        self.assertEqual(default_workers, 1)
        self.assertEqual(default_threads, 1)

    def test_workers_threads(self):
        for i in range(1, 64):
            with mock.patch("paperless.settings.multiprocessing.cpu_count") as cpu_count:
                cpu_count.return_value = i

                default_workers = default_task_workers()

                default_threads = default_threads_per_worker(default_workers)

                self.assertTrue(default_workers >= 1)
                self.assertTrue(default_threads >= 1)

                self.assertTrue(default_workers * default_threads <= i, f"{i}")
