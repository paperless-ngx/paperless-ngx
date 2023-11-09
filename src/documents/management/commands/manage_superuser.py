import logging
import os
from argparse import RawTextHelpFormatter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

logger = logging.getLogger("paperless.management.superuser")


class Command(BaseCommand):
    help = (
        "Creates a Django superuser:\n"
        "  User named: admin\n"
        "  Email: root@localhost\n"
        "  Password: based on env variable PAPERLESS_ADMIN_PASSWORD\n"
        "No superuser will be created, when:\n"
        "  - The username is taken already exists\n"
        "  - A superuser already exists\n"
        "  - PAPERLESS_ADMIN_PASSWORD is not set"
    )

    def create_parser(self, *args, **kwargs):
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def handle(self, *args, **options):
        username = os.getenv("PAPERLESS_ADMIN_USER", "admin")
        mail = os.getenv("PAPERLESS_ADMIN_MAIL", "root@localhost")
        password = os.getenv("PAPERLESS_ADMIN_PASSWORD")

        # Check if there's already a user called admin
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.NOTICE(
                    f"Did not create superuser, a user {username} already exists",
                ),
            )
            return

        # Check if any superuseruser
        # exists already, leave as is if it does
        if User.objects.filter(is_superuser=True).count() > 0:
            self.stdout.write(
                self.style.NOTICE(
                    "Did not create superuser, the DB already contains superusers",
                ),
            )
            return

        if password is None:
            self.stdout.write(
                self.style.ERROR(
                    "Please check if PAPERLESS_ADMIN_PASSWORD has been"
                    " set in the environment",
                ),
            )
        else:
            # Create superuser with password based on env variable
            User.objects.create_superuser(username, mail, password)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created superuser "{username}" with provided password.',
                ),
            )
