import os
import shutil

from django.test import TestCase, override_settings

from documents.tests.utils import DirectoriesMixin
from paperless import binaries_check, paths_check
from paperless.checks import debug_mode_check


class TestChecks(DirectoriesMixin, TestCase):

    def test_binaries(self):
        self.assertEqual(binaries_check(None), [])

    @override_settings(CONVERT_BINARY="uuuhh", OPTIPNG_BINARY="forgot")
    def test_binaries_fail(self):
        self.assertEqual(len(binaries_check(None)), 2)

    def test_paths_check(self):
        self.assertEqual(paths_check(None), [])

    @override_settings(MEDIA_ROOT="uuh",
                       DATA_DIR="whatever",
                       CONSUMPTION_DIR="idontcare")
    def test_paths_check_dont_exist(self):
        msgs = paths_check(None)
        self.assertEqual(len(msgs), 3, str(msgs))

        for msg in msgs:
            self.assertTrue(msg.msg.endswith("is set but doesn't exist."))

    def test_paths_check_no_access(self):
        os.chmod(self.dirs.data_dir, 0o000)
        os.chmod(self.dirs.media_dir, 0o000)
        os.chmod(self.dirs.consumption_dir, 0o000)

        self.addCleanup(os.chmod, self.dirs.data_dir, 0o777)
        self.addCleanup(os.chmod, self.dirs.media_dir, 0o777)
        self.addCleanup(os.chmod, self.dirs.consumption_dir, 0o777)

        msgs = paths_check(None)
        self.assertEqual(len(msgs), 3)

        for msg in msgs:
            self.assertTrue(msg.msg.endswith("is not writeable"))

    @override_settings(DEBUG=False)
    def test_debug_disabled(self):
        self.assertEqual(debug_mode_check(None), [])

    @override_settings(DEBUG=True)
    def test_debug_enabled(self):
        self.assertEqual(len(debug_mode_check(None)), 1)
