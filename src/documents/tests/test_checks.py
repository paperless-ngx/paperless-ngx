import textwrap
from unittest import mock

from django.core.checks import Error
from django.core.checks import Warning
from django.test import TestCase
from django.test import override_settings

from documents.checks import changed_password_check
from documents.checks import filename_format_check
from documents.checks import parser_check
from documents.models import Document
from documents.tests.factories import DocumentFactory


class TestDocumentChecks(TestCase):
    def test_changed_password_check_empty_db(self):
        self.assertListEqual(changed_password_check(None), [])

    def test_changed_password_check_no_encryption(self):
        DocumentFactory.create(storage_type=Document.STORAGE_TYPE_UNENCRYPTED)
        self.assertListEqual(changed_password_check(None), [])

    def test_encrypted_missing_passphrase(self):
        DocumentFactory.create(storage_type=Document.STORAGE_TYPE_GPG)
        msgs = changed_password_check(None)
        self.assertEqual(len(msgs), 1)
        msg_text = msgs[0].msg
        self.assertEqual(
            msg_text,
            "The database contains encrypted documents but no password is set.",
        )

    @override_settings(
        PASSPHRASE="test",
    )
    @mock.patch("paperless.db.GnuPG.decrypted")
    @mock.patch("documents.models.Document.source_file")
    def test_encrypted_decrypt_fails(self, mock_decrypted, mock_source_file):
        mock_decrypted.return_value = None
        mock_source_file.return_value = b""

        DocumentFactory.create(storage_type=Document.STORAGE_TYPE_GPG)

        msgs = changed_password_check(None)

        self.assertEqual(len(msgs), 1)
        msg_text = msgs[0].msg
        self.assertEqual(
            msg_text,
            textwrap.dedent(
                """
                The current password doesn't match the password of the
                existing documents.

                If you intend to change your password, you must first export
                all of the old documents, start fresh with the new password
                and then re-import them."
                """,
            ),
        )

    def test_parser_check(self):
        self.assertEqual(parser_check(None), [])

        with mock.patch("documents.checks.document_consumer_declaration.send") as m:
            m.return_value = []

            self.assertEqual(
                parser_check(None),
                [
                    Error(
                        "No parsers found. This is a bug. The consumer won't be "
                        "able to consume any documents without parsers.",
                    ),
                ],
            )

    def test_filename_format_check(self):
        self.assertEqual(filename_format_check(None), [])

        with override_settings(FILENAME_FORMAT="{created}/{title}"):
            self.assertEqual(
                filename_format_check(None),
                [
                    Warning(
                        "Filename format {created}/{title} is using the old style, please update to use double curly brackets",
                        hint="{{ created }}/{{ title }}",
                    ),
                ],
            )
