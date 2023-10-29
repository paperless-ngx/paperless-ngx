from django.core.management.base import BaseCommand

from paperless_mail import tasks


class Command(BaseCommand):
    help = "Manually triggers a fetching and processing of all mail accounts"

    def handle(self, *args, **options):
        tasks.process_mail_accounts()
