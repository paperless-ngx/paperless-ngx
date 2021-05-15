from django.core.management.base import BaseCommand
from documents.sanity_checker import check_sanity


class Command(BaseCommand):

    help = """
        This command checks your document archive for issues.
    """.replace("    ", "")

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown"
        )

    def handle(self, *args, **options):

        messages = check_sanity(progress=not options['no_progress_bar'])

        messages.log_messages()
