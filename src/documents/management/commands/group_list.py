from django.contrib.auth.models import Group
from django.core.management import BaseCommand

from documents.management.commands.mixins import ProgressBarMixin


class Command(ProgressBarMixin, BaseCommand):
    help = "List all groups"

    def handle(self, *args, **options):
        groups = Group.objects.all()
        for group in groups:
            self.stdout.write(f"{group.name}\n")
