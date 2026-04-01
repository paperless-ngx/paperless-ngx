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

    def setUp(self) -> None:
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

        # Copy sample files to document paths (using different files to distinguish versions)
        shutil.copy(
            self.SAMPLE_DIR / "documents" / "originals" / "0000001.pdf",
            self.doc1.archive_path,
        )
        shutil.copy(
            self.SAMPLE_DIR / "documents" / "originals" / "0000002.pdf",
            self.doc1.source_path,
        )
        shutil.copy(
            self.SAMPLE_DIR / "documents" / "originals" / "0000003.pdf",
            self.doc2.source_path,
        )

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_success(self) -> None:
        """
        GIVEN:
            - Multiple existing documents (doc1 with archive, doc2 without)
        WHEN:
            - API request is made to bulk email documents
        THEN:
            - Email is sent with all documents attached
            - Archive version used by default for doc1
            - Original version used for doc2 (no archive available)
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

        attachment_names = [att[0] for att in email.attachments]
        self.assertEqual(len(attachment_names), 2)
        self.assertIn(f"{self.doc1!s}.pdf", attachment_names)
        self.assertIn(f"{self.doc2!s}.pdf", attachment_names)

        doc1_attachment = next(
            att for att in email.attachments if att[0] == f"{self.doc1!s}.pdf"
        )
        archive_size = self.doc1.archive_path.stat().st_size
        self.assertEqual(len(doc1_attachment[1]), archive_size)

        doc2_attachment = next(
            att for att in email.attachments if att[0] == f"{self.doc2!s}.pdf"
        )
        original_size = self.doc2.source_path.stat().st_size
        self.assertEqual(len(doc2_attachment[1]), original_size)

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_use_original_version(self) -> None:
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

        attachment = mail.outbox[0].attachments[0]
        self.assertEqual(attachment[0], f"{self.doc1!s}.pdf")

        original_size = self.doc1.source_path.stat().st_size
        self.assertEqual(len(attachment[1]), original_size)

    def test_email_missing_required_fields(self) -> None:
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

    def test_email_empty_document_list(self) -> None:
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

    def test_email_invalid_document_id(self) -> None:
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

    def test_email_invalid_email_address(self) -> None:
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

    def test_email_insufficient_permissions(self) -> None:
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

    def test_email_only_requires_view_permission(self) -> None:
        """
        GIVEN:
            - User having only view documents permission
        WHEN:
            - API request is made to bulk email documents
        THEN:
            - Request succeeds
        """
        user1 = User.objects.create_user(username="test1")
        user1.user_permissions.add(*Permission.objects.filter(codename="view_document"))

        self.client.force_authenticate(user1)

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_duplicate_filenames(self) -> None:
        """
        GIVEN:
            - Multiple documents with the same title
        WHEN:
            - API request is made to bulk email documents
        THEN:
            - Filenames are made unique with counters
        """
        doc3 = Document.objects.create(
            title="test1",
            mime_type="application/pdf",
            content="this is document 3",
            checksum="3",
            filename="test3.pdf",
        )
        shutil.copy(self.SAMPLE_DIR / "simple.pdf", doc3.source_path)

        doc4 = Document.objects.create(
            title="test1",
            mime_type="application/pdf",
            content="this is document 4",
            checksum="4",
            filename="test4.pdf",
        )
        shutil.copy(self.SAMPLE_DIR / "simple.pdf", doc4.source_path)

        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk, doc3.pk, doc4.pk],
                    "addresses": "test@example.com",
                    "subject": "Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        attachment_names = [att[0] for att in mail.outbox[0].attachments]
        self.assertEqual(len(attachment_names), 3)
        self.assertIn(f"{self.doc1!s}.pdf", attachment_names)
        self.assertIn(f"{doc3!s}_01.pdf", attachment_names)
        self.assertIn(f"{doc3!s}_02.pdf", attachment_names)

    @mock.patch(
        "django.core.mail.message.EmailMessage.send",
        side_effect=Exception("Email error"),
    )
    def test_email_send_error(self, mocked_send) -> None:
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

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_cc_bcc(self) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - API request is made with cc and bcc fields
        THEN:
            - Email is sent with correct CC and BCC headers
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "to@example.com",
                    "subject": "CC/BCC Test",
                    "message": "Test message",
                    "cc": "cc1@example.com,cc2@example.com",
                    "bcc": "bcc@example.com",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, ["to@example.com"])
        self.assertEqual(email.cc, ["cc1@example.com", "cc2@example.com"])
        self.assertEqual(email.bcc, ["bcc@example.com"])

    @override_settings(
        EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_empty_cc_bcc(self) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - API request is made without cc and bcc fields
        THEN:
            - Email is sent without CC and BCC headers
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                {
                    "documents": [self.doc1.pk],
                    "addresses": "to@example.com",
                    "subject": "No CC/BCC Test",
                    "message": "Test message",
                },
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, ["to@example.com"])
        self.assertEqual(email.cc, [])
        self.assertEqual(email.bcc, [])


class TestEmailContacts(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/email_contacts/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_create_contact(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            {"name": "John Doe", "email": "john@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "John Doe")
        self.assertEqual(response.data["email"], "john@example.com")

    def test_list_contacts(self) -> None:
        from documents.models import EmailContact

        EmailContact.objects.create(
            name="Alice",
            email="alice@example.com",
            owner=self.user,
        )
        EmailContact.objects.create(
            name="Bob",
            email="bob@example.com",
            owner=self.user,
        )

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_update_contact(self) -> None:
        from documents.models import EmailContact

        contact = EmailContact.objects.create(
            name="Old Name",
            email="old@example.com",
            owner=self.user,
        )
        response = self.client.patch(
            f"{self.ENDPOINT}{contact.pk}/",
            {"name": "New Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "New Name")

    def test_delete_contact(self) -> None:
        from documents.models import EmailContact

        contact = EmailContact.objects.create(
            name="Delete Me",
            email="del@example.com",
            owner=self.user,
        )
        response = self.client.delete(f"{self.ENDPOINT}{contact.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(EmailContact.objects.filter(pk=contact.pk).exists())


class TestEmailTemplates(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/email_templates/"

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

    def test_create_template(self) -> None:
        response = self.client.post(
            self.ENDPOINT,
            {
                "name": "Welcome",
                "subject": "Hello {{ doc_title }}",
                "body": "Please find attached.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Welcome")
        self.assertEqual(response.data["subject"], "Hello {{ doc_title }}")

    def test_list_templates(self) -> None:
        from documents.models import EmailTemplate

        EmailTemplate.objects.create(
            name="T1",
            subject="S1",
            body="B1",
            owner=self.user,
        )
        EmailTemplate.objects.create(
            name="T2",
            subject="S2",
            body="B2",
            owner=self.user,
        )

        response = self.client.get(self.ENDPOINT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_update_template(self) -> None:
        from documents.models import EmailTemplate

        template = EmailTemplate.objects.create(
            name="Old",
            subject="S",
            body="B",
            owner=self.user,
        )
        response = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            {"name": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated")

    def test_delete_template(self) -> None:
        from documents.models import EmailTemplate

        template = EmailTemplate.objects.create(
            name="Del",
            subject="S",
            body="B",
            owner=self.user,
        )
        response = self.client.delete(f"{self.ENDPOINT}{template.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(EmailTemplate.objects.filter(pk=template.pk).exists())
