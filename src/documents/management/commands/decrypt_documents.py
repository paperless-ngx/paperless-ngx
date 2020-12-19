import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

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
            help="If PAPERLESS_PASSPHRASE isn't set already, you need to "
                 "specify it here"
        )

    def handle(self, *args, **options):

        try:
            print(
                "\n\nWARNING: This script is going to work directly on your "
                "document originals, so\nWARNING: you probably shouldn't run "
                "this unless you've got a recent backup\nWARNING: handy.  It "
                "*should* work without a hitch, but be safe and backup your\n"
                "WARNING: stuff first.\n\nHit Ctrl+C to exit now, or Enter to "
                "continue.\n\n"
            )
            __ = input()
        except KeyboardInterrupt:
            return

        passphrase = options["passphrase"] or settings.PASSPHRASE
        if not passphrase:
            raise CommandError(
                "Passphrase not defined.  Please set it with --passphrase or "
                "by declaring it in your environment or your config."
            )

        self.__gpg_to_unencrypted(passphrase)

    @staticmethod
    def __gpg_to_unencrypted(passphrase):

        encrypted_files = Document.objects.filter(
            storage_type=Document.STORAGE_TYPE_GPG)

        for document in encrypted_files:

            print("Decrypting {}".format(
                document).encode('utf-8'))

            old_paths = [document.source_path, document.thumbnail_path]

            raw_document = GnuPG.decrypted(document.source_file, passphrase)
            raw_thumb = GnuPG.decrypted(document.thumbnail_file, passphrase)

            document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

            ext = os.path.splitext(document.filename)[1]

            if not ext == '.gpg':
                raise CommandError(
                    f"Abort: encrypted file {document.source_path} does not "
                    f"end with .gpg")

            document.filename = os.path.splitext(document.filename)[0]

            with open(document.source_path, "wb") as f:
                f.write(raw_document)

            with open(document.thumbnail_path, "wb") as f:
                f.write(raw_thumb)

            Document.objects.filter(id=document.id).update(
                storage_type=document.storage_type, filename=document.filename)

            for path in old_paths:
                os.unlink(path)
