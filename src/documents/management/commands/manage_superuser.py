import logging
import os
import re
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.forms import EmailField
from django.core.exceptions import ValidationError

def isEmailAddressValid( email ):
    try:
        EmailField().clean(email)
        return True
    except ValidationError:
        return False

logger = logging.getLogger("paperless.management.superuser")


class Command(BaseCommand):

    help = """
        Creates a Django superuser based on env variables.
        PAPERLESS_ADMIN_USER name of admin user (Default: admin)
        PAPERLESS_ADMIN_MAIL admin email address (Default: root@localhost)
        PAPERLESS_ADMIN_PASSWORD (NODEFAULT)

        Logic:
              Check if email is valid, if not exit
              Check if password is set, if not exit
              Check if user count > 0, if yes exit
                                          else create
    """.replace("    ", "")

    def handle(self, *args, **options):
        # Get info from env
        username = os.getenv('PAPERLESS_ADMIN_USER', 'admin')
        mail = os.getenv('PAPERLESS_ADMIN_MAIL', 'root@localhost')
        password = os.getenv('PAPERLESS_ADMIN_PASSWORD')

        # Return if email address does not pass basic validation
        if not isEmailAddressValid(mail):
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

        # Check user count > 0 and exits if users already exist
        if not User.objects.count() > 0:
            # Create superuser based on env variables
            User.objects.create_superuser(username, mail, password)
            self.stdout.write(
                f'Created superuser "{username}" with provided password.')
        else:
            self.stdout.write(
                f'No changes made as there are  already users in the database')
