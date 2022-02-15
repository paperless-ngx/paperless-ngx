import logging
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


logger = logging.getLogger("paperless.management.superuser")


class Command(BaseCommand):

    help = """
        Creates a Django superuser based on env variables.
    """.replace("    ", "")

    def handle(self, *args, **options):

        username = os.getenv('PAPERLESS_ADMIN_USER')
        if not username:
            return

        mail = os.getenv('PAPERLESS_ADMIN_MAIL', 'root@localhost')
        password = os.getenv('PAPERLESS_ADMIN_PASSWORD')

        # Check if user exists already, leave as is if it does
        if User.objects.filter(username=username).exists():
            user: User = User.objects.get_by_natural_key(username)
            user.set_password(password)
            user.save()
            self.stdout.write(f"Changed password of user {username}.")
        elif password:
            # Create superuser based on env variables
            User.objects.create_superuser(username, mail, password)
            self.stdout.write(
                f'Created superuser "{username}" with provided password.')
        else:
            self.stdout.write(
                f'Did not create superuser "{username}".')
            self.stdout.write(
                'Make sure you specified "PAPERLESS_ADMIN_PASSWORD" in your '
                '"docker-compose.env" file.')
