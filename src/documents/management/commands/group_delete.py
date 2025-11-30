from django.contrib.auth.models import Group
from django.core.management import BaseCommand
from django.db import transaction

from documents.management.commands.mixins import ProgressBarMixin


class Command(ProgressBarMixin, BaseCommand):
    help = "Delete a group"

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            help="Name of the group",
        )

        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)

        with transaction.atomic():
            name = options["name"]
            Group.objects.filter(name=name).delete()
