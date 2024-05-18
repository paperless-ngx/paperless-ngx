import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from documents.models import Document
from paperless.db import GnuPG


class Command(BaseCommand):
    help = (
        "This is how you migrate your stored documents from an encrypted "
        "state to an unencrypted one (or vice-versa)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--passphrase",
            help=(
                "If PAPERLESS_PASSPHRASE isn't set already, you need to "
                "specify it here"
            ),
        )

    def handle(self, *args, **options):
        try:
            self.stdout.write(
                self.style.WARNING(
                    "\n\n"
                    "WARNING: This script is going to work directly on your "
                    "document originals, so\n"
                    "WARNING: you probably shouldn't run "
                    "this unless you've got a recent backup\n"
                    "WARNING: handy.  It "
                    "*should* work without a hitch, but be safe and backup your\n"
                    "WARNING: stuff first.\n\n"
                    "Hit Ctrl+C to exit now, or Enter to "
                    "continue.\n\n",
                ),
            )
            _ = input()
        except KeyboardInterrupt:
            return

        passphrase = options["passphrase"] or settings.PASSPHRASE
        if not passphrase:
            raise CommandError(
                "Passphrase not defined.  Please set it with --passphrase or "
                "by declaring it in your environment or your config.",
            )

        self.__gpg_to_unencrypted(passphrase)

    def __gpg_to_unencrypted(self, passphrase: str):
        encrypted_files = Document.objects.filter(
            storage_type=Document.STORAGE_TYPE_GPG,
        )

        for document in encrypted_files:
            self.stdout.write(f"Decrypting {document}")

            old_paths = [document.source_path, document.thumbnail_path]

            with document.source_file as file_handle:
                raw_document = GnuPG.decrypted(file_handle, passphrase)
            with document.thumbnail_file as file_handle:
                raw_thumb = GnuPG.decrypted(file_handle, passphrase)

            document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

            ext = os.path.splitext(document.filename)[1]

            if not ext == ".gpg":
                raise CommandError(
                    f"Abort: encrypted file {document.source_path} does not "
                    f"end with .gpg",
                )

            document.filename = os.path.splitext(document.filename)[0]

            with open(document.source_path, "wb") as f:
                f.write(raw_document)

            with open(document.thumbnail_path, "wb") as f:
                f.write(raw_thumb)

            Document.objects.filter(id=document.id).update(
                storage_type=document.storage_type,
                filename=document.filename,
            )

            for path in old_paths:
                os.unlink(path)
