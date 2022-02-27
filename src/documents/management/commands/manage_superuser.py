import logging
import os
import re
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


logger = logging.getLogger("paperless.management.superuser")


class Command(BaseCommand):

    help = """
        Creates a Django superuser based on env variables.
        PAPERLESS_ADMIN_USER name of admin user (Default: admin)
        PAPERLESS_ADMIN_MAIL admin email address (Default: root@localhost)
        PAPERLESS_ADMIN_PASSWORD (NODEFAULT)

        Logic:
              Check if password is set, if not exit
              Check is admin user exists, if exists exit
                                          else create
    """.replace("    ", "")

    def handle(self, *args, **options):
        # Get info from env
        username = os.getenv('PAPERLESS_ADMIN_USER', 'admin')
        mail = os.getenv('PAPERLESS_ADMIN_MAIL', 'root@localhost')
        password = os.getenv('PAPERLESS_ADMIN_PASSWORD')

        # Return if email address does not pass basic validation
        if not re.fullmatch(r"[^@]+@[^@]+", mail):
            self.stdout.write(
                'Given email address failed '
                'validation.')
            return

        # Return if password is not set
        if not password:
            self.stdout.write(
                'Make sure you specified "PAPERLESS_ADMIN_PASSWORD" in your '
                '"docker-compose.env" file.')
            return

        # Check if user exists already, leave as is if it does
        if not User.objects.filter(username=username).exists():
            # Create superuser based on env variables
            User.objects.create_superuser(username, mail, password)
            self.stdout.write(
                f'Created superuser "{username}" with provided password.')
        else:
            self.stdout.write(
                f'No changes made as user "{username}" already exists')
