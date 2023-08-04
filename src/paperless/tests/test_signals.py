from django.http import HttpRequest
from django.test import TestCase

from paperless.signals import handle_failed_login


class TestFailedLoginLogging(TestCase):
    def setUp(self):
        super().setUp()

        self.creds = {
            "username": "john lennon",
        }

    def test_unauthenticated(self):
        """
        GIVEN:
            - Request with no authentication provided
        WHEN:
            - Request provided to signal handler
        THEN:
            - Unable to determine logged for unauthenticated user
        """
        request = HttpRequest()
        request.META = {}
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, {}, request)
            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:No authentication provided. Unable to determine IP address.",
                ],
            )

    def test_none(self):
        """
        GIVEN:
            - Request with no IP possible
        WHEN:
            - Request provided to signal handler
        THEN:
            - Unable to determine logged
        """
        request = HttpRequest()
        request.META = {}
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, self.creds, request)

            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:Login failed for user `john lennon`. Unable to determine IP address.",
                ],
            )

    def test_public(self):
        """
        GIVEN:
            - Request with publicly routeable IP
        WHEN:
            - Request provided to signal handler
        THEN:
            - Expected IP is logged
        """
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "177.139.233.139",
        }
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, self.creds, request)

            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:Login failed for user `john lennon` from IP `177.139.233.139`.",
                ],
            )

    def test_private(self):
        """
        GIVEN:
            - Request with private range IP
        WHEN:
            - Request provided to signal handler
        THEN:
            - Expected IP is logged
            - IP is noted to be a private IP
        """
        request = HttpRequest()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "10.0.0.1",
        }
        with self.assertLogs("paperless.auth") as logs:
            handle_failed_login(None, self.creds, request)

            self.assertEqual(
                logs.output,
                [
                    "INFO:paperless.auth:Login failed for user `john lennon` from private IP `10.0.0.1`.",
                ],
            )
