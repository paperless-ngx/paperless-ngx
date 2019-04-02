import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from termcolor import colored as coloured

from documents.models import Document
from paperless.db import GnuPG


class Command(BaseCommand):

    help = (
        "This is how you migrate your stored documents from an encrypted "
        "state to an unencrypted one (or vice-versa)"
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "from",
            choices=("gpg", "unencrypted"),
            help="The state you want to change your documents from"
        )
        parser.add_argument(
            "to",
            choices=("gpg", "unencrypted"),
            help="The state you want to change your documents to"
        )
        parser.add_argument(
            "--passphrase",
            help="If PAPERLESS_PASSPHRASE isn't set already, you need to "
                 "specify it here"
        )

    def handle(self, *args, **options):

        try:
            print(coloured(
                "\n\nWARNING: This script is going to work directly on your "
                "document originals, so\nWARNING: you probably shouldn't run "
                "this unless you've got a recent backup\nWARNING: handy.  It "
                "*should* work without a hitch, but be safe and backup your\n"
                "WARNING: stuff first.\n\nHit Ctrl+C to exit now, or Enter to "
                "continue.\n\n",
                "yellow",
                attrs=("bold",)
            ))
            __ = input()
        except KeyboardInterrupt:
            return

        if options["from"] == options["to"]:
            raise CommandError(
                'The "from" and "to" values can\'t be the same.'
            )

        passphrase = options["passphrase"] or settings.PASSPHRASE
        if not passphrase:
            raise CommandError(
                "Passphrase not defined.  Please set it with --passphrase or "
                "by declaring it in your environment or your config."
            )

        if options["from"] == "gpg" and options["to"] == "unencrypted":
            self.__gpg_to_unencrypted(passphrase)
        elif options["from"] == "unencrypted" and options["to"] == "gpg":
            self.__unencrypted_to_gpg(passphrase)

    @staticmethod
    def __gpg_to_unencrypted(passphrase):

        encrypted_files = Document.objects.filter(
            storage_type=Document.STORAGE_TYPE_GPG)

        for document in encrypted_files:

            print(coloured("Decrypting {}".format(
                document).encode('utf-8'), "green"))

            old_paths = [document.source_path, document.thumbnail_path]
            raw_document = GnuPG.decrypted(document.source_file, passphrase)
            raw_thumb = GnuPG.decrypted(document.thumbnail_file, passphrase)

            document.storage_type = Document.STORAGE_TYPE_UNENCRYPTED

            with open(document.source_path, "wb") as f:
                f.write(raw_document)

            with open(document.thumbnail_path, "wb") as f:
                f.write(raw_thumb)

            document.save(update_fields=("storage_type",))

            for path in old_paths:
                os.unlink(path)

    @staticmethod
    def __unencrypted_to_gpg(passphrase):

        unencrypted_files = Document.objects.filter(
            storage_type=Document.STORAGE_TYPE_UNENCRYPTED)

        for document in unencrypted_files:

            print(coloured("Encrypting {}".format(document), "green"))

            old_paths = [document.source_path, document.thumbnail_path]
            with open(document.source_path, "rb") as raw_document:
                with open(document.thumbnail_path, "rb") as raw_thumb:
                    document.storage_type = Document.STORAGE_TYPE_GPG
                    with open(document.source_path, "wb") as f:
                        f.write(GnuPG.encrypted(raw_document, passphrase))
                    with open(document.thumbnail_path, "wb") as f:
                        f.write(GnuPG.encrypted(raw_thumb, passphrase))

            document.save(update_fields=("storage_type",))

            for path in old_paths:
                os.unlink(path)
