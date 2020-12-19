from django.core.management.base import BaseCommand

from documents.models import Log


class Command(BaseCommand):

    help = "A quick & dirty way to see what's in the logs"

    def handle(self, *args, **options):
        for log in Log.objects.order_by("pk"):
            print(log)
