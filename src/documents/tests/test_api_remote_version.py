import json
import urllib.request
from unittest import mock
from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.test import APITestCase

from documents.tests.utils import DirectoriesMixin
from paperless import version


class TestApiRemoteVersion(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/remote_version/"

    def setUp(self):
        super().setUp()

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_enabled_no_update_prefix(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = json.dumps({"tag_name": "ngx-1.6.0"}).encode()
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": "1.6.0",
                "update_available": False,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_enabled_no_update_no_prefix(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = json.dumps(
            {"tag_name": version.__full_version_str__},
        ).encode()
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": version.__full_version_str__,
                "update_available": False,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_enabled_update(self, urlopen_mock):
        new_version = (
            version.__version__[0],
            version.__version__[1],
            version.__version__[2] + 1,
        )
        new_version_str = ".".join(map(str, new_version))

        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = json.dumps(
            {"tag_name": new_version_str},
        ).encode()
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": new_version_str,
                "update_available": True,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_bad_json(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.return_value = b'{ "blah":'
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": "0.0.0",
                "update_available": False,
            },
        )

    @mock.patch("urllib.request.urlopen")
    def test_remote_version_exception(self, urlopen_mock):
        cm = MagicMock()
        cm.getcode.return_value = status.HTTP_200_OK
        cm.read.side_effect = urllib.error.URLError("an error")
        cm.__enter__.return_value = cm
        urlopen_mock.return_value = cm

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data,
            {
                "version": "0.0.0",
                "update_available": False,
            },
        )
