from django.core.management.base import BaseCommand
from documents.sanity_checker import check_sanity


class Command(BaseCommand):

    help = """
        This command checks your document archive for issues.
    """.replace("    ", "")

    def handle(self, *args, **options):

        messages = check_sanity(progress=True)

        messages.log_messages()
