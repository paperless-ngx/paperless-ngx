import json
import shutil
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import Document
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin


class TestEmail(DirectoriesMixin, SampleDirMixin, APITestCase):
    ENDPOINT = "/api/documents/email/"

    def setUp(self):
        super().setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

        self.doc1 = Document.objects.create(
            title="test1",
            mime_type="application/pdf",
            content="this is document 1",
            checksum="1",
            filename="test1.pdf",
            archive_checksum="A1",
            archive_filename="archive1.pdf",
        )
        self.doc2 = Document.objects.create(
            title="test2",
            mime_type="application/pdf",
            content="this is document 2",
            checksum="2",
            filename="test2.pdf",
        )

        # Copy sample files to document paths
        shutil.copy(self.SAMPLE_DIR / "simple.pdf", self.doc1.archive_path)
        shutil.copy(self.SAMPLE_DIR / "simple.pdf", self.doc1.source_path)
        shutil.copy(self.SAMPLE_DIR / "simple.pdf", self.doc2.source_path)

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_success(self):
        """
        GIVEN:
            - Multiple existing documents
        WHEN:
            - API request is made to bulk email documents
        THEN:
            - Email is sent with all documents attached
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk, self.doc2.pk],
                    "addresses": "hello@paperless-ngx.com,test@example.com",
                    "subject": "Bulk email test",
                    "message": "Here are your documents",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Email sent")
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, ["hello@paperless-ngx.com", "test@example.com"])
        self.assertEqual(email.subject, "Bulk email test")
        self.assertEqual(email.body, "Here are your documents")
        self.assertEqual(len(email.attachments), 2)

        # Check attachment names (should default to archive version for doc1, original for doc2)
        attachment_names = [att[0] for att in email.attachments]
        self.assertIn("archive1.pdf", attachment_names)
        self.assertIn("test2.pdf", attachment_names)

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_use_original_version(self):
        """
        GIVEN:
            - Documents with archive versions
        WHEN:
            - API request is made to bulk email with use_archive_version=False
        THEN:
            - Original files are attached instead of archive versions
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                    "use_archive_version": False,
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].attachments[0][0], "test1.pdf")

    def test_email_missing_required_fields(self):
        """
        GIVEN:
            - Request with missing required fields
        WHEN:
            - API request is made to bulk email endpoint
        THEN:
            - Bad request response is returned
        """
        # Missing addresses
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing subject
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "test@example.com",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing message
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "test@example.com",
                    "subject": "Test",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing documents
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_empty_document_list(self):
        """
        GIVEN:
            - Request with empty document list
        WHEN:
            - API request is made to bulk email endpoint
        THEN:
            - Bad request response is returned
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [],
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_invalid_document_id(self):
        """
        GIVEN:
            - Request with non-existent document ID
        WHEN:
            - API request is made to bulk email endpoint
        THEN:
            - Bad request response is returned
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [999],
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_invalid_email_address(self):
        """
        GIVEN:
            - Request with invalid email address
        WHEN:
            - API request is made to bulk email endpoint
        THEN:
            - Bad request response is returned
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "invalid-email",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test multiple addresses with one invalid
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "valid@example.com,invalid-email",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_insufficient_permissions(self):
        """
        GIVEN:
            - User without permissions to view document
        WHEN:
            - API request is made to bulk email documents
        THEN:
            - Forbidden response is returned
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        doc_owned = Document.objects.create(
            title="owned_doc",
            mime_type="application/pdf",
            checksum="owned",
            owner=self.user,
        )

        self.client.force_authenticate(user1)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk, doc_owned.pk],
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch(
        "django.core.mail.message.EmailMessage.send",
        side_effect=Exception("Email error"),
    )
    def test_email_send_error(self, mocked_send):
        """
        GIVEN:
            - Existing documents
        WHEN:
            - API request is made to bulk email and error occurs during email send
        THEN:
            - Server error response is returned
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("Error emailing documents", response.content.decode())
