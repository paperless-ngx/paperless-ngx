from django.core.management.base import BaseCommand

from paperless_mail import mail, tasks


class Command(BaseCommand):

    help = """
    """.replace("    ", "")

    def handle(self, *args, **options):

        tasks.process_mail_accounts()
