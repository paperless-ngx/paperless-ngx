from asyncore import write
import logging
import os
from sys import stdout

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


logger = logging.getLogger("paperless.management.superuser")


class Command(BaseCommand):

    help = """
        Creates a Django superuser:
        User named: admin
        Email: root@localhost
        with password based on env variable.
        In case any user already exists no
        changes are made
    """.replace(
        "    ", ""
    )

    def handle(self, *args, **options):

        username = "admin"
        mail = "root@localhost"
        password = os.getenv("PAPERLESS_ADMIN_PASSWORD")

        # Check if any superuseruser
        # exists already, leave as is if it does
        if User.objects.filter(is_superuser=True).count() > 0:
            self.stdout.write("Did not create superuser.")
            self.stdout.write("The db already contains superusers")
            return

        if password:
            # Create superuser with password based on env variable
            User.objects.create_superuser(username, mail, password)
            self.stdout.write(f'Created superuser "{username}"')
            self.stdout.write("with provided password.")
            return

        self.stdout.write("Please check if PAPERLESS_ADMIN_PASSWORD")
        self.stdout.write("has been set in docker-compose.env")

        return
