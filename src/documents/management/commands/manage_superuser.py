import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):

    help = """
        Creates a Django superuser based on env variables.
    """.replace("    ", "")

    def handle(self, *args, **options):

        # Get user details from env variables
        PAPERLESS_ADMIN_USER=os.getenv('PAPERLESS_ADMIN_USER')
        PAPERLESS_ADMIN_MAIL=os.getenv('PAPERLESS_ADMIN_MAIL', 'root@localhost')
        PAPERLESS_ADMIN_PASSWORD=os.getenv('PAPERLESS_ADMIN_PASSWORD')

        # If PAPERLESS_ADMIN_USER env variable is set
        if PAPERLESS_ADMIN_USER:
            try:
                # Check if user exists already, leave as is if it does
                if User.objects.filter(username=PAPERLESS_ADMIN_USER).exists():
                    self.stdout.write(f'The user "{PAPERLESS_ADMIN_USER}" already exists! Leaving user as is.')
                elif PAPERLESS_ADMIN_PASSWORD:
                    # Create superuser based on env variables
                    User.objects.create_superuser(PAPERLESS_ADMIN_USER, PAPERLESS_ADMIN_MAIL, PAPERLESS_ADMIN_PASSWORD)
                    self.stdout.write(f'Created superuser "{PAPERLESS_ADMIN_USER}" with provided password.')
                else:
                    self.stdout.write(f'Did not create superuser "{PAPERLESS_ADMIN_USER}".')
                    self.stdout.write('Make sure you specified "PAPERLESS_ADMIN_PASSWORD" in your "docker-compose.env" file.')
            except Exception as error:
                self.stdout.write(f'Exception occured while creating superuser: {error}')